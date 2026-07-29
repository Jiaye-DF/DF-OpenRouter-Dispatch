"""proxy 附件落地接線測試(v2.2.1 / task-525)。

守住本 task 的四條判準(propose v2.2.1 §D.3 / §D.4 / §D.5):

1. **快照只留路徑**:`usage_logs.request_content` 內的附件為 S3 物件 key
   (`files` 為 `filename` + key,**推翻** v2.1.2「僅記檔名」),不含 `data:` base64。
2. **下游 payload 零變更**:以 `respx` 攔截真實 HTTP 請求,斷言開關開 / 關兩次送出的
   body **逐欄相同** —— `image_url.url` 仍是 base64、`file_data` 照舊存在。
   `_rewrite_request` 本版零 diff,本檔是它的行為證明。
3. **best-effort**:S3 掛掉不擋請求 —— 下游照常被呼叫、回應照常成功、`usage_logs`
   照常寫入,附件記 `upload_failed` 標記。
4. **零 base64 硬規則**:`file_data` 的 base64 任何情況下不得進 `request_content`。

兩條路徑(`run_chat` / `run_chat_stream`)各自成對驗證;漏一條 → 串流請求仍寫
base64,遷移完又會長回來。全程 stub S3、respx 攔 HTTP,**不打真 AWS / 真 OpenRouter**。
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import httpx
import pytest
import respx

from app.clients.factory import ChatClientFactory
from app.clients.openrouter.client import OpenRouterClient
from app.clients.s3 import S3UploadError
from app.schemas.model import ChatMessage
from app.services import attachment as attachment_svc
from app.services import proxy
from app.services.attachment import build_object_key

MODEL = "openai/gpt-4o-mini"
_OR_BASE = "https://openrouter.test/api/v1"
_KEY_PREFIX = "test"
_TW_TZ = ZoneInfo("Asia/Taipei")

_PNG_BYTES = b"\x89PNG\r\n\x1a\n-fake-image-bytes"
_PNG_URI = "data:image/png;base64," + base64.b64encode(_PNG_BYTES).decode()
_PDF_BYTES = b"%PDF-1.7\n-fake-pdf-bytes"
_PDF_URI = "data:application/pdf;base64," + base64.b64encode(_PDF_BYTES).decode()
_REMOTE_URL = "https://example.com/remote.png"

OPENROUTER_RESPONSE = {
    "id": "gen-test-123",
    "model": MODEL,
    "choices": [{"message": {"role": "assistant", "content": "模型回覆內容"}}],
    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, "cost": 0.001},
}

_SSE_BODY = (
    'data: {"id":"gen-test-123","choices":[{"delta":{"content":"哈"}}]}\n'
    "\n"
    'data: {"id":"gen-test-123","choices":[{"delta":{"content":"囉"}}]}\n'
    "\n"
    "data: [DONE]\n"
    "\n"
).encode()


# --- 替身 ---------------------------------------------------------------


@dataclass
class _FakeSettings:
    """只承接 `attachment.build_attachment_snapshot` 會讀的兩顆設定。"""

    S3_STORAGE_ENABLED: bool = True
    S3_KEY_PREFIX: str = _KEY_PREFIX


class _StubS3:
    """記錄 `put_object` 的 S3 替身;`fail_all=True` 模擬 S3 全面不可用。"""

    def __init__(self, *, fail_all: bool = False) -> None:
        self.calls: list[tuple[str, bytes, str]] = []
        self._fail_all = fail_all

    async def put_object(self, key: str, body: bytes, content_type: str) -> None:
        self.calls.append((key, body, content_type))
        if self._fail_all:
            raise S3UploadError("S3 put_object 失敗:AccessDenied")


class _FakeResult:
    def __init__(self, row: object) -> None:
        self._row = row

    def scalar_one_or_none(self) -> object:
        return self._row


class _FakeDb:
    """假 AsyncSession:只需承接 `_check_model_whitelist` 的 execute。"""

    def __init__(self, model_row: object) -> None:
        self._model_row = model_row

    async def execute(self, stmt: object) -> _FakeResult:
        return _FakeResult(self._model_row)


def _make_key_repo_cls(key_row: SimpleNamespace) -> type:
    class _FakeKeyRepo:
        def __init__(self, db: object) -> None:
            self.db = db

        async def list_active_by_department(self, department_uid: object) -> list[SimpleNamespace]:
            return [key_row]

    return _FakeKeyRepo


# --- 開關切換 -----------------------------------------------------------


def _enable_s3(monkeypatch: pytest.MonkeyPatch, stub: _StubS3 | None) -> None:
    monkeypatch.setattr(attachment_svc, "get_settings", lambda: _FakeSettings())

    def _get_client() -> _StubS3:
        if stub is None:
            # 開關已開卻取不到 client(bucket 未設 / 憑證缺):§D.5 要求全記
            # upload_failed,而非降級寫回 base64。
            raise S3UploadError("S3_BUCKET 未設定")
        return stub

    monkeypatch.setattr(attachment_svc, "get_s3_client", _get_client)


def _disable_s3(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        attachment_svc, "get_settings", lambda: _FakeSettings(S3_STORAGE_ENABLED=False)
    )

    def _boom() -> None:
        raise AssertionError("S3_STORAGE_ENABLED=false 不應取得 S3 client")

    monkeypatch.setattr(attachment_svc, "get_s3_client", _boom)


# --- world fixture ------------------------------------------------------


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    model_row = SimpleNamespace(provider="openrouter", model_uid=uuid4(), model_key=MODEL)
    key_row = SimpleNamespace(
        openrouter_key_uid=uuid4(),  # 每測試新 uid,避免共用 in-memory limiter 狀態
        rpm_limit=0,  # 0 = 不限
        min_request_interval_ms=0,
    )
    usage_logs: list[dict[str, Any]] = []

    monkeypatch.setattr(proxy, "OpenRouterKeyRepository", _make_key_repo_cls(key_row))
    monkeypatch.setattr(proxy, "decrypt_key", lambda row: "sk-or-test")
    monkeypatch.setattr(proxy, "schedule_usage_log", lambda **kw: usage_logs.append(kw))

    caller = {
        "department_uid": uuid4(),
        "project_uid": uuid4(),
        "user_uid": uuid4(),
    }
    return SimpleNamespace(
        db=_FakeDb(model_row),
        caller=caller,
        usage_logs=usage_logs,
        model_row=model_row,
    )


def _chat_kwargs(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {"model": MODEL, "text": None, "images": None, "videos": None}
    base.update(overrides)
    return base


async def _call(world: SimpleNamespace, *, stream: bool = False, **chat_kwargs: Any) -> Any:
    """跑一次代理(真 httpx + respx 攔截),回傳輸出 / 下游 body / 記帳參數。"""
    response = (
        httpx.Response(200, content=_SSE_BODY)
        if stream
        else httpx.Response(200, json=OPENROUTER_RESPONSE)
    )
    with respx.mock(base_url=_OR_BASE, assert_all_called=False) as router:
        route = router.post("/chat/completions").mock(return_value=response)
        async with httpx.AsyncClient() as http:
            factory = ChatClientFactory(
                openrouter=OpenRouterClient(http, _OR_BASE), internal_httpx=http
            )
            kwargs = {**world.caller, **_chat_kwargs(**chat_kwargs)}
            if stream:
                chunks = [
                    chunk
                    async for chunk in proxy.run_chat_stream(
                        world.db, client_factory=factory, **kwargs
                    )
                ]
                output = "".join(chunks)
            else:
                output = await proxy.run_chat(world.db, client_factory=factory, **kwargs)
        payloads = [json.loads(call.request.content) for call in route.calls]
    return SimpleNamespace(
        output=output,
        payloads=payloads,
        called=bool(route.calls),
        log=world.usage_logs[-1] if world.usage_logs else None,
        logs=world.usage_logs,
    )


def _request_log(outcome: Any) -> dict[str, Any]:
    assert outcome.log is not None, "usage_logs 必須有寫入"
    return dict(outcome.log["request_log"])


def _expected_key(outcome: Any, *, index: int, content: bytes, mime: str) -> str:
    """用落地層公開的純函式重算 key —— 同時驗證 request_uid 就是那筆 usage_log 的 uid。

    這條「重算得同一把 key」的性質正是 530 / 531 兩階段遷移的地基,故在接線層也守一次。
    """
    return build_object_key(
        scope="chat",
        owner_uid=str(outcome.log["usage_log_uid"]),
        index=index,
        content=content,
        mime=mime,
        key_prefix=_KEY_PREFIX,
        occurred_at=datetime.now(_TW_TZ),
    )


# ---------------------------------------------------------------------------
# 1. 單輪模式:images 快照為 S3 路徑,不含 data URI
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("stream", [False, True], ids=["run_chat", "run_chat_stream"])
async def test_single_turn_images_snapshot_is_s3_path(
    world: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, stream: bool
) -> None:
    stub = _StubS3()
    _enable_s3(monkeypatch, stub)

    outcome = await _call(world, stream=stream, text="hello", images=[_PNG_URI, _REMOTE_URL])

    log = _request_log(outcome)
    key = log["images"][0]
    assert isinstance(key, str)
    assert key == _expected_key(outcome, index=0, content=_PNG_BYTES, mime="image/png")
    assert key.startswith(f"{_KEY_PREFIX}/chat/")
    assert "data:" not in json.dumps(log["images"], ensure_ascii=False)
    # 遠端 URL 原樣保留、不代抓(§D.2)。
    assert log["images"][1] == _REMOTE_URL
    assert [body for _, body, _ in stub.calls] == [_PNG_BYTES]
    # text 與其餘快照欄位不受影響。
    assert log["text"] == "hello"
    assert log["model"] == MODEL


# ---------------------------------------------------------------------------
# 2. messages 模式:image_url part 的 url 改存 S3 路徑
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("stream", [False, True], ids=["run_chat", "run_chat_stream"])
async def test_messages_mode_image_url_snapshot_is_s3_path(
    world: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, stream: bool
) -> None:
    stub = _StubS3()
    _enable_s3(monkeypatch, stub)
    messages = [
        ChatMessage.model_validate(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "看一下這張圖"},
                    {"type": "image_url", "image_url": {"url": _PNG_URI}},
                ],
            }
        )
    ]

    outcome = await _call(world, stream=stream, messages=messages)

    log = _request_log(outcome)
    parts = log["messages"][0]["content"]
    assert parts[0] == {"type": "text", "text": "看一下這張圖"}
    assert parts[1] == {
        "type": "image_url",
        "image_url": {"url": _expected_key(outcome, index=0, content=_PNG_BYTES, mime="image/png")},
    }
    assert "data:" not in json.dumps(log, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 3. files 快照:filename + 路徑(推翻 v2.1.2「僅記檔名」,§D.3)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("stream", [False, True], ids=["run_chat", "run_chat_stream"])
async def test_files_snapshot_has_filename_and_key(
    world: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, stream: bool
) -> None:
    stub = _StubS3()
    _enable_s3(monkeypatch, stub)

    outcome = await _call(
        world,
        stream=stream,
        files=[{"filename": "報告.pdf", "file_data": _PDF_URI}],
    )

    log = _request_log(outcome)
    assert log["files"] == [
        {
            "type": "file",
            "file": {
                "filename": "報告.pdf",
                "key": _expected_key(outcome, index=0, content=_PDF_BYTES, mime="application/pdf"),
            },
        }
    ]
    # 實體確實上傳、且送的是解碼後 bytes + 白名單推導的 Content-Type。
    assert stub.calls == [(log["files"][0]["file"]["key"], _PDF_BYTES, "application/pdf")]


@pytest.mark.parametrize("stream", [False, True], ids=["run_chat", "run_chat_stream"])
async def test_messages_mode_file_part_has_filename_and_key(
    world: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, stream: bool
) -> None:
    stub = _StubS3()
    _enable_s3(monkeypatch, stub)
    messages = [
        ChatMessage.model_validate(
            {
                "role": "user",
                "content": [
                    {"type": "file", "file": {"filename": "report.pdf", "file_data": _PDF_URI}}
                ],
            }
        )
    ]

    outcome = await _call(world, stream=stream, messages=messages)

    log = _request_log(outcome)
    assert log["messages"][0]["content"][0] == {
        "type": "file",
        "file": {
            "filename": "report.pdf",
            "key": _expected_key(outcome, index=0, content=_PDF_BYTES, mime="application/pdf"),
        },
    }


# ---------------------------------------------------------------------------
# 4. best-effort:S3 失敗不擋請求(§D.5)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("stream", [False, True], ids=["run_chat", "run_chat_stream"])
@pytest.mark.parametrize(
    "unavailable", [False, True], ids=["put_object_failed", "client_unavailable"]
)
async def test_s3_failure_does_not_block_request(
    world: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, stream: bool, unavailable: bool
) -> None:
    """S3 掛掉 / 逾時:200 照常、下游照常被呼叫、usage_logs 照常寫入。"""
    stub = None if unavailable else _StubS3(fail_all=True)
    _enable_s3(monkeypatch, stub)

    outcome = await _call(
        world,
        stream=stream,
        text="hello",
        images=[_PNG_URI],
        files=[{"filename": "報告.pdf", "file_data": _PDF_URI}],
    )

    # 對外行為與 v2.2.0 完全一致 —— 無新增 5xx 情境。
    if stream:
        assert '"content": "哈"' in outcome.output
        assert outcome.output.endswith("data: [DONE]\n\n")
    else:
        assert outcome.output == "模型回覆內容"
    # 下游仍被呼叫。
    assert outcome.called is True
    # usage_logs 仍寫入,且狀態為 success。
    assert len(outcome.logs) == 1
    assert outcome.log["status"] == "success"
    assert outcome.log["error_code"] is None

    log = _request_log(outcome)
    assert log["images"][0] == {
        "type": "image_url",
        "upload_failed": True,
        "mime": "image/png",
        "bytes": len(_PNG_BYTES),
        "sha256": hashlib.sha256(_PNG_BYTES).hexdigest(),
        "reason": "s3_upload_failed" if not unavailable else "s3_unavailable",
    }
    marker = log["files"][0]["file"]
    assert marker["filename"] == "報告.pdf"
    assert marker["upload_failed"] is True
    assert marker["sha256"] == hashlib.sha256(_PDF_BYTES).hexdigest()


# ---------------------------------------------------------------------------
# 5. 開關關閉:快照與 v2.2.0 完全一致
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("stream", [False, True], ids=["run_chat", "run_chat_stream"])
async def test_disabled_switch_snapshot_identical_to_v2_2_0(
    world: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, stream: bool
) -> None:
    _disable_s3(monkeypatch)
    tools = [{"type": "openrouter:web_search"}]

    outcome = await _call(
        world,
        stream=stream,
        text="hello",
        images=[_PNG_URI],
        tools=tools,
        files=[{"filename": "report.pdf", "file_data": _PDF_URI}],
    )

    log = _request_log(outcome)
    expected = {
        "model": MODEL,
        "text": "hello",
        "images": [_PNG_URI],
        "tools": tools,
        "files": ["report.pdf"],  # v2.2.0:僅記檔名
    }
    # 鍵序亦不變(v2.2.0 位元級一致)。
    assert json.dumps(log, ensure_ascii=False) == json.dumps(expected, ensure_ascii=False)


async def test_disabled_switch_messages_snapshot_identical_to_v2_2_0(
    world: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    _disable_s3(monkeypatch)
    messages = [
        ChatMessage.model_validate(
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": _PNG_URI}},
                    {"type": "file", "file": {"filename": "report.pdf", "file_data": _PDF_URI}},
                ],
            }
        )
    ]

    outcome = await _call(world, messages=messages)

    log = _request_log(outcome)
    assert log["messages"][0]["content"] == [
        {"type": "image_url", "image_url": {"url": _PNG_URI}},  # v2.2.0:base64 原樣
        {"type": "file", "file": {"filename": "report.pdf"}},  # v2.2.0:僅檔名
    ]


# ---------------------------------------------------------------------------
# 6. 下游 payload 零變更(必測):respx 攔截,開 / 關逐欄相同
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("stream", [False, True], ids=["run_chat", "run_chat_stream"])
async def test_downstream_payload_identical_with_switch_on_and_off(
    world: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, stream: bool
) -> None:
    """S3 開關不得改變送往 OpenRouter 的 body 一個 byte(§D.4,`_rewrite_request` 零 diff)。"""
    body = {
        "text": "hello",
        "images": [_PNG_URI, _REMOTE_URL],
        "files": [{"filename": "報告.pdf", "file_data": _PDF_URI}],
        "tools": [{"type": "openrouter:web_search"}],
        "temperature": 0.7,
        "max_tokens": 256,
    }

    _disable_s3(monkeypatch)
    off = await _call(world, stream=stream, **body)

    _enable_s3(monkeypatch, _StubS3())
    on = await _call(world, stream=stream, **body)

    assert off.payloads and on.payloads
    assert json.dumps(on.payloads[0], ensure_ascii=False, sort_keys=True) == json.dumps(
        off.payloads[0], ensure_ascii=False, sort_keys=True
    )

    # 逐欄再點名一次:下游拿到的仍是 base64 / 原始 URL,file_data 照舊存在。
    content = on.payloads[0]["messages"][0]["content"]
    assert content[1] == {"type": "image_url", "image_url": {"url": _PNG_URI}}
    assert content[2] == {"type": "image_url", "image_url": {"url": _REMOTE_URL}}
    assert content[3] == {
        "type": "file",
        "file": {"filename": "報告.pdf", "file_data": _PDF_URI},
    }
    assert ";base64," in json.dumps(on.payloads[0], ensure_ascii=False)


@pytest.mark.parametrize("stream", [False, True], ids=["run_chat", "run_chat_stream"])
async def test_downstream_payload_identical_in_messages_mode(
    world: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, stream: bool
) -> None:
    raw = {
        "role": "user",
        "content": [
            {"type": "text", "text": "看圖與檔案"},
            {"type": "image_url", "image_url": {"url": _PNG_URI}},
            {"type": "file", "file": {"filename": "report.pdf", "file_data": _PDF_URI}},
        ],
    }

    _disable_s3(monkeypatch)
    off = await _call(world, stream=stream, messages=[ChatMessage.model_validate(raw)])

    _enable_s3(monkeypatch, _StubS3())
    on = await _call(world, stream=stream, messages=[ChatMessage.model_validate(raw)])

    assert on.payloads[0] == off.payloads[0]
    assert on.payloads[0]["messages"][0] == raw  # 原樣透傳,含 file_data


@pytest.mark.parametrize("stream", [False, True], ids=["run_chat", "run_chat_stream"])
async def test_downstream_payload_unchanged_when_s3_fails(
    world: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, stream: bool
) -> None:
    """S3 失敗同樣不得影響下游 payload —— 記帳層無權改動要送出的東西。"""
    body = {
        "text": "hello",
        "images": [_PNG_URI],
        "files": [{"filename": "report.pdf", "file_data": _PDF_URI}],
    }

    _disable_s3(monkeypatch)
    off = await _call(world, stream=stream, **body)

    _enable_s3(monkeypatch, _StubS3(fail_all=True))
    failed = await _call(world, stream=stream, **body)

    assert failed.payloads[0] == off.payloads[0]


# ---------------------------------------------------------------------------
# 7. 快照零 base64 回歸(硬規則:file_data 任何情況下不入 request_content)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("stream", [False, True], ids=["run_chat", "run_chat_stream"])
@pytest.mark.parametrize(
    "path",
    ["upload_ok", "upload_failed", "s3_unavailable"],
)
async def test_snapshot_never_contains_base64_when_enabled(
    world: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, stream: bool, path: str
) -> None:
    stub = {
        "upload_ok": _StubS3(),
        "upload_failed": _StubS3(fail_all=True),
        "s3_unavailable": None,
    }[path]
    _enable_s3(monkeypatch, stub)

    outcome = await _call(
        world,
        stream=stream,
        text="hello",
        images=[_PNG_URI],
        files=[{"filename": "報告.pdf", "file_data": _PDF_URI}],
    )

    dumped = json.dumps(_request_log(outcome), ensure_ascii=False)
    assert "file_data" not in dumped
    assert ";base64," not in dumped
    assert "data:" not in dumped


@pytest.mark.parametrize("stream", [False, True], ids=["run_chat", "run_chat_stream"])
async def test_snapshot_never_contains_file_data_when_disabled(
    world: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, stream: bool
) -> None:
    """開關關閉時 images 仍是 base64(v2.2.0 行為),但 `file_data` 一樣不得入庫。"""
    _disable_s3(monkeypatch)

    outcome = await _call(
        world,
        stream=stream,
        files=[{"filename": "報告.pdf", "file_data": _PDF_URI}],
        messages=None,
    )

    assert "file_data" not in json.dumps(_request_log(outcome), ensure_ascii=False)


# ---------------------------------------------------------------------------
# 8. request_uid = usage_log_uid:S3 key 可反查回那筆紀錄
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("stream", [False, True], ids=["run_chat", "run_chat_stream"])
async def test_attachment_key_owner_is_the_usage_log_uid(
    world: SimpleNamespace, monkeypatch: pytest.MonkeyPatch, stream: bool
) -> None:
    """附件 key 的擁有者層級必須就是該筆 usage_log 的主鍵(否則物件對不回紀錄)。"""
    stub = _StubS3()
    _enable_s3(monkeypatch, stub)

    outcome = await _call(world, stream=stream, images=[_PNG_URI])

    usage_log_uid = outcome.log["usage_log_uid"]
    assert isinstance(usage_log_uid, UUID)
    assert f"/{usage_log_uid}/" in stub.calls[0][0]
    assert _request_log(outcome)["images"][0] == stub.calls[0][0]


async def test_each_request_gets_its_own_uid(
    world: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    stub = _StubS3()
    _enable_s3(monkeypatch, stub)

    await _call(world, images=[_PNG_URI])
    await _call(world, images=[_PNG_URI])

    uids = [log["usage_log_uid"] for log in world.usage_logs]
    assert len(uids) == 2
    assert uids[0] != uids[1]
    # 內容相同但 owner 不同 → key 不同,兩次上傳不互相覆蓋。
    assert stub.calls[0][0] != stub.calls[1][0]
