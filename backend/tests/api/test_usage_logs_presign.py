"""用量明細 API 回吐 presigned URL 測試(task-527)。

全程以 stub 取代 S3,**不打真 AWS**、不需要 AWS 憑證(`09-object-storage.md` § 測試),
斷言只看「有 TTL 參數 + 指向正確 key」,不斷言完整簽章字串。

沿用 tests/api/test_usage_logs.py 的 mock 風格(FastAPI app + ASGITransport +
dependency_overrides + monkeypatch UsageLogRepository)。守住四件事:

1. 四種附件形態各自正確(object_key 換 URL;data URI / 遠端 URL / upload_failed 原樣)。
2. presign 失敗 → **仍回 200**,該附件退回原樣值 + log warning。
3. `S3_STORAGE_ENABLED=false` → 一次 S3 都不碰。
4. messages 模式與單輪模式兩種快照形狀皆處理。
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

import app.api.v1.usage_logs as usage_logs
from app.clients.s3 import S3ConfigError, S3Error, S3TimeoutError
from app.core.database import get_db
from app.core.deps import require_user
from app.main import create_app
from app.schemas.actor import Actor

pytestmark = pytest.mark.asyncio

_KEY = "test/chat/2026/07/29/req-1/0-abcdef0123456789.png"
_KEY2 = "test/chat/2026/07/29/req-1/1-fedcba9876543210.pdf"
_PNG_URI = "data:image/png;base64," + base64.b64encode(b"\x89PNG-fake").decode()
_REMOTE = "https://example.com/cat.png"
_TTL = 900

# repo 回傳列:(UsageLog-like, project_code, project_name)
_Row = tuple[object, str | None, str | None]


# --- 替身 ---------------------------------------------------------------


@dataclass
class _FakeSettings:
    S3_STORAGE_ENABLED: bool = True
    S3_PRESIGN_TTL_SECONDS: int = _TTL


class _StubS3:
    """記錄 `presign_get` 呼叫的 S3 替身;可指定拋錯。"""

    def __init__(self, *, error: Exception | None = None) -> None:
        self.calls: list[tuple[str, int]] = []
        self._error = error

    async def presign_get(self, key: str, ttl: int) -> str:
        self.calls.append((key, ttl))
        if self._error is not None:
            raise self._error
        # 形狀比照 boto3 SigV4 presigned URL(僅測試用,非真簽章)。
        return (
            f"https://bucket.s3.ap-northeast-1.amazonaws.com/{key}"
            f"?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Expires={ttl}"
            "&X-Amz-Signature=stubsignature0123456789"
        )


class _FakeRepo:
    detail_row: _Row | None = None
    list_rows: list[_Row] = []
    list_total: int = 0

    def __init__(self, db: object) -> None:
        self.db = db

    async def list(self, **kwargs: object) -> tuple[list[_Row], int]:
        return type(self).list_rows, type(self).list_total

    async def get_by_uid_with_project(self, uid: UUID) -> _Row | None:
        return type(self).detail_row


class _FakeDb:
    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None

    def add(self, row: object) -> None:
        return None


def _admin() -> Actor:
    return Actor(user_uid=uuid4(), account="admin", username="管理員", role="admin")


def _fake_log(request_content: dict[str, Any] | None) -> SimpleNamespace:
    return SimpleNamespace(
        pid=1,
        usage_log_uid=uuid4(),
        user_uid=uuid4(),
        department_uid=uuid4(),
        project_uid=None,
        openrouter_key_uid=None,
        model="openai/gpt-4o",
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        cost_usd=Decimal("0.001500"),
        latency_ms=123,
        status="success",
        error_code=None,
        used_tools=False,
        openrouter_generation_id=None,
        created_at=datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC),
        request_content=request_content,
        response_summary={"text": "ok"},
    )


def _make_client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    detail_row: _Row | None = None,
    list_rows: list[_Row] | None = None,
) -> AsyncClient:
    _FakeRepo.detail_row = detail_row
    _FakeRepo.list_rows = list_rows or []
    _FakeRepo.list_total = len(list_rows or [])
    monkeypatch.setattr(usage_logs, "UsageLogRepository", _FakeRepo)

    app = create_app()

    async def _fake_get_db():  # type: ignore[no-untyped-def]
        yield _FakeDb()

    app.dependency_overrides[get_db] = _fake_get_db
    app.dependency_overrides[require_user] = _admin
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _use_s3(
    monkeypatch: pytest.MonkeyPatch,
    *,
    enabled: bool = True,
    error: Exception | None = None,
    ttl: int = _TTL,
) -> _StubS3:
    stub = _StubS3(error=error)
    monkeypatch.setattr(
        usage_logs,
        "get_settings",
        lambda: _FakeSettings(S3_STORAGE_ENABLED=enabled, S3_PRESIGN_TTL_SECONDS=ttl),
    )
    monkeypatch.setattr(usage_logs, "get_s3_client", lambda: stub)
    return stub


def _no_s3(monkeypatch: pytest.MonkeyPatch, *, enabled: bool = False) -> None:
    """確保該路徑真的完全不碰 S3 —— 一旦取 client 就直接炸測試。"""

    def _boom() -> object:
        raise AssertionError("此路徑不應取得 S3 client")

    monkeypatch.setattr(
        usage_logs, "get_settings", lambda: _FakeSettings(S3_STORAGE_ENABLED=enabled)
    )
    monkeypatch.setattr(usage_logs, "get_s3_client", _boom)


async def _detail(
    monkeypatch: pytest.MonkeyPatch, request_content: dict[str, Any] | None
) -> dict[str, Any]:
    row = (_fake_log(request_content), "PRJ-A", "專案A")
    async with _make_client(monkeypatch, detail_row=row) as client:
        resp = await client.get(f"/api/v1/usage-logs/{uuid4()}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # response 殼:ApiResponse { success, code, data, detail }
    assert body["success"] is True
    assert body["code"] == 200
    assert body["detail"] == "success"
    return body["data"]["request_content"]


def _assert_presigned(url: object, key: str) -> None:
    assert isinstance(url, str)
    assert url.startswith("https://")
    parsed = urlparse(url)
    assert parsed.path.lstrip("/") == key
    query = parse_qs(parsed.query)
    assert query["X-Amz-Signature"]
    assert query["X-Amz-Expires"] == [str(_TTL)]


# --- 1. 單輪模式:四種形態 ------------------------------------------------


async def test_single_turn_object_key_becomes_presigned_url(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = _use_s3(monkeypatch)
    content = await _detail(monkeypatch, {"model": "m", "text": "hi", "images": [_KEY], "files": []})
    _assert_presigned(content["images"][0], _KEY)
    assert stub.calls == [(_KEY, _TTL)]
    # 其餘欄位不受影響
    assert content["text"] == "hi"
    assert content["model"] == "m"


async def test_single_turn_data_uri_returned_as_is(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = _use_s3(monkeypatch)
    content = await _detail(monkeypatch, {"model": "m", "text": "", "images": [_PNG_URI]})
    # 遷移期新舊並存:舊 data URI 一個 byte 都不改,前端既有渲染路徑保底。
    assert content["images"] == [_PNG_URI]
    assert stub.calls == []


async def test_single_turn_remote_url_returned_as_is(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = _use_s3(monkeypatch)
    content = await _detail(monkeypatch, {"model": "m", "images": [_REMOTE]})
    assert content["images"] == [_REMOTE]
    assert stub.calls == []


async def test_single_turn_upload_failed_marker_returned_as_is(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = _use_s3(monkeypatch)
    marker = {
        "type": "image_url",
        "upload_failed": True,
        "mime": "image/png",
        "bytes": 12,
        "sha256": "deadbeef",
        "reason": "s3_upload_failed",
    }
    file_marker = {
        "type": "file",
        "file": {
            "filename": "報表.pdf",
            "upload_failed": True,
            "mime": "application/pdf",
            "bytes": 34,
            "sha256": "cafebabe",
            "reason": "s3_upload_failed",
        },
    }
    content = await _detail(
        monkeypatch, {"model": "m", "images": [marker], "files": [file_marker]}
    )
    # 前端據失敗標記顯示「內容未留存」;濾掉或改寫都會複製 v2.1.2 的靜默失效。
    assert content["images"] == [marker]
    assert content["files"] == [file_marker]
    assert stub.calls == []


async def test_single_turn_file_dict_key_becomes_presigned_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = _use_s3(monkeypatch)
    content = await _detail(
        monkeypatch,
        {"model": "m", "images": [], "files": [{"type": "file", "file": {"filename": "a.pdf", "key": _KEY2}}]},
    )
    file_part = content["files"][0]
    _assert_presigned(file_part["file"]["key"], _KEY2)
    # 檔名與 part 型別不得被吃掉
    assert file_part["file"]["filename"] == "a.pdf"
    assert file_part["type"] == "file"
    assert stub.calls == [(_KEY2, _TTL)]


async def test_single_turn_legacy_filename_string_is_not_presigned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = _use_s3(monkeypatch)
    # v2.2.0 單輪 files 只留檔名字串(非物件 key)。presign 只是本地簽章計算、不驗物件存在,
    # 若拿檔名去簽會產生一條看似正常卻指向不存在物件的 URL。
    content = await _detail(monkeypatch, {"model": "m", "images": [], "files": ["報表.pdf"]})
    assert content["files"] == ["報表.pdf"]
    assert stub.calls == []


async def test_single_turn_mixed_forms(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = _use_s3(monkeypatch)
    marker = {"type": "image_url", "upload_failed": True, "reason": "invalid_data_uri"}
    content = await _detail(
        monkeypatch, {"model": "m", "images": [_KEY, _PNG_URI, _REMOTE, marker]}
    )
    _assert_presigned(content["images"][0], _KEY)
    assert content["images"][1] == _PNG_URI
    assert content["images"][2] == _REMOTE
    assert content["images"][3] == marker
    assert stub.calls == [(_KEY, _TTL)]


# --- 2. messages 直傳模式 -------------------------------------------------


async def test_messages_mode_image_and_file_parts(monkeypatch: pytest.MonkeyPatch) -> None:
    stub = _use_s3(monkeypatch)
    content = await _detail(
        monkeypatch,
        {
            "model": "m",
            "messages": [
                {"role": "system", "content": "你是助理"},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "看這張"},
                        {"type": "image_url", "image_url": {"url": _KEY}},
                        {"type": "image_url", "image_url": {"url": _PNG_URI}},
                        {"type": "image_url", "image_url": {"url": _REMOTE}},
                        {"type": "file", "file": {"filename": "a.pdf", "key": _KEY2}},
                        {"type": "file", "file": {"filename": "b.pdf"}},
                    ],
                },
            ],
        },
    )
    # messages 模式沒有 images / files 鍵,不得被憑空補上
    assert "images" not in content
    assert "files" not in content
    assert content["messages"][0] == {"role": "system", "content": "你是助理"}
    parts = content["messages"][1]["content"]
    assert parts[0] == {"type": "text", "text": "看這張"}
    _assert_presigned(parts[1]["image_url"]["url"], _KEY)
    assert parts[2]["image_url"]["url"] == _PNG_URI
    assert parts[3]["image_url"]["url"] == _REMOTE
    _assert_presigned(parts[4]["file"]["key"], _KEY2)
    assert parts[4]["file"]["filename"] == "a.pdf"
    # v2.2.0「只有檔名」的 file 快照無參照可取 → 原樣
    assert parts[5] == {"type": "file", "file": {"filename": "b.pdf"}}
    assert stub.calls == [(_KEY, _TTL), (_KEY2, _TTL)]


async def test_messages_mode_upload_failed_marker_returned_as_is(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = _use_s3(monkeypatch)
    marker = {"type": "image_url", "upload_failed": True, "reason": "s3_upload_failed"}
    content = await _detail(
        monkeypatch, {"model": "m", "messages": [{"role": "user", "content": [marker]}]}
    )
    assert content["messages"][0]["content"] == [marker]
    assert stub.calls == []


# --- 3. best-effort:presign 失敗 -----------------------------------------


async def test_presign_error_still_returns_200_with_original_value(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    stub = _use_s3(monkeypatch, error=S3TimeoutError("presign 逾時", aws_code="RequestTimeout"))
    with caplog.at_level(logging.WARNING, logger="app.api.v1.usage_logs"):
        content = await _detail(monkeypatch, {"model": "m", "images": [_KEY, _KEY2]})
    # 200 已在 _detail 內斷言;附件退回原樣值
    assert content["images"] == [_KEY, _KEY2]
    assert stub.calls == [(_KEY, _TTL), (_KEY2, _TTL)]
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 2
    assert "presign 失敗" in warnings[0].getMessage()
    assert "S3TimeoutError" in warnings[0].getMessage()


async def test_unexpected_presign_exception_still_returns_200(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # 非 S3Error 的未預期例外同樣不得擋掉讀取。
    _use_s3(monkeypatch, error=RuntimeError("boom"))
    with caplog.at_level(logging.WARNING, logger="app.api.v1.usage_logs"):
        content = await _detail(monkeypatch, {"model": "m", "images": [_KEY]})
    assert content["images"] == [_KEY]
    assert any("RuntimeError" in r.getMessage() for r in caplog.records)


async def test_s3_client_unavailable_still_returns_200(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(usage_logs, "get_settings", lambda: _FakeSettings())

    def _boom() -> object:
        raise S3ConfigError("S3_BUCKET 未設定", operation="init", code=500)

    monkeypatch.setattr(usage_logs, "get_s3_client", _boom)
    with caplog.at_level(logging.WARNING, logger="app.api.v1.usage_logs"):
        content = await _detail(monkeypatch, {"model": "m", "images": [_KEY]})
    assert content["images"] == [_KEY]
    assert any("S3 client 取得失敗" in r.getMessage() for r in caplog.records)


async def test_presign_failure_log_leaks_no_credentials(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _use_s3(monkeypatch, error=S3Error("AccessDenied", aws_code="AccessDenied"))
    with caplog.at_level(logging.WARNING, logger="app.api.v1.usage_logs"):
        await _detail(monkeypatch, {"model": "m", "images": [_KEY]})
    text = " ".join(r.getMessage() for r in caplog.records)
    # 敏感欄位過濾表:AWS 憑證與 presigned URL 禁入 log。
    assert "AWS_ACCESS_KEY_ID" not in text
    assert "X-Amz-Signature" not in text
    assert "aws_code=AccessDenied" in text


# --- 4. 開關關閉 / 空內容 -------------------------------------------------


async def test_storage_disabled_never_touches_s3(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_s3(monkeypatch)
    payload = {
        "model": "m",
        "images": [_KEY, _PNG_URI],
        "files": [{"type": "file", "file": {"filename": "a.pdf", "key": _KEY2}}],
    }
    content = await _detail(monkeypatch, payload)
    # 行為與 v2.2.0 逐欄一致
    assert content == payload


async def test_none_request_content_is_untouched(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_s3(monkeypatch, enabled=True)
    assert await _detail(monkeypatch, None) is None


async def test_empty_request_content_is_untouched(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_s3(monkeypatch, enabled=True)
    assert await _detail(monkeypatch, {}) == {}


# --- 5. 列表端點未受影響 --------------------------------------------------


async def test_list_endpoint_has_no_request_content_and_no_presign(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _no_s3(monkeypatch, enabled=True)
    rows: list[_Row] = [(_fake_log({"model": "m", "images": [_KEY]}), "PRJ-A", "專案A")]
    async with _make_client(monkeypatch, list_rows=rows) as client:
        resp = await client.get("/api/v1/usage-logs")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["code"] == 200
    item = body["data"]["items"][0]
    # UsageLogListItem 刻意不含 request_content;本版不得把它加回去。
    assert "request_content" not in item
    assert "response_summary" not in item


# --- 6. Swagger schema 未破壞 ---------------------------------------------


async def test_openapi_detail_endpoint_intact(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_s3(monkeypatch, enabled=True)
    async with _make_client(monkeypatch) as client:
        resp = await client.get("/api/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    assert "/api/v1/usage-logs/{uid}" in paths
    assert paths["/api/v1/usage-logs/{uid}"]["get"]["summary"] == "用量紀錄單筆"
