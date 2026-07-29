"""AI 重跑把 S3 物件 key 圖片重新 inline 成 base64 送下游(task-533)。

v2.2.1 把附件改存 S3 後,`request_content` 裡的圖片變成**物件 key**,而
`request_snapshot._is_replayable` 會把物件 key 形態的 image part 剔除 —— 結果是
「messages 模式 + 含圖」的紀錄重跑時失去圖片,退化成純文字比較(v2.2.0 本來會送 base64)。

本檔鎖住修復後的行為與三條紅線:

1. **下游收到的內容與 v2.2.0 等價**:inline 後的 base64 decode == S3 物件原始 bytes。
2. 🔴 **base64 絕不回流 DB**:落地的 `request_content` 與 discriminator prompt 一律用
   **原始**快照(物件 key),否則 v2.2.1「快照零 base64」硬規則當場破功。
3. 🔴 **禁用 presigned URL**:presigned URL 視同臨時憑證,禁送下游模型
   (`90-third-party-service/09-object-storage.md`);stub 的 `presign_get` 一被呼叫即失敗。

策略同 `test_ai_model_eval_rerun.py`:真 DB(禁 mock SQL)+ respx 攔下游 payload;
S3 一律走 stub,**不打真 AWS**。DB 不可用時由共用 fixture 自行 skip。
"""

from __future__ import annotations

import base64
import json
import logging
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
import pytest_asyncio
import respx
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

import app.services.ai_model_eval_rerun as svc
from app.clients.s3 import S3NotFoundError, S3TimeoutError

# seed / 假回覆 / 下游斷言等腳手架與 task-405 的重跑測試共用一份,避免兩邊漂移。
from tests.services.test_ai_model_eval_rerun import (
    _OR_BASE_URL,
    _TEST_KEY,
    TEST_DATABASE_URL,
    _challenger_response,
    _discriminator_response,
    _is_discriminator,
    _list_reruns,
    _make_client,
    _seed,
    _uniq,
)


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """外層 transaction + 加入式 session;測試結束整批 rollback(不污染 dev DB)。"""
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=None)
    try:
        conn = await engine.connect()
    except (OSError, OperationalError) as exc:  # pragma: no cover - 環境相依
        await engine.dispose()
        pytest.skip(f"測試 DB 無法連線({TEST_DATABASE_URL}):{exc}")

    trans = await conn.begin()
    session = AsyncSession(bind=conn, expire_on_commit=False)
    try:
        yield session
    finally:
        await session.close()
        if trans.is_active:
            await trans.rollback()
        await conn.close()
        await engine.dispose()

# --- fixtures:同一份輸入在 v2.2.1 下的四種附件形態 ---------------------------

TEXT = "這張圖裡的錯誤訊息是什麼?"
IMAGE_BYTES = b"\x89PNG\r\n\x1a\n" + b"fake-image-payload" * 8
IMAGE_KEY = "dev/chat/2026/07/29/req-uid/0-0123456789abcdef.png"
IMAGE_KEY_2 = "dev/chat/2026/07/29/req-uid/1-fedcba9876543210.png"
LEGACY_DATA_URI = "data:image/png;base64,QUJD"
REMOTE_URL = "https://cdn.example.com/a.png"

PART_TEXT: dict[str, Any] = {"type": "text", "text": TEXT}
PART_S3: dict[str, Any] = {"type": "image_url", "image_url": {"url": IMAGE_KEY}}
PART_S3_2: dict[str, Any] = {"type": "image_url", "image_url": {"url": IMAGE_KEY_2}}
PART_LEGACY: dict[str, Any] = {"type": "image_url", "image_url": {"url": LEGACY_DATA_URI}}
PART_REMOTE: dict[str, Any] = {"type": "image_url", "image_url": {"url": REMOTE_URL}}
PART_FAILED: dict[str, Any] = {
    "type": "image_url",
    "upload_failed": True,
    "mime": "image/png",
    "bytes": 3,
    "sha256": "ab" * 32,
    "reason": "s3_upload_failed",
}

_BASE64_MARKER = ";base64,"


def _messages_snapshot(*parts: dict[str, Any]) -> dict[str, Any]:
    """messages 直傳模式的快照(v2.1.2 形狀;附件值為 v2.2.1 形態)。"""
    return {
        "model": "openai/gpt-4o",
        "messages": [
            {"role": "system", "content": "你是除錯助理"},
            {"role": "user", "content": [PART_TEXT, *parts]},
        ],
    }


class _StubS3:
    """S3 stub:記錄每次下載,並在 `presign_get` 被呼叫時直接讓測試失敗。

    `objects` 為 key → `(bytes, content_type)`;不在表內的 key 拋 `S3NotFoundError`,
    `fail_keys` 內的 key 拋 `S3TimeoutError`(模擬 S3 不可用)。
    """

    def __init__(
        self,
        objects: dict[str, tuple[bytes, str]] | None = None,
        *,
        fail_keys: frozenset[str] = frozenset(),
    ) -> None:
        self._objects = objects or {}
        self._fail_keys = fail_keys
        self.get_calls: list[str] = []

    async def get_object(self, key: str) -> tuple[bytes, str]:
        self.get_calls.append(key)
        if key in self._fail_keys:
            raise S3TimeoutError("S3 get_object 逾時", operation="get_object", key=key)
        if key not in self._objects:
            raise S3NotFoundError(
                "S3 物件不存在:NoSuchKey", operation="get_object", key=key, aws_code="NoSuchKey"
            )
        return self._objects[key]

    async def presign_get(self, key: str, ttl: int) -> str:
        raise AssertionError("重跑禁用 presigned URL(禁送下游模型)")


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    *,
    stub: _StubS3 | None = None,
    discriminator: bool = False,
    s3_enabled: bool | None = None,
) -> list[str]:
    """注入 settings + S3 client 工廠;回傳「工廠被呼叫」的紀錄 list。

    `s3_enabled=None` 時 settings **刻意不帶** `S3_STORAGE_ENABLED` —— 一旦程式碼在
    「快照無物件 key 圖片」的情境下讀了它,就會 AttributeError 當場炸掉,
    這正是「完全不碰 S3」要鎖的行為。
    """
    attrs: dict[str, object] = {
        "DEFAULT_OPENROUTER_KEY": _TEST_KEY,
        "AI_RERUN_DISCRIMINATOR_ENABLED": discriminator,
    }
    if s3_enabled is not None:
        attrs["S3_STORAGE_ENABLED"] = s3_enabled
    monkeypatch.setattr(svc, "get_settings", lambda: SimpleNamespace(**attrs))

    factory_calls: list[str] = []

    def _get_s3_client() -> _StubS3:
        factory_calls.append("get_s3_client")
        if stub is None:
            raise AssertionError("本情境不應取用 S3 client")
        return stub

    monkeypatch.setattr(svc, "get_s3_client", _get_s3_client)
    return factory_calls


def _image_parts(request: httpx.Request) -> list[dict[str, Any]]:
    """取下游 payload 內的 image_url parts(challenger 呼叫)。"""
    body = json.loads(request.content)
    parts: list[dict[str, Any]] = []
    for msg in body["messages"]:
        content = msg.get("content")
        if isinstance(content, list):
            parts += [p for p in content if p.get("type") == "image_url"]
    return parts


def _urls(request: httpx.Request) -> list[str]:
    return [p["image_url"]["url"] for p in _image_parts(request)]


# --- (1) 物件 key → 下載 + inline,下游收到的內容與 v2.2.0 等價 -----------------


@respx.mock(base_url=_OR_BASE_URL)
async def test_object_key_image_is_inlined_as_base64_data_uri(
    respx_mock, db_session: AsyncSession, monkeypatch
) -> None:
    stub = _StubS3({IMAGE_KEY: (IMAGE_BYTES, "image/png")})
    _patch(monkeypatch, stub=stub, s3_enabled=True)
    challenger = _uniq("anthropic/claude-haiku")
    seed = await _seed(
        db_session,
        recommends=[challenger, None, None],
        extra_models=[challenger],
        request_content=_messages_snapshot(PART_S3),
    )

    route = respx_mock.post("/chat/completions").mock(
        side_effect=lambda req: _challenger_response("看到了", cost=0.001, total_tokens=30)
    )

    client = _make_client()
    await svc.rerun_evaluation(seed.eval_uid, db=db_session, client=client)
    await client._client.aclose()

    urls = _urls(route.calls[0].request)
    assert len(urls) == 1
    assert urls[0].startswith("data:image/png;base64,")
    # 🔴 下游收到的內容與 v2.2.0 等價:decode 回來就是 S3 物件的原始 bytes。
    assert base64.b64decode(urls[0].split(",", 1)[1]) == IMAGE_BYTES
    # 只下載一次,且全程未動用 presigned URL(stub 的 presign_get 會直接失敗)。
    assert stub.get_calls == [IMAGE_KEY]

    reruns = await _list_reruns(db_session, seed.eval_uid)
    assert len(reruns) == 1
    assert reruns[0].status == "success"


@respx.mock(base_url=_OR_BASE_URL)
async def test_object_key_downloaded_once_for_multiple_challengers(
    respx_mock, db_session: AsyncSession, monkeypatch
) -> None:
    """多個 challenger 共用同一份 inline 結果:S3 只下載一次(成本 / 延遲不隨 challenger 放大)。"""
    stub = _StubS3({IMAGE_KEY: (IMAGE_BYTES, "image/png")})
    _patch(monkeypatch, stub=stub, s3_enabled=True)
    ch1 = _uniq("anthropic/claude-haiku")
    ch2 = _uniq("openai/gpt-mini")
    seed = await _seed(
        db_session,
        recommends=[ch1, ch2, None],
        extra_models=[ch1, ch2],
        # 同一張圖出現兩次:去重後仍只下載一次。
        request_content=_messages_snapshot(PART_S3, PART_S3),
    )

    route = respx_mock.post("/chat/completions").mock(
        side_effect=lambda req: _challenger_response("看到了", cost=0.001, total_tokens=30)
    )

    client = _make_client()
    await svc.rerun_evaluation(seed.eval_uid, db=db_session, client=client)
    await client._client.aclose()

    assert route.call_count == 2
    assert stub.get_calls == [IMAGE_KEY]
    assert len(_urls(route.calls[0].request)) == 2
    assert len(_urls(route.calls[1].request)) == 2


# --- (2) 🔴 base64 不得回流 DB / 不得進 discriminator prompt --------------------


@respx.mock(base_url=_OR_BASE_URL)
async def test_inlined_base64_never_reaches_db_or_discriminator_prompt(
    respx_mock, db_session: AsyncSession, monkeypatch
) -> None:
    """落地與 prompt 一律用**原始** request_content(物件 key),inline 版只給下游。"""
    stub = _StubS3({IMAGE_KEY: (IMAGE_BYTES, "image/png")})
    _patch(monkeypatch, stub=stub, discriminator=True, s3_enabled=True)
    challenger = _uniq("anthropic/claude-haiku")
    snapshot = _messages_snapshot(PART_S3)
    seed = await _seed(
        db_session,
        recommends=[challenger, None, None],
        extra_models=[challenger],
        request_content=snapshot,
    )

    prompt_inputs: list[dict[str, Any]] = []
    real_build = svc.build_discriminator_prompt

    def _spy_build(request_content, output_a, output_b, **kwargs):  # type: ignore[no-untyped-def]
        prompt_inputs.append(dict(request_content))
        return real_build(request_content, output_a, output_b, **kwargs)

    monkeypatch.setattr(svc, "build_discriminator_prompt", _spy_build)

    def _handler(req: httpx.Request) -> httpx.Response:
        if _is_discriminator(req):
            return _discriminator_response("B", 0.8, "challenger 看得到圖")
        return _challenger_response("看到了", cost=0.001, total_tokens=30)

    route = respx_mock.post("/chat/completions").mock(side_effect=_handler)

    client = _make_client()
    await svc.rerun_evaluation(seed.eval_uid, db=db_session, client=client, blind_swap=False)
    await client._client.aclose()

    # 下游 challenger payload 確實帶了 base64(功能有生效),才有「不回流」可談。
    assert _BASE64_MARKER in route.calls[0].request.content.decode()

    # 🔴 落地 DB 的 request_content:零 base64,仍是物件 key。
    reruns = await _list_reruns(db_session, seed.eval_uid)
    assert len(reruns) == 1
    persisted = json.dumps(reruns[0].request_content, ensure_ascii=False)
    assert _BASE64_MARKER not in persisted
    assert IMAGE_KEY in persisted
    # 其餘會落地的 JSONB 欄位(輸出摘要)亦然。
    assert _BASE64_MARKER not in json.dumps(reruns[0].response_summary or {}, ensure_ascii=False)

    # 🔴 discriminator prompt 的輸入:同樣是原始快照。
    assert len(prompt_inputs) == 1
    assert _BASE64_MARKER not in json.dumps(prompt_inputs[0], ensure_ascii=False)
    disc_bodies = [
        c.request.content.decode() for c in route.calls if _is_discriminator(c.request)
    ]
    assert len(disc_bodies) == 1
    assert _BASE64_MARKER not in disc_bodies[0]

    # ORM 的 JSONB 物件未被就地改動(否則 base64 會被 flush 回 usage_logs)。
    assert snapshot["messages"][1]["content"][1] == PART_S3
    assert _BASE64_MARKER not in json.dumps(snapshot, ensure_ascii=False)


# --- (3) 其餘三種形態:行為與現況一致,且完全不碰 S3 ---------------------------


@pytest.mark.parametrize(
    ("part", "expected_urls"),
    [
        (PART_LEGACY, [LEGACY_DATA_URI]),
        (PART_REMOTE, [REMOTE_URL]),
        (PART_FAILED, []),
    ],
    ids=["legacy_data_uri", "remote_url", "upload_failed"],
)
@respx.mock(base_url=_OR_BASE_URL)
async def test_non_object_key_forms_untouched_and_never_call_s3(
    respx_mock,
    db_session: AsyncSession,
    monkeypatch,
    part: dict[str, Any],
    expected_urls: list[str],
) -> None:
    """data URI / 遠端 URL 原樣送出、upload_failed 剔除;三者皆**不取 client、不讀 S3 設定**。

    (`_patch` 的 settings 刻意不含 `S3_STORAGE_ENABLED`:讀了就 AttributeError。)
    """
    factory_calls = _patch(monkeypatch)
    challenger = _uniq("anthropic/claude-haiku")
    seed = await _seed(
        db_session,
        recommends=[challenger, None, None],
        extra_models=[challenger],
        request_content=_messages_snapshot(part),
    )

    route = respx_mock.post("/chat/completions").mock(
        side_effect=lambda req: _challenger_response("ok", cost=0.001, total_tokens=30)
    )

    client = _make_client()
    await svc.rerun_evaluation(seed.eval_uid, db=db_session, client=client)
    await client._client.aclose()

    assert _urls(route.calls[0].request) == expected_urls
    assert factory_calls == []
    reruns = await _list_reruns(db_session, seed.eval_uid)
    assert reruns[0].status == "success"


# --- (4) best-effort:下載失敗 → 該 part 剔除,重跑照常完成 ----------------------


@respx.mock(base_url=_OR_BASE_URL)
async def test_download_failure_drops_part_and_rerun_still_completes(
    respx_mock, db_session: AsyncSession, monkeypatch, caplog
) -> None:
    stub = _StubS3(
        {IMAGE_KEY_2: (IMAGE_BYTES, "image/png")}, fail_keys=frozenset({IMAGE_KEY})
    )
    _patch(monkeypatch, stub=stub, s3_enabled=True)
    challenger = _uniq("anthropic/claude-haiku")
    seed = await _seed(
        db_session,
        recommends=[challenger, None, None],
        extra_models=[challenger],
        request_content=_messages_snapshot(PART_S3, PART_S3_2),
    )

    route = respx_mock.post("/chat/completions").mock(
        side_effect=lambda req: _challenger_response("ok", cost=0.001, total_tokens=30)
    )

    client = _make_client()
    with caplog.at_level(logging.WARNING, logger="app.services.ai_model_eval_rerun"):
        await svc.rerun_evaluation(seed.eval_uid, db=db_session, client=client)
    await client._client.aclose()

    # 失敗的那張維持物件 key → 被 replay_messages 自然剔除;成功的那張照常 inline。
    urls = _urls(route.calls[0].request)
    assert len(urls) == 1
    assert base64.b64decode(urls[0].split(",", 1)[1]) == IMAGE_BYTES
    assert IMAGE_KEY not in json.dumps(json.loads(route.calls[0].request.content))

    # 有 warning,且 log 不含 AWS 憑證 / 簽章。
    assert "附件下載失敗" in caplog.text
    assert "S3TimeoutError" in caplog.text
    for token in ("AKIA", "X-Amz-Signature", "aws_secret", "Bearer "):
        assert token not in caplog.text

    # 重跑照常完成。
    reruns = await _list_reruns(db_session, seed.eval_uid)
    assert len(reruns) == 1
    assert reruns[0].status == "success"


@respx.mock(base_url=_OR_BASE_URL)
async def test_missing_object_drops_part_without_blocking_rerun(
    respx_mock, db_session: AsyncSession, monkeypatch
) -> None:
    """物件不存在(遷移遺漏 / 已清除)→ 該 part 剔除,重跑仍完成。"""
    stub = _StubS3({})
    _patch(monkeypatch, stub=stub, s3_enabled=True)
    challenger = _uniq("anthropic/claude-haiku")
    seed = await _seed(
        db_session,
        recommends=[challenger, None, None],
        extra_models=[challenger],
        request_content=_messages_snapshot(PART_S3),
    )

    route = respx_mock.post("/chat/completions").mock(
        side_effect=lambda req: _challenger_response("ok", cost=0.001, total_tokens=30)
    )

    client = _make_client()
    await svc.rerun_evaluation(seed.eval_uid, db=db_session, client=client)
    await client._client.aclose()

    assert stub.get_calls == [IMAGE_KEY]
    assert _urls(route.calls[0].request) == []
    # 文字仍在:整段對話沒有被連坐丟掉。
    body = json.loads(route.calls[0].request.content)
    assert any(TEXT in json.dumps(m, ensure_ascii=False) for m in body["messages"])
    reruns = await _list_reruns(db_session, seed.eval_uid)
    assert reruns[0].status == "success"


# --- (5) 總開關關閉 → 完全不呼叫 S3 -------------------------------------------


@respx.mock(base_url=_OR_BASE_URL)
async def test_storage_disabled_never_calls_s3(
    respx_mock, db_session: AsyncSession, monkeypatch
) -> None:
    stub = _StubS3({IMAGE_KEY: (IMAGE_BYTES, "image/png")})
    factory_calls = _patch(monkeypatch, stub=stub, s3_enabled=False)
    challenger = _uniq("anthropic/claude-haiku")
    seed = await _seed(
        db_session,
        recommends=[challenger, None, None],
        extra_models=[challenger],
        request_content=_messages_snapshot(PART_S3),
    )

    route = respx_mock.post("/chat/completions").mock(
        side_effect=lambda req: _challenger_response("ok", cost=0.001, total_tokens=30)
    )

    client = _make_client()
    await svc.rerun_evaluation(seed.eval_uid, db=db_session, client=client)
    await client._client.aclose()

    assert factory_calls == []
    assert stub.get_calls == []
    # 行為同現況:物件 key 送不出去 → 被剔除,重跑照常完成。
    assert _urls(route.calls[0].request) == []
    reruns = await _list_reruns(db_session, seed.eval_uid)
    assert reruns[0].status == "success"


# --- (6) 回歸:單輪模式行為未變(仍不重放圖片)---------------------------------


@respx.mock(base_url=_OR_BASE_URL)
async def test_single_turn_snapshot_still_does_not_replay_images(
    respx_mock, db_session: AsyncSession, monkeypatch
) -> None:
    """單輪模式自 v2.1.1 起只重放 `text`;本 task 是「恢復」不是「擴大」,不得順手改。"""
    factory_calls = _patch(monkeypatch)
    challenger = _uniq("anthropic/claude-haiku")
    seed = await _seed(
        db_session,
        recommends=[challenger, None, None],
        extra_models=[challenger],
        request_content={"model": "openai/gpt-4o", "text": TEXT, "images": [IMAGE_KEY]},
    )

    route = respx_mock.post("/chat/completions").mock(
        side_effect=lambda req: _challenger_response("ok", cost=0.001, total_tokens=30)
    )

    client = _make_client()
    await svc.rerun_evaluation(seed.eval_uid, db=db_session, client=client)
    await client._client.aclose()

    body = json.loads(route.calls[0].request.content)
    assert body["messages"] == [{"role": "user", "content": TEXT}]
    assert factory_calls == []


# --- (7) mime 推導:S3 的 Content-Type 缺漏 / 非白名單 → octet-stream ----------


@pytest.mark.parametrize(
    ("content_type", "expected_mime"),
    [
        ("image/jpeg", "image/jpeg"),
        ("image/png; charset=binary", "image/png"),
        ("", "application/octet-stream"),
        ("image/svg+xml", "application/octet-stream"),
    ],
    ids=["jpeg", "with_params", "missing", "not_whitelisted"],
)
@respx.mock(base_url=_OR_BASE_URL)
async def test_mime_comes_from_object_metadata_via_whitelist(
    respx_mock,
    db_session: AsyncSession,
    monkeypatch,
    content_type: str,
    expected_mime: str,
) -> None:
    """mime 取 S3 物件 metadata,再過 `attachment.content_type_for_mime` 收斂(不自備對照表)。"""
    stub = _StubS3({IMAGE_KEY: (IMAGE_BYTES, content_type)})
    _patch(monkeypatch, stub=stub, s3_enabled=True)
    challenger = _uniq("anthropic/claude-haiku")
    seed = await _seed(
        db_session,
        recommends=[challenger, None, None],
        extra_models=[challenger],
        request_content=_messages_snapshot(PART_S3),
    )

    route = respx_mock.post("/chat/completions").mock(
        side_effect=lambda req: _challenger_response("ok", cost=0.001, total_tokens=30)
    )

    client = _make_client()
    await svc.rerun_evaluation(seed.eval_uid, db=db_session, client=client)
    await client._client.aclose()

    assert _urls(route.calls[0].request)[0].startswith(f"data:{expected_mime};base64,")
