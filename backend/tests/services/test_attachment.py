"""附件落地層 `app/services/attachment.py` 單元測試(task-524)。

全程以 stub 替身取代 S3,**不打真 AWS**、不需要 AWS 憑證
(`09-object-storage.md` § 測試)。重點守三件事:

1. key 為 deterministic 純函式(530 / 531 靠重算取得同一把 key)。
2. 輸出**永遠不含 base64**,尤其 `file_data`(§D.5 硬規則)。
3. best-effort:任一附件失敗不中斷、不拋例外、有結構化 log。
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from app.clients.s3 import S3TimeoutError, S3UploadError
from app.schemas.model import ChatMessage
from app.services import attachment as svc
from app.services.attachment import (
    AttachmentSnapshot,
    build_attachment_snapshot,
    build_object_key,
    content_type_for_mime,
    extension_for_mime,
    is_remote_url,
    parse_data_uri,
)

_TW_TZ = ZoneInfo("Asia/Taipei")
_AT = datetime(2026, 7, 29, 14, 30, tzinfo=_TW_TZ)
_REQUEST_UID = "01J8ZQK7REQUEST0001"

_PNG_BYTES = b"\x89PNG\r\n\x1a\n-fake-image-bytes"
_PNG_URI = "data:image/png;base64," + base64.b64encode(_PNG_BYTES).decode()
_PNG2_BYTES = b"\x89PNG\r\n\x1a\n-second-image"
_PNG2_URI = "data:image/png;base64," + base64.b64encode(_PNG2_BYTES).decode()
_PNG3_BYTES = b"\x89PNG\r\n\x1a\n-third-image"
_PNG3_URI = "data:image/png;base64," + base64.b64encode(_PNG3_BYTES).decode()
_PDF_BYTES = b"%PDF-1.7\n-fake-pdf-bytes"
_PDF_URI = "data:application/pdf;base64," + base64.b64encode(_PDF_BYTES).decode()


# --- 替身 ---------------------------------------------------------------


@dataclass
class _FakeSettings:
    S3_STORAGE_ENABLED: bool = True
    S3_KEY_PREFIX: str = "test"


class _StubS3:
    """記錄 `put_object` 呼叫的 S3 替身;可指定第 N 次呼叫拋錯。"""

    def __init__(self, *, fail_on: set[int] | None = None, error: Exception | None = None) -> None:
        self.calls: list[tuple[str, bytes, str]] = []
        self._fail_on = fail_on or set()
        self._error = error or S3UploadError("S3 put_object 失敗:AccessDenied")

    async def put_object(self, key: str, body: bytes, content_type: str) -> None:
        index = len(self.calls)
        self.calls.append((key, body, content_type))
        if index in self._fail_on:
            raise self._error


def _use_settings(monkeypatch: pytest.MonkeyPatch, **kwargs: Any) -> None:
    settings = _FakeSettings(**kwargs)
    monkeypatch.setattr(svc, "get_settings", lambda: settings)


def _no_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """確保「開關關閉」路徑真的完全不碰 S3 —— 一旦取 client 就直接炸測試。"""

    def _boom() -> None:
        raise AssertionError("S3_STORAGE_ENABLED=false 不應取得 S3 client")

    monkeypatch.setattr(svc, "get_s3_client", _boom)


def _dump(snapshot: AttachmentSnapshot) -> str:
    return json.dumps(
        {"images": snapshot.images, "files": snapshot.files, "messages": snapshot.messages},
        ensure_ascii=False,
    )


def _messages(*parts: dict[str, Any]) -> list[ChatMessage]:
    return [ChatMessage.model_validate({"role": "user", "content": list(parts)})]


# --- 1. data URI 解析:成功 / 三種畸形值 ---------------------------------


def test_parse_data_uri_success() -> None:
    parsed = parse_data_uri(_PNG_URI)
    assert parsed is not None
    assert parsed.mime == "image/png"
    assert parsed.content == _PNG_BYTES
    assert parsed.size == len(_PNG_BYTES)
    assert parsed.sha256 == hashlib.sha256(_PNG_BYTES).hexdigest()


def test_parse_data_uri_accepts_intermediate_parameters() -> None:
    uri = "data:text/plain;charset=utf-8;base64," + base64.b64encode(b"hi").decode()
    parsed = parse_data_uri(uri)
    assert parsed is not None
    assert parsed.mime == "text/plain"
    assert parsed.content == b"hi"


def test_parse_data_uri_malformed_not_base64() -> None:
    assert parse_data_uri("data:image/png;base64,!!!not-base64!!!") is None


def test_parse_data_uri_malformed_empty_payload() -> None:
    assert parse_data_uri("data:image/png;base64,") is None


def test_parse_data_uri_malformed_missing_mime() -> None:
    assert parse_data_uri("data:;base64,QUJD") is None


def test_parse_data_uri_rejects_plain_and_remote_values() -> None:
    assert parse_data_uri("https://example.com/a.png") is None
    assert parse_data_uri("not-an-attachment") is None


def test_is_remote_url() -> None:
    assert is_remote_url("https://example.com/a.png")
    assert is_remote_url("HTTP://example.com/a.png")
    assert not is_remote_url(_PNG_URI)
    assert not is_remote_url("ftp://example.com/a.png")


# --- 2. key 為 deterministic 純函式 -------------------------------------


def test_build_object_key_is_deterministic() -> None:
    first = build_object_key(
        scope="chat",
        owner_uid=_REQUEST_UID,
        index=0,
        content=_PNG_BYTES,
        mime="image/png",
        key_prefix="test",
        occurred_at=_AT,
    )
    second = build_object_key(
        scope="chat",
        owner_uid=_REQUEST_UID,
        index=0,
        content=_PNG_BYTES,
        mime="image/png",
        key_prefix="test",
        occurred_at=_AT,
    )
    assert first == second


def test_build_object_key_chat_format() -> None:
    digest = hashlib.sha256(_PNG_BYTES).hexdigest()[:16]
    key = build_object_key(
        scope="chat",
        owner_uid=_REQUEST_UID,
        index=2,
        content=_PNG_BYTES,
        mime="image/png",
        key_prefix="prod/",
        occurred_at=_AT,
    )
    assert key == f"prod/chat/2026/07/29/{_REQUEST_UID}/2-{digest}.png"


def test_build_object_key_legacy_format() -> None:
    digest = hashlib.sha256(_PDF_BYTES).hexdigest()[:16]
    key = build_object_key(
        scope="legacy",
        owner_uid="01JUSAGELOG0001",
        index=1,
        content=_PDF_BYTES,
        mime="application/pdf",
        key_prefix="prod",
    )
    assert key == f"prod/legacy/01JUSAGELOG0001/1-{digest}.pdf"


def test_build_object_key_uses_taipei_calendar_day() -> None:
    """UTC 的 2026-07-28T17:30Z 在台北已是 07-29 —— 日期分層須取台北日曆日。"""
    utc_at = datetime(2026, 7, 28, 17, 30, tzinfo=ZoneInfo("UTC"))
    key = build_object_key(
        scope="chat",
        owner_uid=_REQUEST_UID,
        index=0,
        content=_PNG_BYTES,
        mime="image/png",
        key_prefix="test",
        occurred_at=utc_at,
    )
    assert "/chat/2026/07/29/" in key


def test_build_object_key_is_safe() -> None:
    key = build_object_key(
        scope="legacy",
        owner_uid="../../etc/passwd",
        index=0,
        content=_PNG_BYTES,
        mime="image/png",
        key_prefix="/dev/",
    )
    assert not key.startswith("/")
    assert ".." not in key
    assert key.startswith("dev/legacy/")


def test_build_object_key_empty_prefix_has_no_leading_slash() -> None:
    key = build_object_key(
        scope="legacy",
        owner_uid="u1",
        index=0,
        content=_PNG_BYTES,
        mime="image/png",
        key_prefix="",
    )
    assert key.startswith("legacy/u1/")


def test_build_object_key_requires_occurred_at_for_chat() -> None:
    with pytest.raises(ValueError):
        build_object_key(
            scope="chat",
            owner_uid=_REQUEST_UID,
            index=0,
            content=_PNG_BYTES,
            mime="image/png",
            key_prefix="test",
        )


def test_extension_and_content_type_whitelist() -> None:
    assert extension_for_mime("image/PNG") == "png"
    assert extension_for_mime("application/pdf") == "pdf"
    # 白名單外(含可帶 script 的 SVG)一律落 bin + octet-stream,禁瀏覽器直接渲染。
    assert extension_for_mime("image/svg+xml") == "bin"
    assert content_type_for_mime("image/svg+xml") == "application/octet-stream"
    assert content_type_for_mime("image/png") == "image/png"


# --- 3. 遠端 URL 原樣保留、未呼叫 S3 ------------------------------------


async def test_remote_url_kept_as_is_and_s3_not_called(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_settings(monkeypatch)
    stub = _StubS3()
    snapshot = await build_attachment_snapshot(
        request_uid=_REQUEST_UID,
        images=["https://example.com/a.png", "http://example.com/b.jpg"],
        client=stub,  # type: ignore[arg-type]
        occurred_at=_AT,
    )
    assert snapshot.images == ["https://example.com/a.png", "http://example.com/b.jpg"]
    assert stub.calls == []
    assert snapshot.uploaded == 0
    assert snapshot.failed == 0


# --- 4. S3 失敗 → 失敗標記、不拋例外、有 log ----------------------------


async def test_s3_upload_error_yields_marker_without_raising(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _use_settings(monkeypatch)
    stub = _StubS3(fail_on={0}, error=S3UploadError("S3 put_object 失敗:AccessDenied"))
    with caplog.at_level(logging.WARNING, logger="app.services.attachment"):
        snapshot = await build_attachment_snapshot(
            request_uid=_REQUEST_UID,
            images=[_PNG_URI],
            client=stub,  # type: ignore[arg-type]
            occurred_at=_AT,
        )
    marker = snapshot.images[0]
    assert isinstance(marker, dict)
    assert marker["type"] == "image_url"
    assert marker["upload_failed"] is True
    assert marker["mime"] == "image/png"
    assert marker["bytes"] == len(_PNG_BYTES)
    assert marker["sha256"] == hashlib.sha256(_PNG_BYTES).hexdigest()
    assert snapshot.failed == 1
    assert snapshot.uploaded == 0

    records = [r for r in caplog.records if r.name == "app.services.attachment"]
    assert records, "S3 失敗必須落結構化 log"
    message = records[0].getMessage()
    assert "s3_upload_failed" in message
    assert "index=0" in message
    # log 禁帶 base64 內容。
    assert base64.b64encode(_PNG_BYTES).decode() not in message


async def test_s3_timeout_is_also_best_effort(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_settings(monkeypatch)
    stub = _StubS3(fail_on={0}, error=S3TimeoutError("S3 put_object 逾時"))
    snapshot = await build_attachment_snapshot(
        request_uid=_REQUEST_UID,
        images=[_PNG_URI],
        client=stub,  # type: ignore[arg-type]
        occurred_at=_AT,
    )
    assert isinstance(snapshot.images[0], dict)
    assert snapshot.failed == 1


async def test_malformed_data_uri_is_best_effort(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _use_settings(monkeypatch)
    stub = _StubS3()
    with caplog.at_level(logging.WARNING, logger="app.services.attachment"):
        snapshot = await build_attachment_snapshot(
            request_uid=_REQUEST_UID,
            images=["data:image/png;base64,!!!broken!!!"],
            client=stub,  # type: ignore[arg-type]
            occurred_at=_AT,
        )
    marker = snapshot.images[0]
    assert isinstance(marker, dict)
    assert marker["upload_failed"] is True
    assert marker["reason"] == "invalid_data_uri"
    assert stub.calls == []
    assert any("invalid_data_uri" in r.getMessage() for r in caplog.records)


async def test_unexpected_exception_does_not_break_main_flow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_settings(monkeypatch)
    stub = _StubS3(fail_on={0}, error=RuntimeError("未預期錯誤"))
    snapshot = await build_attachment_snapshot(
        request_uid=_REQUEST_UID,
        images=[_PNG_URI],
        client=stub,  # type: ignore[arg-type]
        occurred_at=_AT,
    )
    assert isinstance(snapshot.images[0], dict)
    assert snapshot.failed == 1


async def test_client_unavailable_marks_all_failed_without_base64(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """開關已開卻取不到 client:全部記 upload_failed,**不**降級寫回 base64。"""
    _use_settings(monkeypatch)

    def _raise() -> None:
        raise S3UploadError("S3_BUCKET 未設定")

    monkeypatch.setattr(svc, "get_s3_client", _raise)
    snapshot = await build_attachment_snapshot(
        request_uid=_REQUEST_UID,
        images=[_PNG_URI],
        files=[{"filename": "a.pdf", "file_data": _PDF_URI}],
        occurred_at=_AT,
    )
    assert isinstance(snapshot.images[0], dict)
    assert snapshot.failed == 2
    assert "base64" not in _dump(snapshot)


# --- 5. 部分成功部分失敗:順序與索引正確 --------------------------------


async def test_partial_failure_keeps_order_and_index(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_settings(monkeypatch)
    stub = _StubS3(fail_on={1})
    snapshot = await build_attachment_snapshot(
        request_uid=_REQUEST_UID,
        images=[_PNG_URI, _PNG2_URI, _PNG3_URI],
        client=stub,  # type: ignore[arg-type]
        occurred_at=_AT,
    )
    first, second, third = snapshot.images
    assert isinstance(first, str)
    assert isinstance(second, dict)
    assert isinstance(third, str)

    assert first.endswith(f"/0-{hashlib.sha256(_PNG_BYTES).hexdigest()[:16]}.png")
    assert third.endswith(f"/2-{hashlib.sha256(_PNG3_BYTES).hexdigest()[:16]}.png")
    assert second["sha256"] == hashlib.sha256(_PNG2_BYTES).hexdigest()
    assert second["bytes"] == len(_PNG2_BYTES)
    assert snapshot.uploaded == 2
    assert snapshot.failed == 1

    # 上傳成功的兩張確實送出、且送的是解碼後的原始 bytes。
    assert [body for _, body, _ in stub.calls] == [_PNG_BYTES, _PNG2_BYTES, _PNG3_BYTES]


# --- 6. 開關關閉:完全不呼叫 S3,輸出等同輸入 --------------------------


async def test_disabled_switch_short_circuits(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_settings(monkeypatch, S3_STORAGE_ENABLED=False)
    _no_client(monkeypatch)
    stub = _StubS3()
    snapshot = await build_attachment_snapshot(
        request_uid=_REQUEST_UID,
        images=[_PNG_URI, "https://example.com/a.png"],
        files=[{"filename": "a.pdf", "file_data": _PDF_URI}],
        client=stub,  # type: ignore[arg-type]
        occurred_at=_AT,
    )
    assert snapshot.enabled is False
    # images 原樣保留(等同 v2.2.0 行為)。
    assert snapshot.images == [_PNG_URI, "https://example.com/a.png"]
    # files 維持 v2.2.0 的「僅記檔名」,file_data 從不入快照。
    assert snapshot.files == ["a.pdf"]
    assert stub.calls == []


async def test_disabled_switch_messages_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_settings(monkeypatch, S3_STORAGE_ENABLED=False)
    _no_client(monkeypatch)
    messages = _messages(
        {"type": "text", "text": "看圖"},
        {"type": "image_url", "image_url": {"url": _PNG_URI}},
        {"type": "file", "file": {"filename": "a.pdf", "file_data": _PDF_URI}},
    )
    snapshot = await build_attachment_snapshot(
        request_uid=_REQUEST_UID, messages=messages, occurred_at=_AT
    )
    assert snapshot.messages is not None
    parts = snapshot.messages[0]["content"]
    assert isinstance(parts, list)
    assert parts[0] == {"type": "text", "text": "看圖"}
    assert parts[1] == {"type": "image_url", "image_url": {"url": _PNG_URI}}
    assert parts[2] == {"type": "file", "file": {"filename": "a.pdf"}}
    assert "file_data" not in _dump(snapshot)


# --- 7. 單輪與 messages 兩模式走同一路徑、產出等價結果 -----------------


async def test_single_turn_and_messages_modes_are_equivalent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_settings(monkeypatch)

    single_stub = _StubS3()
    single = await build_attachment_snapshot(
        request_uid=_REQUEST_UID,
        images=[_PNG_URI],
        files=[{"filename": "a.pdf", "file_data": _PDF_URI}],
        client=single_stub,  # type: ignore[arg-type]
        occurred_at=_AT,
    )

    messages_stub = _StubS3()
    messages = await build_attachment_snapshot(
        request_uid=_REQUEST_UID,
        messages=_messages(
            {"type": "text", "text": "看圖"},
            {"type": "image_url", "image_url": {"url": _PNG_URI}},
            {"type": "file", "file": {"filename": "a.pdf", "file_data": _PDF_URI}},
        ),
        client=messages_stub,  # type: ignore[arg-type]
        occurred_at=_AT,
    )

    assert messages.messages is not None
    parts = messages.messages[0]["content"]
    assert isinstance(parts, list)

    # 兩模式對同一份內容產出**完全相同**的 key,且 S3 收到相同的 (key, body, content_type)。
    assert parts[1] == {"type": "image_url", "image_url": {"url": single.images[0]}}
    assert parts[2] == single.files[0]
    assert single_stub.calls == messages_stub.calls
    assert single.uploaded == messages.uploaded == 2


async def test_messages_mode_partial_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_settings(monkeypatch)
    stub = _StubS3(fail_on={0})
    snapshot = await build_attachment_snapshot(
        request_uid=_REQUEST_UID,
        messages=_messages(
            {"type": "image_url", "image_url": {"url": _PNG_URI}},
            {"type": "file", "file": {"filename": "a.pdf", "file_data": _PDF_URI}},
        ),
        client=stub,  # type: ignore[arg-type]
        occurred_at=_AT,
    )
    assert snapshot.messages is not None
    parts = snapshot.messages[0]["content"]
    assert isinstance(parts, list)
    assert parts[0]["upload_failed"] is True
    assert parts[1]["file"]["filename"] == "a.pdf"
    assert isinstance(parts[1]["file"]["key"], str)
    assert snapshot.uploaded == 1
    assert snapshot.failed == 1


async def test_messages_string_content_untouched(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_settings(monkeypatch)
    stub = _StubS3()
    snapshot = await build_attachment_snapshot(
        request_uid=_REQUEST_UID,
        messages=[ChatMessage.model_validate({"role": "system", "content": "你是助理"})],
        client=stub,  # type: ignore[arg-type]
        occurred_at=_AT,
    )
    assert snapshot.messages == [{"role": "system", "content": "你是助理"}]
    assert stub.calls == []


# --- 8. 快照零 base64 回歸(硬規則) ------------------------------------


async def test_snapshot_never_contains_base64_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_settings(monkeypatch)
    stub = _StubS3()
    snapshot = await build_attachment_snapshot(
        request_uid=_REQUEST_UID,
        images=[_PNG_URI],
        files=[{"filename": "報告.pdf", "file_data": _PDF_URI}],
        client=stub,  # type: ignore[arg-type]
        occurred_at=_AT,
    )
    dumped = _dump(snapshot)
    assert "base64" not in dumped
    assert "file_data" not in dumped
    assert snapshot.files[0] == {
        "type": "file",
        "file": {"filename": "報告.pdf", "key": stub.calls[1][0]},
    }
    assert stub.calls[1][2] == "application/pdf"


async def test_snapshot_never_contains_base64_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_settings(monkeypatch)
    stub = _StubS3(fail_on={0, 1})
    snapshot = await build_attachment_snapshot(
        request_uid=_REQUEST_UID,
        images=[_PNG_URI],
        files=[{"filename": "報告.pdf", "file_data": _PDF_URI}],
        client=stub,  # type: ignore[arg-type]
        occurred_at=_AT,
    )
    dumped = _dump(snapshot)
    assert "base64" not in dumped
    assert "file_data" not in dumped
    assert snapshot.files[0] == {
        "type": "file",
        "file": {
            "filename": "報告.pdf",
            "upload_failed": True,
            "mime": "application/pdf",
            "bytes": len(_PDF_BYTES),
            "sha256": hashlib.sha256(_PDF_BYTES).hexdigest(),
            "reason": "s3_upload_failed",
        },
    }


async def test_snapshot_never_contains_base64_in_messages_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_settings(monkeypatch)
    stub = _StubS3(fail_on={1})
    snapshot = await build_attachment_snapshot(
        request_uid=_REQUEST_UID,
        messages=_messages(
            {"type": "image_url", "image_url": {"url": _PNG_URI}},
            {"type": "file", "file": {"filename": "a.pdf", "file_data": _PDF_URI}},
        ),
        client=stub,  # type: ignore[arg-type]
        occurred_at=_AT,
    )
    dumped = _dump(snapshot)
    assert "base64" not in dumped
    assert "file_data" not in dumped


async def test_files_disabled_switch_never_leaks_file_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use_settings(monkeypatch, S3_STORAGE_ENABLED=False)
    _no_client(monkeypatch)
    snapshot = await build_attachment_snapshot(
        request_uid=_REQUEST_UID,
        files=[{"filename": "a.pdf", "file_data": _PDF_URI}],
        occurred_at=_AT,
    )
    dumped = json.dumps(snapshot.files, ensure_ascii=False)
    assert "base64" not in dumped
    assert "file_data" not in dumped


# --- 其他 ---------------------------------------------------------------


async def test_empty_input_produces_empty_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_settings(monkeypatch)
    stub = _StubS3()
    snapshot = await build_attachment_snapshot(
        request_uid=_REQUEST_UID,
        client=stub,  # type: ignore[arg-type]
        occurred_at=_AT,
    )
    assert snapshot.images == []
    assert snapshot.files == []
    assert snapshot.messages is None
    assert stub.calls == []


async def test_key_prefix_from_settings_is_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    _use_settings(monkeypatch, S3_KEY_PREFIX="prod")
    stub = _StubS3()
    snapshot = await build_attachment_snapshot(
        request_uid=_REQUEST_UID,
        images=[_PNG_URI],
        client=stub,  # type: ignore[arg-type]
        occurred_at=_AT,
    )
    assert isinstance(snapshot.images[0], str)
    assert snapshot.images[0].startswith("prod/chat/2026/07/29/")


async def test_snapshot_key_matches_public_key_builder(monkeypatch: pytest.MonkeyPatch) -> None:
    """530 / 531 重算 key 的前提:落地層用的就是公開匯出的那支函式。"""
    _use_settings(monkeypatch)
    stub = _StubS3()
    snapshot = await build_attachment_snapshot(
        request_uid=_REQUEST_UID,
        images=[_PNG_URI],
        client=stub,  # type: ignore[arg-type]
        occurred_at=_AT,
    )
    expected = build_object_key(
        scope="chat",
        owner_uid=_REQUEST_UID,
        index=0,
        content=_PNG_BYTES,
        mime="image/png",
        key_prefix="test",
        occurred_at=_AT,
    )
    assert snapshot.images[0] == expected
