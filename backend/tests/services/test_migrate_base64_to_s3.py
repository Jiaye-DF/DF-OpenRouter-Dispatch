"""遷移 script Phase 1(`scripts/migrate_base64_to_s3.py`)測試(task-530)。

守三件事(照 task-530 Acceptance):

1. **DB 零變更**:Phase 1 對 DB 只有 SELECT;跑完 `request_content` / `updated_at`
   一個 byte 都不變。
2. **key 與 task-524 一致**:script 產出的 key 必須等於直接呼叫
   `app.services.attachment.build_object_key(scope="legacy", ...)` 的結果 ——
   Phase 2 靠重算取得同一把 key,對不上整個兩階段設計就崩了。
3. **冪等 + best-effort**:重跑不重傳、單一附件失敗不中斷整批。

S3 一律 stub、**不打真 AWS**(`09-object-storage.md` § 測試)。

DB 這一層分兩種測法,理由寫在這裡免得被誤讀為違反「禁 mock SQL」:

- 大多數案例用 `_RecordingSession` 這個記憶體替身。它測的**不是** SQL 語意,而是
  script 自身的走訪 / 冪等 / 報表 / **「到底送出了哪些語句」** —— 「無寫入語句」這條
  只有攔截語句才驗得到,真 DB 反而驗不了(rollback 後看不出中途有沒有寫過)。
- 「DB 零變更」另有一支真 DB 整合測試(`test_phase1_leaves_database_untouched`),
  連本機測試 DB、以全表指紋(`request_content` / `updated_at` / `xmin`)前後比對,
  測試結束一律 rollback。DB 不可用時 skip(對齊 `tests/repositories/*` 慣例)。
"""

from __future__ import annotations

import base64
import copy
import json
import os
import sys
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from uuid_utils import uuid7

from app.clients.s3 import S3ConfigError, S3TimeoutError, S3UploadError
from app.models.usage_log import UsageLog
from app.services.attachment import build_object_key, content_type_for_mime

# `backend/scripts` 不是 package(無 `__init__.py`),故先掛上 sys.path 再以**頂層模組名**
# import。why 不寫 `from scripts.migrate_base64_to_s3 import ...`:那會讓同一個檔在
# `uv run mypy .` 下同時被認成 `migrate_base64_to_s3` 與 `scripts.migrate_base64_to_s3`,
# mypy 以 "Source file found twice" 直接中止,全庫型別檢查等於停擺。
sys.path.append(str(Path(__file__).resolve().parents[2] / "scripts"))

from migrate_base64_to_s3 import (  # noqa: E402
    MigrationReport,
    RewritePreconditionError,
    RewriteReport,
    format_report,
    format_rewrite_report,
    iter_image_attachments,
    legacy_object_key,
    run_rewrite,
    run_upload,
)

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://ord:ord_dev_pass_change_me@localhost:5533/ord",
)

_PREFIX = "test"

_PNG_BYTES = b"\x89PNG\r\n\x1a\n-legacy-image-one"
_PNG_URI = "data:image/png;base64," + base64.b64encode(_PNG_BYTES).decode()
_JPG_BYTES = b"\xff\xd8\xff-legacy-image-two"
_JPG_URI = "data:image/jpeg;base64," + base64.b64encode(_JPG_BYTES).decode()
_GIF_BYTES = b"GIF89a-legacy-image-three"
_GIF_URI = "data:image/gif;base64," + base64.b64encode(_GIF_BYTES).decode()

_UID_A = "01920000-0000-7000-8000-0000000000aa"
_UID_B = "01920000-0000-7000-8000-0000000000bb"

# Phase 2 用:掃描到的原 `updated_at`,與「trigger 若沒被停用會寫進去的值」。
_FAKE_UPDATED_AT = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)
_TRIGGER_NOW = datetime(2026, 7, 29, 9, 0, tzinfo=UTC)


# --- 快照形狀 -----------------------------------------------------------


def _single_turn(*images: str) -> dict[str, object]:
    """單輪模式快照(`proxy._build_request_log` 的 v2.1.1 形狀)。"""
    return {"model": "openai/gpt-4o", "text": "看圖", "images": list(images)}


def _messages(*images: str) -> dict[str, object]:
    """messages 直傳模式快照(v2.1.2 形狀)。"""
    return {
        "model": "openai/gpt-4o",
        "messages": [
            {"role": "system", "content": "you are a bot"},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "看圖"},
                    *[{"type": "image_url", "image_url": {"url": img}} for img in images],
                    {"type": "file", "file": {"filename": "spec.pdf"}},
                ],
            },
        ],
    }


# --- 替身 ---------------------------------------------------------------


class _StubS3:
    """S3 替身:記錄 `put_object` / `head_object`,可指定失敗與已存在的 key。"""

    def __init__(
        self,
        *,
        existing: set[str] | None = None,
        fail_puts: set[str] | None = None,
        fail_heads: set[str] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.puts: list[tuple[str, bytes, str]] = []
        self.heads: list[str] = []
        self.existing: set[str] = set(existing or ())
        self._fail_puts = fail_puts or set()
        self._fail_heads = fail_heads or set()
        self._error = error or S3UploadError("S3 put_object 失敗:AccessDenied")

    async def head_object(self, key: str) -> bool:
        self.heads.append(key)
        if key in self._fail_heads:
            raise self._error
        return key in self.existing

    async def put_object(self, key: str, body: bytes, content_type: str) -> None:
        if key in self._fail_puts:
            raise self._error
        self.puts.append((key, body, content_type))
        # 上傳成功即視為存在 —— 讓「連跑兩次」的冪等測試貼近真實 S3 行為。
        self.existing.add(key)


class _FakeResult:
    def __init__(self, rows: Sequence[tuple[object, ...]]) -> None:
        self._rows = list(rows)

    def all(self) -> list[tuple[object, ...]]:
        return self._rows

    def first(self) -> tuple[object, ...] | None:
        return self._rows[0] if self._rows else None

    def scalar_one(self) -> object:
        return self._rows[0][0]


class _RecordingSession:
    """記憶體 session 替身:模擬 `pid` 游標分批,並**記錄每一條送出的語句**。

    「Phase 1 無寫入語句」這條 acceptance 只有攔截語句驗得到,故這裡刻意不用真 DB。
    """

    def __init__(self, rows: Sequence[tuple[int, str, dict[str, object]]]) -> None:
        self._rows = sorted(rows, key=lambda r: r[0])
        self.statements: list[str] = []
        self.commits = 0

    async def execute(self, statement: object) -> _FakeResult:
        sql = str(statement)
        self.statements.append(sql)
        params = statement.compile().params  # type: ignore[attr-defined]
        after_pid = int(params["after_pid"])
        batch_size = int(params["batch_size"])
        picked = [
            row
            for row in self._rows
            if row[0] > after_pid and _like_base64(json.dumps(row[2], ensure_ascii=False))
        ]
        # 掃描語句自 task-531 起多帶一欄 `updated_at`(兩階段共用同一條 SQL)。
        return _FakeResult([(*row, _FAKE_UPDATED_AT) for row in picked[:batch_size]])

    async def commit(self) -> None:  # pragma: no cover - 被呼叫即代表行為已偏離
        self.commits += 1


class _MemRow:
    __slots__ = ("content", "pid", "uid", "updated_at")

    def __init__(self, pid: int, uid: str, content: dict[str, object]) -> None:
        self.pid = pid
        self.uid = uid
        self.content = copy.deepcopy(content)
        self.updated_at = _FAKE_UPDATED_AT


def _json_at(doc: object, path: Sequence[str]) -> object:
    cur = doc
    for part in path:
        if isinstance(cur, list):
            idx = int(part)
            if idx >= len(cur):
                return None
            cur = cur[idx]
        elif isinstance(cur, dict):
            if part not in cur:
                return None
            cur = cur[part]
        else:
            return None
    return cur


def _json_put(doc: object, path: Sequence[str], value: str) -> None:
    parent = _json_at(doc, path[:-1])
    last = path[-1]
    if isinstance(parent, list):
        parent[int(last)] = value
    elif isinstance(parent, dict):
        parent[last] = value


class _RewriteSession:
    """Phase 2 用的記憶體 session 替身:掃描 / `jsonb_set` UPDATE / 完成判準查詢。

    刻意**模擬 DB trigger** `trg_usage_logs_updated_at`:同一個交易內若沒先送出
    `SET LOCAL session_replication_role = replica`,UPDATE 就會把 `updated_at` 推成
    `_TRIGGER_NOW`。這讓「停用 trigger 的語句必須先送」在單元層就測得到;
    真 DB 的行為另有整合測試把關(`test_rewrite_real_db_*`)。
    """

    def __init__(
        self,
        rows: Sequence[tuple[int, str, dict[str, object]]],
        *,
        deny_bypass: bool = False,
    ) -> None:
        self.rows: dict[int, _MemRow] = {
            pid: _MemRow(pid, uid, content) for pid, uid, content in rows
        }
        self.statements: list[str] = []
        self.updates: list[dict[str, object]] = []
        self.commits = 0
        self.rollbacks = 0
        self.bypasses = 0
        self._bypass_active = False
        self._deny_bypass = deny_bypass

    async def execute(self, statement: object) -> _FakeResult:
        sql = " ".join(str(statement).split())
        self.statements.append(sql)

        if sql.startswith("SET LOCAL"):
            if self._deny_bypass:
                raise DBAPIError(sql, {}, PermissionError("permission denied to set parameter"))
            self._bypass_active = True
            self.bypasses += 1
            return _FakeResult([])

        params = statement.compile().params  # type: ignore[attr-defined]

        if sql.startswith("SELECT count(*)"):
            remaining = sum(
                1
                for row in self.rows.values()
                if _like_base64(json.dumps(row.content, ensure_ascii=False))
            )
            return _FakeResult([(remaining,)])

        if sql.startswith("SELECT pid"):
            after_pid = int(params["after_pid"])
            batch_size = int(params["batch_size"])
            picked = [
                row
                for row in sorted(self.rows.values(), key=lambda r: r.pid)
                if row.pid > after_pid
                and _like_base64(json.dumps(row.content, ensure_ascii=False))
            ]
            return _FakeResult(
                [
                    (row.pid, row.uid, copy.deepcopy(row.content), row.updated_at)
                    for row in picked[:batch_size]
                ]
            )

        if sql.startswith("UPDATE usage_logs"):
            self.updates.append(dict(params))
            row = self.rows[int(params["pid"])]
            path = [str(part) for part in params["path"]]
            if _json_at(row.content, path) != params["expected"]:
                # 樂觀鎖沒中(`AND request_content #>> path = :expected`)。
                return _FakeResult([])
            _json_put(row.content, path, str(params["value"]))
            row.updated_at = params["updated_at"] if self._bypass_active else _TRIGGER_NOW
            return _FakeResult([(row.pid,)])

        raise AssertionError(f"未預期的語句:{sql}")

    async def commit(self) -> None:
        self.commits += 1
        self._bypass_active = False

    async def rollback(self) -> None:
        self.rollbacks += 1
        self._bypass_active = False


def _like_base64(dumped: str) -> str | None:
    """模擬 `request_content::text LIKE '%data:%base64,%'`。"""
    head = dumped.find("data:")
    if head < 0:
        return None
    return dumped if "base64," in dumped[head:] else None


def _expected_key(uid: str, index: int, content: bytes, mime: str) -> str:
    """直接呼叫 task-524 的函式算 key —— 用來對照 script 的產出。"""
    return build_object_key(
        scope="legacy",
        owner_uid=uid,
        index=index,
        content=content,
        mime=mime,
        key_prefix=_PREFIX,
    )


async def _run(
    session: _RecordingSession,
    client: _StubS3 | None,
    **kwargs: object,
) -> MigrationReport:
    return await run_upload(
        session,  # type: ignore[arg-type]
        client=client,  # type: ignore[arg-type]
        key_prefix=_PREFIX,
        **kwargs,  # type: ignore[arg-type]
    )


# --- 1. 走訪:兩種快照形狀與序號規則 -------------------------------------


def test_iter_covers_single_turn_shape() -> None:
    refs = list(iter_image_attachments(_single_turn(_PNG_URI, _JPG_URI)))
    assert [r.index for r in refs] == [0, 1]
    assert [r.path for r in refs] == [("images", 0), ("images", 1)]
    assert [r.value for r in refs] == [_PNG_URI, _JPG_URI]


def test_iter_covers_messages_shape() -> None:
    refs = list(iter_image_attachments(_messages(_PNG_URI, _JPG_URI)))
    assert [r.index for r in refs] == [0, 1]
    # path 指到可直接寫回的字串節點(Phase 2 用)。
    assert refs[0].path == ("messages", 1, "content", 1, "image_url", "url")
    assert refs[1].path == ("messages", 1, "content", 2, "image_url", "url")


def test_iter_index_counts_every_slot_including_remote_and_malformed() -> None:
    """序號代表「位置」,遠端 URL 與畸形值同樣佔號 —— 否則 Phase 2 會整排位移。"""
    content = _single_turn("https://cdn.example.com/a.png", "data:image/png;base64,@@@", _PNG_URI)
    refs = list(iter_image_attachments(content))
    assert [r.index for r in refs] == [0, 1, 2]
    assert refs[2].value == _PNG_URI


def test_iter_ignores_broken_structures() -> None:
    content: dict[str, object] = {
        "images": ["ok", 123, None],
        "messages": [
            "not-a-dict",
            {"role": "user", "content": "plain text"},
            {"role": "user", "content": [{"type": "image_url"}, {"type": "image_url", "image_url": {}}]},
        ],
    }
    refs = list(iter_image_attachments(content))
    assert [r.value for r in refs] == ["ok"]


def test_iter_skips_files_without_content() -> None:
    """歷史 `files` 只有檔名、從未留過內容 → 不走訪、不佔序號(§D.3)。"""
    content: dict[str, object] = {"images": [_PNG_URI], "files": ["spec.pdf"]}
    refs = list(iter_image_attachments(content))
    assert len(refs) == 1


# --- 2. key 與 task-524 一致 ---------------------------------------------


def test_legacy_key_matches_task_524_function() -> None:
    key = legacy_object_key(
        usage_log_uid=_UID_A, index=3, content=_PNG_BYTES, mime="image/png", key_prefix=_PREFIX
    )
    assert key == _expected_key(_UID_A, 3, _PNG_BYTES, "image/png")
    assert key.startswith(f"{_PREFIX}/legacy/{_UID_A}/3-")
    assert key.endswith(".png")


async def test_uploaded_key_matches_task_524_function() -> None:
    """script **實際上傳用的 key** 必須與直接呼叫 524 的結果逐字相同。"""
    session = _RecordingSession([(1, _UID_A, _single_turn(_PNG_URI, _JPG_URI))])
    client = _StubS3()
    await _run(session, client)

    assert [key for key, _, _ in client.puts] == [
        _expected_key(_UID_A, 0, _PNG_BYTES, "image/png"),
        _expected_key(_UID_A, 1, _JPG_BYTES, "image/jpeg"),
    ]


async def test_upload_body_and_content_type_are_derived_from_whitelist() -> None:
    session = _RecordingSession([(1, _UID_A, _single_turn(_PNG_URI))])
    client = _StubS3()
    await _run(session, client)

    key, body, content_type = client.puts[0]
    assert body == _PNG_BYTES
    assert content_type == content_type_for_mime("image/png") == "image/png"
    assert key.endswith(".png")


# --- 3. DB 零變更 / 無寫入語句 -------------------------------------------


async def test_phase1_emits_only_select_statements() -> None:
    session = _RecordingSession(
        [(1, _UID_A, _single_turn(_PNG_URI)), (2, _UID_B, _messages(_JPG_URI))]
    )
    await _run(session, _StubS3())

    assert session.statements, "至少要送出一條掃描語句"
    for sql in session.statements:
        stripped = sql.strip().upper()
        assert stripped.startswith("SELECT")
        for forbidden in ("UPDATE ", "INSERT ", "DELETE "):
            assert forbidden not in stripped
    assert session.commits == 0


async def test_phase1_emits_only_select_statements_in_dry_run() -> None:
    session = _RecordingSession([(1, _UID_A, _single_turn(_PNG_URI))])
    await _run(session, _StubS3(), dry_run=True)

    assert all(sql.strip().upper().startswith("SELECT") for sql in session.statements)
    assert session.commits == 0


# --- 4. dry-run -----------------------------------------------------------


async def test_dry_run_does_not_upload_but_counts_correctly() -> None:
    session = _RecordingSession(
        [(1, _UID_A, _single_turn(_PNG_URI, _JPG_URI)), (2, _UID_B, _messages(_GIF_URI))]
    )
    client = _StubS3()
    report = await _run(session, client, dry_run=True)

    assert client.puts == []
    assert report.rows_scanned == 2
    assert report.eligible == 3
    assert report.planned == 3
    assert report.uploaded == 0


async def test_dry_run_counts_existing_objects_separately() -> None:
    existing = _expected_key(_UID_A, 0, _PNG_BYTES, "image/png")
    session = _RecordingSession([(1, _UID_A, _single_turn(_PNG_URI, _JPG_URI))])
    client = _StubS3(existing={existing})
    report = await _run(session, client, dry_run=True)

    assert client.puts == []
    assert report.existing == 1
    assert report.planned == 1


async def test_dry_run_works_without_s3_client() -> None:
    """沒配 AWS 憑證的 dev 環境也要跑得起來(只報「應上傳」)。"""
    session = _RecordingSession([(1, _UID_A, _single_turn(_PNG_URI))])
    report = await _run(session, None, dry_run=True)

    assert report.eligible == 1
    assert report.planned == 1
    assert report.uploaded == 0


# --- 5. 冪等 --------------------------------------------------------------


async def test_second_run_uploads_nothing() -> None:
    rows = [(1, _UID_A, _single_turn(_PNG_URI, _JPG_URI)), (2, _UID_B, _messages(_GIF_URI))]
    client = _StubS3()

    first = await _run(_RecordingSession(rows), client)
    assert first.uploaded == 3
    assert len(client.puts) == 3

    client.puts.clear()
    second = await _run(_RecordingSession(rows), client)

    assert client.puts == []
    assert second.uploaded == 0
    assert second.existing == 3


# --- 6. 兩種形狀都被掃到並上傳 --------------------------------------------


async def test_both_snapshot_shapes_are_uploaded() -> None:
    session = _RecordingSession(
        [(1, _UID_A, _single_turn(_PNG_URI)), (2, _UID_B, _messages(_JPG_URI, _GIF_URI))]
    )
    client = _StubS3()
    report = await _run(session, client)

    assert report.rows_scanned == 2
    assert report.rows_with_image == 2
    assert report.uploaded == 3
    assert [key for key, _, _ in client.puts] == [
        _expected_key(_UID_A, 0, _PNG_BYTES, "image/png"),
        _expected_key(_UID_B, 0, _JPG_BYTES, "image/jpeg"),
        _expected_key(_UID_B, 1, _GIF_BYTES, "image/gif"),
    ]


# --- 7. 失敗不中斷 --------------------------------------------------------


async def test_upload_failure_is_recorded_and_batch_continues() -> None:
    failing = _expected_key(_UID_A, 0, _PNG_BYTES, "image/png")
    session = _RecordingSession(
        [(1, _UID_A, _single_turn(_PNG_URI, _JPG_URI)), (2, _UID_B, _messages(_GIF_URI))]
    )
    client = _StubS3(fail_puts={failing})
    report = await _run(session, client)

    assert report.failed == 1
    assert report.failures[0].pid == 1
    assert report.failures[0].index == 0
    assert report.uploaded == 2
    assert [key for key, _, _ in client.puts] == [
        _expected_key(_UID_A, 1, _JPG_BYTES, "image/jpeg"),
        _expected_key(_UID_B, 0, _GIF_BYTES, "image/gif"),
    ]


async def test_head_failure_is_recorded_and_batch_continues() -> None:
    failing = _expected_key(_UID_A, 0, _PNG_BYTES, "image/png")
    session = _RecordingSession([(1, _UID_A, _single_turn(_PNG_URI, _JPG_URI))])
    client = _StubS3(fail_heads={failing}, error=S3TimeoutError("S3 head_object 逾時"))
    report = await _run(session, client)

    assert report.failed == 1
    assert report.failures[0].reason == "s3_head_failed"
    assert report.uploaded == 1


async def test_unexpected_exception_does_not_break_batch() -> None:
    class _Boom(_StubS3):
        attempts = 0

        async def put_object(self, key: str, body: bytes, content_type: str) -> None:
            _Boom.attempts += 1
            if _Boom.attempts == 1:
                raise RuntimeError("boto3 內部爆炸")
            await super().put_object(key, body, content_type)

    session = _RecordingSession([(1, _UID_A, _single_turn(_PNG_URI, _JPG_URI))])
    report = await _run(session, _Boom())

    assert report.failed == 1
    assert report.failures[0].detail == "RuntimeError"
    assert report.uploaded == 1


async def test_config_error_aborts_immediately() -> None:
    """憑證 / bucket 設定錯每列都會重演,續跑只會刷出滿版失敗清單 → 直接中止。"""
    session = _RecordingSession([(1, _UID_A, _single_turn(_PNG_URI, _JPG_URI))])
    client = _StubS3(
        fail_heads={_expected_key(_UID_A, 0, _PNG_BYTES, "image/png")},
        error=S3ConfigError("S3 憑證未正確注入:NoCredentialsError"),
    )
    with pytest.raises(S3ConfigError):
        await _run(session, client)
    assert client.puts == []


# --- 8. 遠端 URL / 畸形值 -------------------------------------------------


async def test_remote_url_is_left_alone_and_malformed_is_counted() -> None:
    content = _single_turn(
        "https://cdn.example.com/a.png", "data:image/png;base64,@@@not-base64", _PNG_URI
    )
    session = _RecordingSession([(1, _UID_A, content)])
    client = _StubS3()
    report = await _run(session, client)

    assert report.remote_skipped == 1
    assert report.invalid == 1
    assert report.eligible == 1
    assert report.uploaded == 1
    # 序號 2:遠端 URL 與畸形值各佔一號。
    assert client.puts[0][0] == _expected_key(_UID_A, 2, _PNG_BYTES, "image/png")


# --- 9. 分批 / limit / 併發 ----------------------------------------------


async def test_cursor_batching_covers_all_rows() -> None:
    rows = [(pid, _UID_A, _single_turn(_PNG_URI)) for pid in range(1, 8)]
    session = _RecordingSession(rows)
    client = _StubS3()
    report = await _run(session, client, batch_size=2)

    assert report.rows_scanned == 7
    # 7 列 / 每批 2 → 4 批有資料 + 1 批空。
    assert len(session.statements) == 5


async def test_limit_stops_early() -> None:
    rows = [(pid, _UID_A, _single_turn(_PNG_URI)) for pid in range(1, 11)]
    session = _RecordingSession(rows)
    report = await _run(session, _StubS3(), batch_size=3, limit=4)

    assert report.rows_scanned == 4


async def test_after_pid_resumes() -> None:
    rows = [(pid, _UID_A, _single_turn(_PNG_URI)) for pid in range(1, 6)]
    session = _RecordingSession(rows)
    report = await _run(session, _StubS3(), after_pid=3)

    assert report.rows_scanned == 2


async def test_concurrency_yields_identical_counts() -> None:
    rows = [(pid, _UID_A, _single_turn(_PNG_URI, _JPG_URI)) for pid in range(1, 6)]
    sequential = await _run(_RecordingSession(rows), _StubS3(), concurrency=1)
    parallel = await _run(_RecordingSession(rows), _StubS3(), concurrency=4)

    assert (sequential.uploaded, sequential.eligible) == (parallel.uploaded, parallel.eligible)
    assert sequential.failed == parallel.failed == 0


# --- 10. 報表 -------------------------------------------------------------


async def test_report_text_contains_all_required_numbers() -> None:
    failing = _expected_key(_UID_B, 0, _GIF_BYTES, "image/gif")
    session = _RecordingSession(
        [(1, _UID_A, _single_turn(_PNG_URI)), (2, _UID_B, _messages(_GIF_URI))]
    )
    report = await _run(session, _StubS3(fail_puts={failing}))
    rendered = format_report(report, dry_run=False)

    assert "應上傳 N" in rendered
    assert "實際上傳 M" in rendered
    assert "已存在 K" in rendered
    assert "pid=2" in rendered


# --- 11. 真 DB:DB 零變更(必測)-----------------------------------------


def _new_uid() -> UUID:
    return UUID(str(uuid7()))


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


_FINGERPRINT_SQL = text(
    """
    SELECT count(*) AS rows,
           md5(coalesce(string_agg(
               pid::text || '|' ||
               coalesce(md5(request_content::text), '-') || '|' ||
               updated_at::text || '|' || xmin::text,
               E'\n' ORDER BY pid), '')) AS digest
    FROM usage_logs
    """
)


async def _fingerprint(session: AsyncSession) -> tuple[int, str]:
    """全表指紋:`request_content` + `updated_at` + `xmin`。

    why 也取 `xmin`:即使 UPDATE 寫回一模一樣的值,`xmin` 也會換成新的 txid ——
    有它才能證明「連一次寫入都沒發生」,而不只是「值看起來沒變」。
    """
    row = (await session.execute(_FINGERPRINT_SQL)).one()
    return int(row[0]), str(row[1])


async def _insert_row(session: AsyncSession, content: dict[str, object]) -> tuple[int, str]:
    uid = _new_uid()
    log = UsageLog(usage_log_uid=uid, model="openai/gpt-4o", status="success")
    log.request_content = content
    session.add(log)
    await session.flush()
    return log.pid, str(uid)


async def test_phase1_leaves_database_untouched(db_session: AsyncSession) -> None:
    """對真 DB 跑完 `--phase upload` 後,全表 `request_content` / `updated_at` 完全相同。"""
    max_pid = int((await db_session.execute(text("SELECT coalesce(max(pid), 0) FROM usage_logs"))).scalar_one())
    _, uid_a = await _insert_row(db_session, _single_turn(_PNG_URI, _JPG_URI))
    _, uid_b = await _insert_row(db_session, _messages(_GIF_URI))

    before = await _fingerprint(db_session)

    client = _StubS3()
    report = await run_upload(
        db_session,
        client=client,  # type: ignore[arg-type]
        key_prefix=_PREFIX,
        batch_size=10,
        after_pid=max_pid,
    )

    after = await _fingerprint(db_session)
    assert after == before, "Phase 1 不得改動 usage_logs 任何一列"

    assert report.rows_scanned == 2
    assert report.uploaded == 3
    assert [key for key, _, _ in client.puts] == [
        _expected_key(uid_a, 0, _PNG_BYTES, "image/png"),
        _expected_key(uid_a, 1, _JPG_BYTES, "image/jpeg"),
        _expected_key(uid_b, 0, _GIF_BYTES, "image/gif"),
    ]


async def test_real_db_scan_matches_like_filter(db_session: AsyncSession) -> None:
    """不含 base64 的列不該被撈進來(`::text LIKE` 粗篩 + 精確走訪的合力)。"""
    max_pid = int((await db_session.execute(text("SELECT coalesce(max(pid), 0) FROM usage_logs"))).scalar_one())
    await _insert_row(db_session, {"model": "openai/gpt-4o", "text": "純文字", "images": []})
    await _insert_row(db_session, _single_turn(_PNG_URI))

    report = await run_upload(
        db_session,
        client=_StubS3(),  # type: ignore[arg-type]
        key_prefix=_PREFIX,
        after_pid=max_pid,
    )

    assert report.rows_scanned == 1
    assert report.uploaded == 1


async def test_real_db_second_run_is_idempotent(db_session: AsyncSession) -> None:
    max_pid = int((await db_session.execute(text("SELECT coalesce(max(pid), 0) FROM usage_logs"))).scalar_one())
    await _insert_row(db_session, _single_turn(_PNG_URI, _JPG_URI))
    client = _StubS3()

    first = await run_upload(
        db_session, client=client, key_prefix=_PREFIX, after_pid=max_pid  # type: ignore[arg-type]
    )
    client.puts.clear()
    second = await run_upload(
        db_session, client=client, key_prefix=_PREFIX, after_pid=max_pid  # type: ignore[arg-type]
    )

    assert first.uploaded == 2
    assert client.puts == []
    assert second.uploaded == 0
    assert second.existing == 2


# ==========================================================================
# Phase 2(task-531):改寫 JSONB —— 本版唯一不可逆的操作
#
# 四條必守鐵律各自有專屬測試,標記為【必測】:
#   1. 安全網:`head_object` 回 False → 該列**未被改寫**且列入待處理清單。
#   2. `updated_at` 不跳動(真 DB 驗證,因為覆寫者是 DB trigger 而非 ORM)。
#   3. 只動附件:其他欄位 / 其他 JSON 節點逐欄比對無差異。
#   4. Phase 1 的唯讀交易設定不套用到 Phase 2(見 script `_run_rewrite` 自建 session)。
# ==========================================================================


async def _rewrite(
    session: _RewriteSession,
    client: _StubS3 | None,
    **kwargs: object,
) -> RewriteReport:
    return await run_rewrite(
        session,  # type: ignore[arg-type]
        client=client,  # type: ignore[arg-type]
        key_prefix=_PREFIX,
        **kwargs,  # type: ignore[arg-type]
    )


def _rich_single_turn(*images: str) -> dict[str, object]:
    """帶齊「不該被動到」的節點:文字 / 檔名 / tools / 生成參數。"""
    return {
        "model": "openai/gpt-4o",
        "text": "看圖說故事",
        "images": list(images),
        "files": ["spec.pdf"],
        "tools": [{"type": "function", "function": {"name": "web_search"}}],
        "temperature": 0.7,
        "max_tokens": 1024,
        "top_p": 0.95,
    }


def _image_values(content: dict[str, object]) -> list[str]:
    """走訪後的圖片值 —— 直接用 script 的走訪函式,序號規則自然一致。"""
    return [ref.value for ref in iter_image_attachments(content)]


# --- 12. 改寫結果:兩種快照形狀 ------------------------------------------


async def test_rewrite_replaces_base64_with_object_key_single_turn() -> None:
    key0 = _expected_key(_UID_A, 0, _PNG_BYTES, "image/png")
    key1 = _expected_key(_UID_A, 1, _JPG_BYTES, "image/jpeg")
    session = _RewriteSession([(1, _UID_A, _rich_single_turn(_PNG_URI, _JPG_URI))])
    report = await _rewrite(session, _StubS3(existing={key0, key1}))

    content = session.rows[1].content
    assert content["images"] == [key0, key1]
    assert "data:" not in json.dumps(content)
    assert (report.rewritten, report.rows_rewritten, report.remaining) == (2, 1, 0)


async def test_rewrite_replaces_base64_with_object_key_messages() -> None:
    key0 = _expected_key(_UID_B, 0, _JPG_BYTES, "image/jpeg")
    key1 = _expected_key(_UID_B, 1, _GIF_BYTES, "image/gif")
    session = _RewriteSession([(2, _UID_B, _messages(_JPG_URI, _GIF_URI))])
    report = await _rewrite(session, _StubS3(existing={key0, key1}))

    content = session.rows[2].content
    messages = content["messages"]
    assert isinstance(messages, list)
    parts = messages[1]["content"]
    assert parts[1]["image_url"]["url"] == key0
    assert parts[2]["image_url"]["url"] == key1
    # messages 的文字 / 檔案 part / system 訊息一律不動。
    assert parts[0] == {"type": "text", "text": "看圖"}
    assert parts[3] == {"type": "file", "file": {"filename": "spec.pdf"}}
    assert messages[0] == {"role": "system", "content": "you are a bot"}
    assert report.rewritten == 2


async def test_rewrite_only_touches_attachment_nodes() -> None:
    """【必測 3 · 單元層】改寫前後,`images` 以外的節點逐一比對相同。"""
    key0 = _expected_key(_UID_A, 0, _PNG_BYTES, "image/png")
    original = _rich_single_turn(_PNG_URI)
    session = _RewriteSession([(1, _UID_A, original)])
    await _rewrite(session, _StubS3(existing={key0}))

    after = session.rows[1].content
    for field_name, value in original.items():
        if field_name == "images":
            continue
        assert after[field_name] == value, f"節點 {field_name} 不該被改動"


async def test_rewrite_writes_exactly_the_keys_phase1_uploaded() -> None:
    """反漂移主測:Phase 2 寫進 DB 的字串 == Phase 1 實際 `put_object` 的 key。"""
    rows = [
        (1, _UID_A, _single_turn(_PNG_URI, _JPG_URI)),
        (2, _UID_B, _messages(_GIF_URI)),
    ]
    client = _StubS3()
    await _run(_RecordingSession(rows), client)
    uploaded = {key for key, _, _ in client.puts}

    session = _RewriteSession(rows)
    await _rewrite(session, client)

    written = {
        value for row in session.rows.values() for value in _image_values(row.content)
    }
    assert written == uploaded


# --- 13. 安全網(必測)----------------------------------------------------


async def test_rewrite_safety_net_skips_row_when_object_missing() -> None:
    """【必測 1】`head_object` 回 False → 該列未被改寫,且列入待處理清單。"""
    session = _RewriteSession([(1, _UID_A, _single_turn(_PNG_URI))])
    before = copy.deepcopy(session.rows[1].content)

    report = await _rewrite(session, _StubS3())  # existing 為空 → head_object 一律 False

    assert session.rows[1].content == before, "物件不存在時絕不可改寫"
    assert session.updates == [], "不得送出任何 UPDATE"
    assert (report.rewritten, report.rows_rewritten, report.rows_skipped) == (0, 0, 1)
    assert [(p.pid, p.reason) for p in report.pending] == [(1, "s3_object_missing")]
    assert report.pending[0].usage_log_uid == _UID_A


async def test_rewrite_missing_one_object_blocks_the_whole_row() -> None:
    """同列只要有一張沒搬成功,整列都不改 —— 避免半路徑半 base64 的中間態。"""
    key0 = _expected_key(_UID_A, 0, _PNG_BYTES, "image/png")
    session = _RewriteSession([(1, _UID_A, _single_turn(_PNG_URI, _JPG_URI))])
    before = copy.deepcopy(session.rows[1].content)

    report = await _rewrite(session, _StubS3(existing={key0}))

    assert session.rows[1].content == before
    assert session.updates == []
    assert report.rows_skipped == 1
    assert report.rewritten == 0


async def test_rewrite_head_failure_blocks_row() -> None:
    key0 = _expected_key(_UID_A, 0, _PNG_BYTES, "image/png")
    session = _RewriteSession([(1, _UID_A, _single_turn(_PNG_URI))])
    client = _StubS3(fail_heads={key0}, error=S3TimeoutError("S3 head_object 逾時"))

    report = await _rewrite(session, client)

    assert session.updates == []
    assert [p.reason for p in report.pending] == ["s3_head_failed"]


async def test_rewrite_without_client_writes_nothing() -> None:
    """取不到 S3 client = 無法驗證存在 → 一律列待處理,不盲寫路徑。"""
    session = _RewriteSession([(1, _UID_A, _single_turn(_PNG_URI))])

    report = await _rewrite(session, None)

    assert session.updates == []
    assert [p.reason for p in report.pending] == ["s3_unavailable"]


async def test_rewrite_config_error_aborts_immediately() -> None:
    key0 = _expected_key(_UID_A, 0, _PNG_BYTES, "image/png")
    session = _RewriteSession([(1, _UID_A, _single_turn(_PNG_URI))])
    client = _StubS3(fail_heads={key0}, error=S3ConfigError("S3 憑證未正確注入"))

    with pytest.raises(S3ConfigError):
        await _rewrite(session, client)
    assert session.updates == []


# --- 14. updated_at 與 trigger 停用 --------------------------------------


async def test_rewrite_preserves_updated_at_and_disables_trigger_first() -> None:
    """【必測 2 · 單元層】UPDATE 顯式帶原 `updated_at`,且 SET LOCAL 必須先送出。"""
    key0 = _expected_key(_UID_A, 0, _PNG_BYTES, "image/png")
    session = _RewriteSession([(1, _UID_A, _single_turn(_PNG_URI))])

    await _rewrite(session, _StubS3(existing={key0}))

    assert session.rows[1].updated_at == _FAKE_UPDATED_AT
    assert session.bypasses == 1
    assert session.updates[0]["updated_at"] == _FAKE_UPDATED_AT
    verbs = [sql.split()[0] for sql in session.statements]
    assert verbs.index("SET") < verbs.index("UPDATE"), "停用 trigger 的語句必須先於 UPDATE"


async def test_rewrite_aborts_when_trigger_bypass_is_denied() -> None:
    """無權停用 trigger → 直接中止,**不**降級去污染 `updated_at`。"""
    key0 = _expected_key(_UID_A, 0, _PNG_BYTES, "image/png")
    session = _RewriteSession([(1, _UID_A, _single_turn(_PNG_URI))], deny_bypass=True)

    with pytest.raises(RewritePreconditionError):
        await _rewrite(session, _StubS3(existing={key0}))

    assert session.updates == []
    assert session.rows[1].updated_at == _FAKE_UPDATED_AT


# --- 15. 冪等 / 中斷後重跑 / dry-run --------------------------------------


async def test_rewrite_second_run_processes_zero_rows() -> None:
    keys = {
        _expected_key(_UID_A, 0, _PNG_BYTES, "image/png"),
        _expected_key(_UID_A, 1, _JPG_BYTES, "image/jpeg"),
        _expected_key(_UID_B, 0, _GIF_BYTES, "image/gif"),
    }
    session = _RewriteSession(
        [(1, _UID_A, _single_turn(_PNG_URI, _JPG_URI)), (2, _UID_B, _messages(_GIF_URI))]
    )
    client = _StubS3(existing=keys)

    first = await _rewrite(session, client)
    second = await _rewrite(session, client)

    assert (first.rows_scanned, first.rewritten) == (2, 3)
    assert (second.rows_scanned, second.rewritten, second.eligible) == (0, 0, 0)
    assert second.remaining == 0


async def test_rewrite_resumes_after_interruption() -> None:
    """中斷後重跑:已改寫列不重做(掃不到)、未改寫列補完。"""
    keys = {_expected_key(uid, 0, _PNG_BYTES, "image/png") for uid in (_UID_A, _UID_B)}
    session = _RewriteSession(
        [
            (1, _UID_A, _single_turn(_PNG_URI)),
            (2, _UID_B, _single_turn(_PNG_URI)),
            (3, _UID_B, _single_turn(_PNG_URI)),
        ]
    )
    client = _StubS3(existing=keys)

    partial = await _rewrite(session, client, limit=1)
    rest = await _rewrite(session, client)

    assert (partial.rows_scanned, partial.rows_rewritten) == (1, 1)
    assert (rest.rows_scanned, rest.rows_rewritten) == (2, 2)
    assert all("data:" not in json.dumps(row.content) for row in session.rows.values())
    assert rest.remaining == 0


async def test_rewrite_dry_run_writes_nothing() -> None:
    key0 = _expected_key(_UID_A, 0, _PNG_BYTES, "image/png")
    key1 = _expected_key(_UID_A, 1, _JPG_BYTES, "image/jpeg")
    session = _RewriteSession([(1, _UID_A, _single_turn(_PNG_URI, _JPG_URI))])
    before = copy.deepcopy(session.rows[1].content)

    report = await _rewrite(session, _StubS3(existing={key0, key1}), dry_run=True)

    assert session.rows[1].content == before
    assert session.updates == []
    assert session.bypasses == 0
    assert session.commits == 0
    assert (report.planned, report.rewritten, report.eligible) == (2, 0, 2)


# --- 16. 遠端 URL / 畸形值 / 已是路徑 -------------------------------------


async def test_rewrite_leaves_remote_url_and_counts_slot() -> None:
    """遠端 URL 原樣保留,但仍佔序號 —— 圖片落在序號 1。"""
    key1 = _expected_key(_UID_A, 1, _PNG_BYTES, "image/png")
    content = _single_turn("https://cdn.example.com/a.png", _PNG_URI)
    session = _RewriteSession([(1, _UID_A, content)])

    report = await _rewrite(session, _StubS3(existing={key1}))

    assert session.rows[1].content["images"] == ["https://cdn.example.com/a.png", key1]
    assert (report.remote_skipped, report.rewritten) == (1, 1)


async def test_rewrite_malformed_value_does_not_block_other_attachments() -> None:
    """畸形值改不了(本來就沒內容可搬),但不該擋住同列其他附件;記入待處理清單。"""
    key1 = _expected_key(_UID_A, 1, _PNG_BYTES, "image/png")
    content = _single_turn("data:image/png;base64,@@@not-base64", _PNG_URI)
    session = _RewriteSession([(1, _UID_A, content)])

    report = await _rewrite(session, _StubS3(existing={key1}))

    assert session.rows[1].content["images"] == ["data:image/png;base64,@@@not-base64", key1]
    assert (report.invalid, report.rewritten, report.rows_rewritten) == (1, 1, 1)
    assert [p.reason for p in report.pending] == ["malformed_data_uri"]
    # 畸形值仍符合 LIKE 粗篩 → 收尾查詢不會歸零,須人工處理(runbook 有寫)。
    assert report.remaining == 1


async def test_rewrite_skips_values_that_are_already_paths() -> None:
    key0 = "test/legacy/whatever/0-deadbeefdeadbeef.png"
    key1 = _expected_key(_UID_A, 1, _JPG_BYTES, "image/jpeg")
    session = _RewriteSession([(1, _UID_A, _single_turn(key0, _JPG_URI))])

    report = await _rewrite(session, _StubS3(existing={key1}))

    assert session.rows[1].content["images"] == [key0, key1]
    assert (report.already_path, report.rewritten) == (1, 1)


# --- 17. 報表 -------------------------------------------------------------


async def test_rewrite_report_text_contains_required_numbers() -> None:
    session = _RewriteSession(
        [(1, _UID_A, _single_turn(_PNG_URI)), (2, _UID_B, _messages(_GIF_URI))]
    )
    report = await _rewrite(
        session, _StubS3(existing={_expected_key(_UID_A, 0, _PNG_BYTES, "image/png")})
    )
    rendered = format_rewrite_report(report, dry_run=False)

    assert "可改寫 N" in rendered
    assert "實際改寫 M" in rendered
    assert "整列跳過(安全網)" in rendered
    assert "剩餘含 base64 列數" in rendered
    assert "pid=2" in rendered
    assert "s3_object_missing" in rendered


# --- 18. 真 DB:updated_at / 其他欄位 / 完成判準(必測)------------------

# why 用 raw INSERT 而不是 ORM:本組測試需要「三天前」的 `updated_at`。
# `usage_logs` 掛著 BEFORE UPDATE trigger,任何 UPDATE 都會把它推成 NOW();而若拿同一
# 交易內剛 INSERT 的列來測,原值本來就等於 NOW(),trigger 有沒有被停用**測不出差別**
# (實測過:那樣寫的斷言即使 trigger 全開也會過)。INSERT 不觸發該 trigger,故可塞舊值。
_INSERT_LEGACY_SQL = text(
    """
    INSERT INTO usage_logs (
        usage_log_uid, model, prompt_tokens, completion_tokens, total_tokens,
        cost_usd, latency_ms, status, error_code, request_content, response_summary,
        openrouter_generation_id, used_tools, is_active, is_deleted, created_at, updated_at
    ) VALUES (
        CAST(:uid AS uuid), :model, :prompt_tokens, :completion_tokens, :total_tokens,
        :cost_usd, :latency_ms, :status, :error_code, CAST(:request_content AS jsonb),
        CAST(:response_summary AS jsonb), :generation_id, :used_tools, true, false,
        :created_at, :updated_at
    )
    RETURNING pid, updated_at
    """
)


async def _insert_legacy_row(
    session: AsyncSession, content: dict[str, object]
) -> tuple[int, str, datetime]:
    uid = str(_new_uid())
    aged = datetime.now(UTC) - timedelta(days=3)
    row = (
        await session.execute(
            _INSERT_LEGACY_SQL.bindparams(
                uid=uid,
                model="openai/gpt-4o",
                prompt_tokens=11,
                completion_tokens=22,
                total_tokens=33,
                cost_usd=Decimal("0.001234"),
                latency_ms=456,
                status="success",
                error_code=None,
                request_content=json.dumps(content, ensure_ascii=False),
                response_summary=json.dumps({"text": "回覆摘要"}, ensure_ascii=False),
                generation_id="gen-abc123",
                used_tools=True,
                created_at=aged,
                updated_at=aged,
            )
        )
    ).one()
    return int(row[0]), uid, row[1]


async def _row_snapshot(session: AsyncSession, pid: int) -> dict[str, object]:
    """整列全欄位快照(含 `request_content`),用來做逐欄比對。"""
    row = (
        await session.execute(
            text("SELECT * FROM usage_logs WHERE pid = :pid").bindparams(pid=pid)
        )
    ).one()
    return dict(row._mapping)


async def _max_pid(session: AsyncSession) -> int:
    return int(
        (await session.execute(text("SELECT coalesce(max(pid), 0) FROM usage_logs"))).scalar_one()
    )


async def _scoped_base64_rows(session: AsyncSession, after_pid: int) -> int:
    """本測試自己插入的列裡,還有幾列含 base64(dev DB 既有資料不入帳)。"""
    return int(
        (
            await session.execute(
                text(
                    "SELECT count(*) FROM usage_logs "
                    "WHERE pid > :after_pid AND request_content::text LIKE :pattern"
                ).bindparams(after_pid=after_pid, pattern="%data:%base64,%")
            )
        ).scalar_one()
    )


@pytest_asyncio.fixture
async def writable_db_session() -> AsyncIterator[AsyncSession]:
    """Phase 2 專用的真 DB session:外層 transaction + **SAVEPOINT** 加入模式。

    why 不共用 Phase 1 的 `db_session`:Phase 2 會自己 `commit()` / `rollback()`
    (每批一個 transaction)。預設的 `conditional_savepoint` 加入模式下,session 的
    `rollback()` 會把測試前置插入的資料一起清掉(實測過);`create_savepoint` 才有
    「commit 只釋放 savepoint、rollback 不越界」的語意。測試結束仍由外層 transaction
    整批 rollback,dev DB 不會留下任何資料。
    """
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=None)
    try:
        conn = await engine.connect()
    except (OSError, OperationalError) as exc:  # pragma: no cover - 環境相依
        await engine.dispose()
        pytest.skip(f"測試 DB 無法連線({TEST_DATABASE_URL}):{exc}")

    trans = await conn.begin()
    session = AsyncSession(
        bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    try:
        yield session
    finally:
        await session.close()
        if trans.is_active:
            await trans.rollback()
        await conn.close()
        await engine.dispose()


async def test_rewrite_real_db_preserves_updated_at_and_other_columns(
    writable_db_session: AsyncSession,
) -> None:
    """【必測 2 + 必測 3】真 DB 改寫後:`updated_at` 未變、其餘欄位逐欄相同。"""
    max_pid = await _max_pid(writable_db_session)
    pid, uid, aged = await _insert_legacy_row(writable_db_session, _rich_single_turn(_PNG_URI, _JPG_URI))
    await writable_db_session.commit()
    before = await _row_snapshot(writable_db_session, pid)

    keys = [
        _expected_key(uid, 0, _PNG_BYTES, "image/png"),
        _expected_key(uid, 1, _JPG_BYTES, "image/jpeg"),
    ]
    report = await run_rewrite(
        writable_db_session,
        client=_StubS3(existing=set(keys)),  # type: ignore[arg-type]
        key_prefix=_PREFIX,
        after_pid=max_pid,
    )
    after = await _row_snapshot(writable_db_session, pid)

    assert report.rewritten == 2
    # 必測 2:updated_at 完全相同(且確實還是三天前那個值,不是被推到今天)。
    assert after["updated_at"] == before["updated_at"] == aged

    # 必測 3:request_content 以外的欄位逐欄比對。
    for column, value in before.items():
        if column == "request_content":
            continue
        assert after[column] == value, f"欄位 {column} 不該被遷移改動"

    # request_content 內部:只有 images 變,其餘節點(text / tools / 生成參數 / files)不變。
    before_content = before["request_content"]
    after_content = after["request_content"]
    assert isinstance(before_content, dict) and isinstance(after_content, dict)
    for node, value in before_content.items():
        if node == "images":
            continue
        assert after_content[node] == value, f"節點 {node} 不該被遷移改動"
    assert after_content["images"] == keys


async def test_rewrite_real_db_safety_net_leaves_row_untouched(writable_db_session: AsyncSession) -> None:
    """【必測 1】真 DB 上刻意讓 `head_object` 回 False → 整列一個 byte 都沒動。"""
    max_pid = await _max_pid(writable_db_session)
    pid, _, _ = await _insert_legacy_row(writable_db_session, _rich_single_turn(_PNG_URI))
    await writable_db_session.commit()
    before = await _row_snapshot(writable_db_session, pid)

    report = await run_rewrite(
        writable_db_session,
        client=_StubS3(),  # type: ignore[arg-type]
        key_prefix=_PREFIX,
        after_pid=max_pid,
    )
    after = await _row_snapshot(writable_db_session, pid)

    assert after == before, "物件不存在時該列必須原封不動"
    assert (report.rewritten, report.rows_skipped) == (0, 1)
    assert [p.reason for p in report.pending] == ["s3_object_missing"]


async def test_rewrite_real_db_completion_criterion_is_zero(writable_db_session: AsyncSession) -> None:
    """完成判準:改寫後本批列已無 `data:...base64,`。"""
    max_pid = await _max_pid(writable_db_session)
    pid_a, uid_a, _ = await _insert_legacy_row(writable_db_session, _single_turn(_PNG_URI, _JPG_URI))
    pid_b, uid_b, _ = await _insert_legacy_row(writable_db_session, _messages(_GIF_URI))
    await writable_db_session.commit()

    keys = {
        _expected_key(uid_a, 0, _PNG_BYTES, "image/png"),
        _expected_key(uid_a, 1, _JPG_BYTES, "image/jpeg"),
        _expected_key(uid_b, 0, _GIF_BYTES, "image/gif"),
    }
    report = await run_rewrite(
        writable_db_session,
        client=_StubS3(existing=keys),  # type: ignore[arg-type]
        key_prefix=_PREFIX,
        after_pid=max_pid,
    )

    assert report.rewritten == 3
    assert report.pending == []
    assert await _scoped_base64_rows(writable_db_session, max_pid) == 0
    after_a = await _row_snapshot(writable_db_session, pid_a)
    after_b = await _row_snapshot(writable_db_session, pid_b)
    assert set(_image_values(after_a["request_content"])) <= keys  # type: ignore[arg-type]
    assert set(_image_values(after_b["request_content"])) <= keys  # type: ignore[arg-type]


async def test_rewrite_real_db_dry_run_writes_nothing(writable_db_session: AsyncSession) -> None:
    max_pid = await _max_pid(writable_db_session)
    pid, uid, _ = await _insert_legacy_row(writable_db_session, _rich_single_turn(_PNG_URI))
    await writable_db_session.commit()
    before = await _row_snapshot(writable_db_session, pid)

    report = await run_rewrite(
        writable_db_session,
        client=_StubS3(existing={_expected_key(uid, 0, _PNG_BYTES, "image/png")}),  # type: ignore[arg-type]
        key_prefix=_PREFIX,
        after_pid=max_pid,
        dry_run=True,
    )
    after = await _row_snapshot(writable_db_session, pid)

    assert after == before, "dry-run 不得寫入任何東西"
    assert (report.planned, report.rewritten) == (1, 0)


async def test_rewrite_real_db_second_run_processes_zero_rows(writable_db_session: AsyncSession) -> None:
    max_pid = await _max_pid(writable_db_session)
    _, uid, _ = await _insert_legacy_row(writable_db_session, _single_turn(_PNG_URI))
    await writable_db_session.commit()
    client = _StubS3(existing={_expected_key(uid, 0, _PNG_BYTES, "image/png")})

    first = await run_rewrite(
        writable_db_session, client=client, key_prefix=_PREFIX, after_pid=max_pid  # type: ignore[arg-type]
    )
    second = await run_rewrite(
        writable_db_session, client=client, key_prefix=_PREFIX, after_pid=max_pid  # type: ignore[arg-type]
    )

    assert (first.rows_scanned, first.rewritten) == (1, 1)
    assert (second.rows_scanned, second.rewritten) == (0, 0)
