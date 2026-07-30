"""遷移 script(`scripts/migrate_base64_to_s3.py`)測試。

守五件事:

1. **key 與 task-524 一致且帶日期資料夾**:script 產出的 key 必須等於直接呼叫
   `build_object_key(scope="chat", occurred_at=<該列 created_at>, ...)` 的結果 ——
   日期取自「當初那筆紀錄的建立時間」,不是遷移執行日。
2. **上傳成功才改寫**;同一列有任何附件沒搬成功 → **整列**不改寫(不留半路徑半 base64)。
3. **只動附件節點**:其他欄位 / 其他 JSON 節點逐一比對無差異,`updated_at` 不跳動。
4. **冪等**:重跑不重傳、不重寫;已是路徑的值直接跳過。
5. **掃描不篩內容**:以 `pid` 由舊到新整批撈,沒有 base64 的列也會被掃過(這是「每批都有
   進度輸出、查詢不會卡住」的前提)。

S3 一律 stub、**不打真 AWS**(`09-object-storage.md` § 測試)。

DB 這一層分兩種測法,理由寫在這裡免得被誤讀為違反「禁 mock SQL」:

- 多數案例用 `_MemSession` 這個記憶體替身。它測的**不是** SQL 語意,而是 script 自身的
  走訪 / 冪等 / 報表 / **「到底送出了哪些語句、順序如何」** —— 例如「停用 trigger 的語句
  必須先於 UPDATE」只有攔截語句才驗得到。
- `updated_at` 不跳動與「只動附件」另有真 DB 整合測試把關:覆寫者是 **DB trigger** 而非
  ORM,替身驗不了。DB 不可用時 skip(對齊 `tests/repositories/*` 慣例)。
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
from app.services.attachment import build_object_key, content_type_for_mime

# `backend/scripts` 不是 package(無 `__init__.py`),故先掛上 sys.path 再以**頂層模組名**
# import。why 不寫 `from scripts.migrate_base64_to_s3 import ...`:那會讓同一個檔在
# `uv run mypy .` 下同時被認成 `migrate_base64_to_s3` 與 `scripts.migrate_base64_to_s3`,
# mypy 以 "Source file found twice" 直接中止,全庫型別檢查等於停擺。
sys.path.append(str(Path(__file__).resolve().parents[2] / "scripts"))

from migrate_base64_to_s3 import (  # noqa: E402
    MigrationPreconditionError,
    MigrationReport,
    _parse_args,
    format_report,
    iter_image_attachments,
    migration_object_key,
    run_migration,
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


def _uid_for(pid: int) -> str:
    """每列一個不同的 uid。key 含 uid,同 uid + 同內容會算出同一把 key。"""
    return f"01920000-0000-7000-8000-{pid:012d}"


# 該列「當初的建立時間」—— 日期資料夾取自它。08:30 UTC = 16:30 台北,同一日曆日,
# 不會因為時區換算而落在相鄰日期,斷言才不會有模糊空間。
_CREATED_AT = datetime(2026, 3, 5, 8, 30, tzinfo=UTC)
# 掃描時讀到的 `updated_at` 原值,與「trigger 若沒被停用會寫進去的值」。
_UPDATED_AT = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)
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


def _no_image() -> dict[str, object]:
    return {"model": "openai/gpt-4o", "text": "純文字", "images": []}


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


class _MemRow:
    __slots__ = ("content", "created_at", "pid", "uid", "updated_at")

    def __init__(self, pid: int, uid: str, content: dict[str, object]) -> None:
        self.pid = pid
        self.uid = uid
        self.content = copy.deepcopy(content)
        self.created_at = _CREATED_AT
        self.updated_at = _UPDATED_AT


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


class _MemSession:
    """記憶體 session 替身:掃描 / `max(pid)` / `jsonb_set` UPDATE。

    刻意**模擬 DB trigger** `trg_usage_logs_updated_at`:同一個交易內若沒先送出
    `SET LOCAL session_replication_role = replica`,UPDATE 就會把 `updated_at` 推成
    `_TRIGGER_NOW`。這讓「停用 trigger 的語句必須先送」在單元層就測得到;真 DB 的行為
    另有整合測試把關。
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

        if sql.startswith("SELECT max(pid)"):
            capped = [r.pid for r in self.rows.values() if r.pid <= int(params["before_pid"])]
            return _FakeResult([(max(capped) if capped else None,)])

        if sql.startswith("SELECT pid"):
            after_pid = int(params["after_pid"])
            before_pid = int(params["before_pid"])
            batch_size = int(params["batch_size"])
            picked = [
                row
                for row in sorted(self.rows.values(), key=lambda r: r.pid)
                if after_pid < row.pid <= before_pid
            ]
            return _FakeResult(
                [
                    (row.pid, row.uid, copy.deepcopy(row.content), row.created_at, row.updated_at)
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


def _expected_key(uid: str, index: int, content: bytes, mime: str) -> str:
    """直接呼叫 task-524 的函式算 key —— 用來對照 script 的產出。"""
    return build_object_key(
        scope="chat",
        owner_uid=uid,
        index=index,
        content=content,
        mime=mime,
        key_prefix=_PREFIX,
        occurred_at=_CREATED_AT,
    )


async def _run(
    session: _MemSession,
    client: _StubS3 | None,
    **kwargs: object,
) -> MigrationReport:
    return await run_migration(
        session,  # type: ignore[arg-type]
        client=client,  # type: ignore[arg-type]
        key_prefix=_PREFIX,
        **kwargs,  # type: ignore[arg-type]
    )


def _image_values(content: dict[str, object]) -> list[str]:
    """走訪後的圖片值 —— 直接用 script 的走訪函式,序號規則自然一致。"""
    return [ref.value for ref in iter_image_attachments(content)]


# --- 0. CLI ---------------------------------------------------------------


def test_cli_needs_no_mode_flag() -> None:
    """單一流程,不再有 --upload / --delete;直接跑就是全做。"""
    args = _parse_args([])
    assert (args.dry_run, args.batch_size, args.limit) == (False, 50, 0)
    assert _parse_args(["--dry-run"]).dry_run is True


# --- 1. 走訪:兩種快照形狀與序號規則 -------------------------------------


def test_iter_covers_single_turn_shape() -> None:
    refs = list(iter_image_attachments(_single_turn(_PNG_URI, _JPG_URI)))
    assert [r.index for r in refs] == [0, 1]
    assert [r.path for r in refs] == [("images", 0), ("images", 1)]
    assert [r.value for r in refs] == [_PNG_URI, _JPG_URI]


def test_iter_covers_messages_shape() -> None:
    refs = list(iter_image_attachments(_messages(_PNG_URI, _JPG_URI)))
    assert [r.index for r in refs] == [0, 1]
    # path 指到可直接寫回的字串節點。
    assert refs[0].path == ("messages", 1, "content", 1, "image_url", "url")
    assert refs[1].path == ("messages", 1, "content", 2, "image_url", "url")


def test_iter_index_counts_every_slot_including_remote_and_malformed() -> None:
    """序號代表「位置」,遠端 URL 與畸形值同樣佔號 —— 否則重跑時序號會整排位移。"""
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
            {
                "role": "user",
                "content": [{"type": "image_url"}, {"type": "image_url", "image_url": {}}],
            },
        ],
    }
    assert [r.value for r in iter_image_attachments(content)] == ["ok"]


def test_iter_skips_files_without_content() -> None:
    """歷史 `files` 只有檔名、從未留過內容 → 不走訪、不佔序號(§D.3)。"""
    content: dict[str, object] = {"images": [_PNG_URI], "files": ["spec.pdf"]}
    assert len(list(iter_image_attachments(content))) == 1


# --- 2. key:日期資料夾取自該列 created_at --------------------------------


def test_key_uses_created_at_date_folders() -> None:
    key = migration_object_key(
        usage_log_uid=_UID_A,
        index=3,
        content=_PNG_BYTES,
        mime="image/png",
        key_prefix=_PREFIX,
        occurred_at=_CREATED_AT,
    )
    assert key == _expected_key(_UID_A, 3, _PNG_BYTES, "image/png")
    assert key.startswith(f"{_PREFIX}/chat/2026/03/05/{_UID_A}/3-")
    assert key.endswith(".png")


async def test_uploaded_key_uses_the_rows_own_date() -> None:
    """兩列不同日期 → 各自落在自己那天的資料夾,不是遷移執行日。"""
    session = _MemSession([(1, _UID_A, _single_turn(_PNG_URI))])
    session.rows[1].created_at = datetime(2025, 12, 31, 20, 0, tzinfo=UTC)  # 台北時間隔天
    client = _StubS3()
    await _run(session, client)

    key = client.puts[0][0]
    assert key.startswith(f"{_PREFIX}/chat/2026/01/01/{_UID_A}/0-")


async def test_uploaded_key_matches_task_524_function() -> None:
    """script 實際上傳用的 key 必須與直接呼叫 524 的結果逐字相同。"""
    session = _MemSession([(1, _UID_A, _single_turn(_PNG_URI, _JPG_URI))])
    client = _StubS3()
    await _run(session, client)

    assert [key for key, _, _ in client.puts] == [
        _expected_key(_UID_A, 0, _PNG_BYTES, "image/png"),
        _expected_key(_UID_A, 1, _JPG_BYTES, "image/jpeg"),
    ]


async def test_upload_body_and_content_type_come_from_whitelist() -> None:
    session = _MemSession([(1, _UID_A, _single_turn(_PNG_URI))])
    client = _StubS3()
    await _run(session, client)

    key, body, content_type = client.puts[0]
    assert body == _PNG_BYTES
    assert content_type == content_type_for_mime("image/png") == "image/png"
    assert key.endswith(".png")


# --- 3. 一趟走完:上傳 + 改寫 --------------------------------------------


async def test_uploads_and_rewrites_in_one_pass_single_turn() -> None:
    key0 = _expected_key(_UID_A, 0, _PNG_BYTES, "image/png")
    key1 = _expected_key(_UID_A, 1, _JPG_BYTES, "image/jpeg")
    session = _MemSession([(1, _UID_A, _rich_single_turn(_PNG_URI, _JPG_URI))])
    client = _StubS3()

    report = await _run(session, client)

    assert [k for k, _, _ in client.puts] == [key0, key1]
    assert session.rows[1].content["images"] == [key0, key1]
    assert "data:" not in json.dumps(session.rows[1].content)
    assert (report.uploaded, report.rewritten, report.rows_rewritten) == (2, 2, 1)
    assert report.still_base64 == 0


async def test_uploads_and_rewrites_in_one_pass_messages() -> None:
    key0 = _expected_key(_UID_B, 0, _JPG_BYTES, "image/jpeg")
    key1 = _expected_key(_UID_B, 1, _GIF_BYTES, "image/gif")
    session = _MemSession([(2, _UID_B, _messages(_JPG_URI, _GIF_URI))])

    report = await _run(session, _StubS3())

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


async def test_only_attachment_nodes_are_touched() -> None:
    """改寫前後,`images` 以外的節點逐一比對相同。"""
    original = _rich_single_turn(_PNG_URI)
    session = _MemSession([(1, _UID_A, original)])
    await _run(session, _StubS3())

    after = session.rows[1].content
    for field_name, value in original.items():
        if field_name == "images":
            continue
        assert after[field_name] == value, f"節點 {field_name} 不該被改動"


# --- 4. 掃描:不篩內容,由舊到新 ------------------------------------------


async def test_scan_covers_rows_without_base64() -> None:
    """沒有 base64 的列也會被掃過(這是每批都有進度輸出的前提),但不會被改寫。"""
    session = _MemSession(
        [
            (1, _UID_A, _no_image()),
            (2, _UID_B, _single_turn(_PNG_URI)),
            (3, _uid_for(3), _no_image()),
        ]
    )
    report = await _run(session, _StubS3())

    assert report.rows_scanned == 3
    assert report.rows_with_base64 == 1
    assert report.rows_rewritten == 1
    assert session.rows[1].content == _no_image()


async def test_scan_sends_no_content_filter() -> None:
    """掃描語句不得帶 `LIKE '%data:%base64,%'` —— 那會讓查詢卡住不返回。"""
    session = _MemSession([(1, _UID_A, _single_turn(_PNG_URI))])
    await _run(session, _StubS3())

    scans = [s for s in session.statements if s.startswith("SELECT pid")]
    assert scans, "至少要送出一條掃描語句"
    assert all("LIKE" not in s for s in scans)


async def test_scan_processes_oldest_first() -> None:
    """由 pid 小到大 = 由舊到新。"""
    rows = [(pid, _uid_for(pid), _single_turn(_PNG_URI)) for pid in (3, 1, 2)]
    client = _StubS3()
    await _run(_MemSession(rows), client, batch_size=1)

    uploaded_uids = [key.split("/")[-2] for key, _, _ in client.puts]
    assert uploaded_uids == [_uid_for(1), _uid_for(2), _uid_for(3)]


async def test_cursor_batching_covers_all_rows() -> None:
    rows = [(pid, _uid_for(pid), _single_turn(_PNG_URI)) for pid in range(1, 8)]
    session = _MemSession(rows)
    report = await _run(session, _StubS3(), batch_size=2)

    assert report.rows_scanned == 7
    assert report.rows_rewritten == 7


async def test_limit_stops_early() -> None:
    rows = [(pid, _uid_for(pid), _single_turn(_PNG_URI)) for pid in range(1, 11)]
    report = await _run(_MemSession(rows), _StubS3(), batch_size=3, limit=4)

    assert report.rows_scanned == 4


async def test_after_pid_resumes_and_last_pid_is_reported() -> None:
    rows = [(pid, _uid_for(pid), _single_turn(_PNG_URI)) for pid in range(1, 6)]
    report = await _run(_MemSession(rows), _StubS3(), after_pid=3)

    assert (report.rows_scanned, report.last_pid) == (2, 5)
    assert "--after-pid 5" in format_report(report, dry_run=False)


async def test_pid_windows_cover_every_row_exactly_once() -> None:
    """`--before-pid X` 與下一窗 `--after-pid X` 接軌,不重不漏。"""
    rows = [(pid, _uid_for(pid), _single_turn(_PNG_URI)) for pid in range(1, 11)]
    client = _StubS3()

    first = await _run(_MemSession(rows), client, before_pid=4)
    second = await _run(_MemSession(rows), client, after_pid=4, before_pid=8)
    third = await _run(_MemSession(rows), client, after_pid=8)

    assert (first.rows_scanned, second.rows_scanned, third.rows_scanned) == (4, 4, 2)
    assert first.uploaded + second.uploaded + third.uploaded == len(rows)
    assert len(client.puts) == len(rows)


async def test_transaction_is_released_after_each_read() -> None:
    """讀完立刻放掉交易,不帶著它去打 S3(長交易會壓住 xmin horizon)。"""
    session = _MemSession([(pid, _uid_for(pid), _no_image()) for pid in range(1, 5)])
    await _run(session, _StubS3(), batch_size=2)

    assert session.rollbacks >= 2


# --- 5. 安全網:沒搬成功就不改寫 ------------------------------------------


async def test_upload_failure_blocks_the_whole_row() -> None:
    """同列只要有一張沒搬成功,整列都不改 —— 避免半路徑半 base64 的中間態。"""
    failing = _expected_key(_UID_A, 0, _PNG_BYTES, "image/png")
    session = _MemSession([(1, _UID_A, _single_turn(_PNG_URI, _JPG_URI))])
    before = copy.deepcopy(session.rows[1].content)

    report = await _run(session, _StubS3(fail_puts={failing}))

    assert session.rows[1].content == before, "上傳失敗時該列必須原封不動"
    assert session.updates == [], "不得送出任何 UPDATE"
    assert (report.rewritten, report.rows_rewritten, report.rows_skipped) == (0, 0, 1)
    assert [(p.pid, p.reason) for p in report.pending] == [(1, "s3_upload_failed")]
    assert report.still_base64 == 1


async def test_head_failure_blocks_the_row() -> None:
    failing = _expected_key(_UID_A, 0, _PNG_BYTES, "image/png")
    session = _MemSession([(1, _UID_A, _single_turn(_PNG_URI))])
    client = _StubS3(fail_heads={failing}, error=S3TimeoutError("S3 head_object 逾時"))

    report = await _run(session, client)

    assert session.updates == []
    assert [p.reason for p in report.pending] == ["s3_head_failed"]


async def test_one_row_failing_does_not_stop_the_batch() -> None:
    failing = _expected_key(_UID_A, 0, _PNG_BYTES, "image/png")
    session = _MemSession(
        [(1, _UID_A, _single_turn(_PNG_URI)), (2, _UID_B, _single_turn(_GIF_URI))]
    )

    report = await _run(session, _StubS3(fail_puts={failing}))

    assert report.rows_skipped == 1
    assert report.rows_rewritten == 1
    assert session.rows[2].content["images"] == [_expected_key(_UID_B, 0, _GIF_BYTES, "image/gif")]


async def test_unexpected_exception_does_not_break_the_batch() -> None:
    class _Boom(_StubS3):
        attempts = 0

        async def put_object(self, key: str, body: bytes, content_type: str) -> None:
            _Boom.attempts += 1
            if _Boom.attempts == 1:
                raise RuntimeError("boto3 內部爆炸")
            await super().put_object(key, body, content_type)

    session = _MemSession(
        [(1, _UID_A, _single_turn(_PNG_URI)), (2, _UID_B, _single_turn(_GIF_URI))]
    )
    report = await _run(session, _Boom())

    assert [p.detail for p in report.pending] == ["RuntimeError"]
    assert report.rows_rewritten == 1


async def test_config_error_aborts_immediately() -> None:
    """憑證 / bucket 設定錯每列都會重演,續跑只會刷出滿版失敗清單 → 直接中止。"""
    session = _MemSession([(1, _UID_A, _single_turn(_PNG_URI, _JPG_URI))])
    client = _StubS3(
        fail_heads={_expected_key(_UID_A, 0, _PNG_BYTES, "image/png")},
        error=S3ConfigError("S3 憑證未正確注入:NoCredentialsError"),
    )
    with pytest.raises(S3ConfigError):
        await _run(session, client)
    assert client.puts == []
    assert session.updates == []


async def test_without_client_writes_nothing() -> None:
    """取不到 S3 client = 無法確認物件存在 → 一律列待處理,不盲寫路徑。"""
    session = _MemSession([(1, _UID_A, _single_turn(_PNG_URI))])

    report = await _run(session, None, dry_run=True)

    assert session.updates == []
    assert [p.reason for p in report.pending] == ["s3_unavailable"]


# --- 6. 冪等 --------------------------------------------------------------


async def test_second_run_uploads_and_rewrites_nothing() -> None:
    rows = [(1, _UID_A, _single_turn(_PNG_URI, _JPG_URI)), (2, _UID_B, _messages(_GIF_URI))]
    session = _MemSession(rows)
    client = _StubS3()

    first = await _run(session, client)
    client.puts.clear()
    second = await _run(session, client)

    assert (first.uploaded, first.rewritten) == (3, 3)
    assert client.puts == []
    assert (second.uploaded, second.rewritten) == (0, 0)
    # 第二趟仍會掃過同樣的列(掃描不篩內容),但值已是路徑 → 全數略過。
    assert (second.rows_scanned, second.already_path) == (2, 3)
    assert second.still_base64 == 0


async def test_existing_object_is_not_reuploaded_but_still_rewritten() -> None:
    """物件已在 S3(前一趟傳過但沒改寫成功)→ 不重傳,但這次要把值改寫掉。"""
    key0 = _expected_key(_UID_A, 0, _PNG_BYTES, "image/png")
    session = _MemSession([(1, _UID_A, _single_turn(_PNG_URI))])
    client = _StubS3(existing={key0})

    report = await _run(session, client)

    assert client.puts == []
    assert (report.existing, report.uploaded, report.rewritten) == (1, 0, 1)
    assert session.rows[1].content["images"] == [key0]


async def test_resumes_after_interruption() -> None:
    """中斷後重跑:已改寫的列略過、未改寫的列補完。"""
    session = _MemSession([(pid, _uid_for(pid), _single_turn(_PNG_URI)) for pid in range(1, 4)])
    client = _StubS3()

    partial = await _run(session, client, limit=1)
    rest = await _run(session, client, after_pid=partial.last_pid)

    assert (partial.rows_scanned, partial.rows_rewritten) == (1, 1)
    assert (rest.rows_scanned, rest.rows_rewritten) == (2, 2)
    assert all("data:" not in json.dumps(row.content) for row in session.rows.values())


# --- 7. updated_at 與 trigger 停用 ----------------------------------------


async def test_preserves_updated_at_and_disables_trigger_first() -> None:
    """UPDATE 顯式帶原 `updated_at`,且 SET LOCAL 必須先送出。"""
    session = _MemSession([(1, _UID_A, _single_turn(_PNG_URI))])

    await _run(session, _StubS3())

    assert session.rows[1].updated_at == _UPDATED_AT
    assert session.bypasses == 1
    assert session.updates[0]["updated_at"] == _UPDATED_AT
    verbs = [sql.split()[0] for sql in session.statements]
    assert verbs.index("SET") < verbs.index("UPDATE"), "停用 trigger 的語句必須先於 UPDATE"


async def test_aborts_when_trigger_bypass_is_denied() -> None:
    """無權停用 trigger → 直接中止,**不**降級去污染 `updated_at`。"""
    session = _MemSession([(1, _UID_A, _single_turn(_PNG_URI))], deny_bypass=True)

    with pytest.raises(MigrationPreconditionError):
        await _run(session, _StubS3())

    assert session.updates == []
    assert session.rows[1].updated_at == _UPDATED_AT


async def test_no_empty_transaction_when_batch_has_nothing_to_write() -> None:
    session = _MemSession([(1, _UID_A, _no_image())])
    await _run(session, _StubS3())

    assert session.bypasses == 0
    assert session.commits == 0


# --- 8. dry-run -----------------------------------------------------------


async def test_dry_run_uploads_nothing_and_writes_nothing() -> None:
    session = _MemSession([(1, _UID_A, _single_turn(_PNG_URI, _JPG_URI))])
    before = copy.deepcopy(session.rows[1].content)
    client = _StubS3()

    report = await _run(session, client, dry_run=True)

    assert client.puts == []
    assert session.rows[1].content == before
    assert session.updates == []
    assert session.commits == 0
    assert (report.planned, report.uploaded, report.rewritten) == (2, 0, 0)
    assert "dry-run" in format_report(report, dry_run=True)


# --- 9. 遠端 URL / 畸形值 -------------------------------------------------


async def test_remote_url_is_left_alone_and_still_takes_a_slot() -> None:
    key1 = _expected_key(_UID_A, 1, _PNG_BYTES, "image/png")
    session = _MemSession([(1, _UID_A, _single_turn("https://cdn.example.com/a.png", _PNG_URI))])

    report = await _run(session, _StubS3())

    assert session.rows[1].content["images"] == ["https://cdn.example.com/a.png", key1]
    assert (report.remote_skipped, report.rewritten) == (1, 1)


async def test_malformed_value_does_not_block_other_attachments() -> None:
    """畸形值改不了(本來就沒內容可搬),但不該擋住同列其他附件;記入待處理清單。"""
    key1 = _expected_key(_UID_A, 1, _PNG_BYTES, "image/png")
    malformed = "data:image/png;base64,@@@not-base64"
    session = _MemSession([(1, _UID_A, _single_turn(malformed, _PNG_URI))])

    report = await _run(session, _StubS3())

    assert session.rows[1].content["images"] == [malformed, key1]
    assert (report.invalid, report.rewritten, report.rows_rewritten) == (1, 1, 1)
    assert [p.reason for p in report.pending] == ["malformed_data_uri"]
    # 畸形值仍是 `data:` 開頭 → 「仍含 base64」不會歸零,須人工處理。
    assert report.still_base64 == 1


# --- 10. 報表 -------------------------------------------------------------


async def test_report_text_contains_required_numbers() -> None:
    failing = _expected_key(_UID_B, 0, _GIF_BYTES, "image/gif")
    session = _MemSession([(1, _UID_A, _single_turn(_PNG_URI)), (2, _UID_B, _messages(_GIF_URI))])
    report = await _run(session, _StubS3(fail_puts={failing}))
    rendered = format_report(report, dry_run=False)

    assert "上傳 S3" in rendered
    assert "改寫成路徑" in rendered
    assert "整列跳過(安全網)" in rendered
    assert "仍含 base64 列數" in rendered
    assert "pid=2" in rendered
    assert "s3_upload_failed" in rendered


# --- 11. 真 DB(必測)-----------------------------------------------------


def _new_uid() -> UUID:
    return UUID(str(uuid7()))


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """真 DB session:外層 transaction + **SAVEPOINT** 加入模式。

    why 是 `create_savepoint` 而不是預設的 `conditional_savepoint`:script 每批都會自己
    `commit()` / `rollback()`。預設加入模式下,session 的 `rollback()` 會把測試前置插入的
    資料一起清掉(實測過);`create_savepoint` 才有「commit 只釋放 savepoint、rollback
    不越界」的語意。

    因此**前置資料插入後必須 `await db_session.commit()`**(釋放 savepoint),否則會被
    script 的第一次 rollback 抹掉。測試結束仍由外層 transaction 整批 rollback,
    dev DB 不會留下任何資料。
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


# why 用 raw INSERT 而不是 ORM:本組測試需要「三天前」的 `updated_at`。`usage_logs` 掛著
# BEFORE UPDATE trigger,任何 UPDATE 都會把它推成 NOW();而若拿同一交易內剛 INSERT 的列來
# 測,原值本來就等於 NOW(),trigger 有沒有被停用**測不出差別**(實測過:那樣寫的斷言即使
# trigger 全開也會過)。INSERT 不觸發該 trigger,故可塞舊值。
_INSERT_SQL = text(
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
    RETURNING pid, created_at, updated_at
    """
)


async def _insert_row(
    session: AsyncSession, content: dict[str, object]
) -> tuple[int, str, datetime, datetime]:
    uid = str(_new_uid())
    created = datetime(2026, 3, 5, 8, 30, tzinfo=UTC)
    aged = datetime.now(UTC) - timedelta(days=3)
    row = (
        await session.execute(
            _INSERT_SQL.bindparams(
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
                created_at=created,
                updated_at=aged,
            )
        )
    ).one()
    return int(row[0]), uid, row[1], row[2]


async def _row_snapshot(session: AsyncSession, pid: int) -> dict[str, object]:
    row = (
        await session.execute(text("SELECT * FROM usage_logs WHERE pid = :pid").bindparams(pid=pid))
    ).one()
    return dict(row._mapping)


async def _max_pid(session: AsyncSession) -> int:
    return int(
        (await session.execute(text("SELECT coalesce(max(pid), 0) FROM usage_logs"))).scalar_one()
    )


def _expected_key_at(uid: str, index: int, content: bytes, mime: str, when: datetime) -> str:
    return build_object_key(
        scope="chat",
        owner_uid=uid,
        index=index,
        content=content,
        mime=mime,
        key_prefix=_PREFIX,
        occurred_at=when,
    )


async def test_real_db_preserves_updated_at_and_other_columns(db_session: AsyncSession) -> None:
    """【必測】真 DB 改寫後:`updated_at` 未變、其餘欄位逐欄相同、key 用該列 created_at。"""
    max_pid = await _max_pid(db_session)
    pid, uid, created, aged = await _insert_row(db_session, _rich_single_turn(_PNG_URI, _JPG_URI))
    await db_session.commit()
    before = await _row_snapshot(db_session, pid)

    report = await run_migration(
        db_session,
        client=_StubS3(),  # type: ignore[arg-type]
        key_prefix=_PREFIX,
        after_pid=max_pid,
    )
    after = await _row_snapshot(db_session, pid)

    keys = [
        _expected_key_at(uid, 0, _PNG_BYTES, "image/png", created),
        _expected_key_at(uid, 1, _JPG_BYTES, "image/jpeg", created),
    ]
    assert report.rewritten == 2
    # updated_at 完全相同(且確實還是三天前那個值,不是被推到今天)。
    assert after["updated_at"] == before["updated_at"] == aged

    for column, value in before.items():
        if column == "request_content":
            continue
        assert after[column] == value, f"欄位 {column} 不該被遷移改動"

    before_content = before["request_content"]
    after_content = after["request_content"]
    assert isinstance(before_content, dict) and isinstance(after_content, dict)
    for node, value in before_content.items():
        if node == "images":
            continue
        assert after_content[node] == value, f"節點 {node} 不該被遷移改動"
    assert after_content["images"] == keys
    assert keys[0].startswith(f"{_PREFIX}/chat/2026/03/05/{uid}/0-")


async def test_real_db_safety_net_leaves_row_untouched(db_session: AsyncSession) -> None:
    """【必測】上傳失敗 → 整列一個 byte 都沒動。"""
    max_pid = await _max_pid(db_session)
    pid, uid, created, _ = await _insert_row(db_session, _rich_single_turn(_PNG_URI))
    await db_session.commit()
    before = await _row_snapshot(db_session, pid)

    failing = _expected_key_at(uid, 0, _PNG_BYTES, "image/png", created)
    report = await run_migration(
        db_session,
        client=_StubS3(fail_puts={failing}),  # type: ignore[arg-type]
        key_prefix=_PREFIX,
        after_pid=max_pid,
    )
    after = await _row_snapshot(db_session, pid)

    assert after == before, "上傳失敗時該列必須原封不動"
    assert (report.rewritten, report.rows_skipped) == (0, 1)
    assert [p.reason for p in report.pending] == ["s3_upload_failed"]


async def test_real_db_dry_run_writes_nothing(db_session: AsyncSession) -> None:
    max_pid = await _max_pid(db_session)
    pid, _, _, _ = await _insert_row(db_session, _rich_single_turn(_PNG_URI))
    await db_session.commit()
    before = await _row_snapshot(db_session, pid)

    report = await run_migration(
        db_session,
        client=_StubS3(),  # type: ignore[arg-type]
        key_prefix=_PREFIX,
        after_pid=max_pid,
        dry_run=True,
    )
    after = await _row_snapshot(db_session, pid)

    assert after == before, "dry-run 不得寫入任何東西"
    assert (report.planned, report.rewritten) == (1, 0)


async def test_real_db_second_run_does_nothing(db_session: AsyncSession) -> None:
    max_pid = await _max_pid(db_session)
    await _insert_row(db_session, _single_turn(_PNG_URI))
    await db_session.commit()
    client = _StubS3()

    first = await run_migration(
        db_session,
        client=client,
        key_prefix=_PREFIX,
        after_pid=max_pid,  # type: ignore[arg-type]
    )
    client.puts.clear()
    second = await run_migration(
        db_session,
        client=client,
        key_prefix=_PREFIX,
        after_pid=max_pid,  # type: ignore[arg-type]
    )

    assert (first.uploaded, first.rewritten) == (1, 1)
    assert client.puts == []
    assert (second.uploaded, second.rewritten) == (0, 0)
    assert second.already_path == 1


async def test_real_db_completion_criterion(db_session: AsyncSession) -> None:
    """跑完本批列後,這些列已無 `data:...base64,`。"""
    max_pid = await _max_pid(db_session)
    pid_a, uid_a, created_a, _ = await _insert_row(db_session, _single_turn(_PNG_URI, _JPG_URI))
    pid_b, uid_b, created_b, _ = await _insert_row(db_session, _messages(_GIF_URI))
    await db_session.commit()

    report = await run_migration(
        db_session,
        client=_StubS3(),  # type: ignore[arg-type]
        key_prefix=_PREFIX,
        after_pid=max_pid,
    )

    assert (report.rewritten, report.still_base64) == (3, 0)
    assert report.pending == []
    remaining = int(
        (
            await db_session.execute(
                text(
                    "SELECT count(*) FROM usage_logs "
                    "WHERE pid > :after AND request_content::text LIKE '%data:%base64,%'"
                ).bindparams(after=max_pid)
            )
        ).scalar_one()
    )
    assert remaining == 0

    expected = {
        _expected_key_at(uid_a, 0, _PNG_BYTES, "image/png", created_a),
        _expected_key_at(uid_a, 1, _JPG_BYTES, "image/jpeg", created_a),
        _expected_key_at(uid_b, 0, _GIF_BYTES, "image/gif", created_b),
    }
    after_a = await _row_snapshot(db_session, pid_a)
    after_b = await _row_snapshot(db_session, pid_b)
    assert set(_image_values(after_a["request_content"])) <= expected  # type: ignore[arg-type]
    assert set(_image_values(after_b["request_content"])) <= expected  # type: ignore[arg-type]
