"""歷史 base64 附件遷移 script(v2.2.1;propose §B.3 / §D.6)。

把 `usage_logs.request_content` 內既有的 base64 圖片搬到 S3,**上傳成功就地把該值改寫成
物件路徑**。一支指令走完,沒有第二階段:

```bash
cd /app && python -m scripts.migrate_base64_to_s3
```

## 流程(每批 50 列)

1. 依 `pid` 由小到大(= 由舊到新)撈 50 列 —— **不篩選**,有沒有 base64 都撈。
2. 逐列走訪附件值,只處理**是 base64 data URI**的(已是 S3 路徑 / 遠端 URL 一律跳過)。
3. 上傳 S3,key 依該列**當初的 `created_at`** 做日期分層:
   `<prefix>/chat/<YYYY>/<MM>/<DD>/<usage_log_uid>/<走訪序號>-<sha256[:16]>.<ext>`
   —— 與新請求的寫入路徑同一套規則(`build_object_key(scope="chat")`),歷史資料因此
   落在與新資料一致的目錄結構下,而不是另闢一個 legacy 區。
4. 上傳成功後,把該值改寫成物件路徑(`jsonb_set` 單點置換)。

## 為什麼掃描不加 `LIKE '%data:%base64,%'` 篩選

那個條件走不到索引,Postgres 得把整表 JSONB 從 TOAST 拉出來轉 text 才能比對。更糟的是
配上 `LIMIT 50` 之後,含圖的列稀疏時**單一查詢會一路掃到湊滿 50 筆命中為止** —— 可能掃過
數十萬列、好幾分鐘不回來,期間畫面完全空白,分不清在跑還是卡死(實際發生過)。

改成純 `pid` 範圍掃描(`WHERE pid > :cursor ORDER BY pid LIMIT 50`)後,查詢走 PK、
**每次都立刻返回**,每 50 列印一行進度。判斷「是不是 base64」交給 Python 端的
`parse_data_uri()`。總 I/O 量沒變(每列終究要看過一次),但不再有停頓。

## 不可逆,執行前必須有可還原的備份

改寫是就地覆寫:**原始 base64 在覆寫後不存在於資料庫任何地方**(沒有暫存欄位、沒有影子表
—— 加了就沒有乾淨的退場路徑,詳見 propose §D.6)。唯一的回退手段是還原 `pg_dump`,而且
「有跑過 dump」不算數,必須實際驗證還原得起來。操作手冊:
`docs/Tasks/v2.2/runbook-v2.2.1-migration.md`。

先跑 `--dry-run` 看數字:不上傳、不寫 DB。

## 安全保證

- **上傳成功才改寫**。`put_object` 失敗(或 `head_object` 查不到)→ 該值不改寫。
- **同一列有任何一個附件沒搬成功 → 整列都不改寫**,避免半路徑半 base64 的中間態
  (那會讓後續重跑無從分辨「沒搬完」還是「本來如此」)。
- **只動附件節點**:`jsonb_set(request_content, <path>, ...)` 由 Postgres 在 server 端做
  單點置換,整份文件不經 Python 重新序列化 —— `text` / `messages` 文字 / `tools` /
  生成參數等節點連 parse 都不會被 parse(避開 JSON 數值 round-trip 失真)。
  另以 `AND request_content #>> <path> = :expected` 做樂觀鎖:值在掃描後被別人改過就不套用。
- **`updated_at` 不跳動**(見下)。
- **冪等**:已是路徑的值直接跳過;`head_object` 命中的物件不重傳。中斷後原指令重跑即可,
  不需要進度檔(想加速就用報表末行給的「最後處理 pid」餵 `--after-pid`)。

## 為什麼要 `session_replication_role = replica`

`usage_logs` 上掛著 DB 層 trigger `trg_usage_logs_updated_at`
(`BEFORE UPDATE ... NEW.updated_at = NOW()`,見 `alembic/baseline_sql/V6__usage_logs.sql`)。
它是 **DB 端**行為,**不是** ORM 的 `onupdate` —— 因此「改走 raw SQL + 顯式寫回原值」
擋不住它:trigger 在 BEFORE 階段覆寫 `NEW.updated_at`,語句寫什麼都沒用(已實測)。

要讓 `updated_at` 不跳動,只能在**本次交易內**停掉 trigger:
`SET LOCAL session_replication_role = replica`(交易結束自動還原,不影響其他連線;
對照 `ALTER TABLE ... DISABLE TRIGGER` 是全域生效 + ACCESS EXCLUSIVE lock,會擋住線上寫入)。
此設定需 superuser(或 PG15+ 由 DBA `GRANT SET ON PARAMETER`);權限不足時本檔**直接中止**
(`MigrationPreconditionError`),不會退而求其次去污染 `updated_at`。

UPDATE 語句仍**顯式**寫回原 `updated_at`:trigger 若哪天被移除,語句本身也保證語意正確。

## 每批放掉交易

`fetch_batch()` 之後**立刻** `rollback()`,S3 呼叫一律在交易外進行。除了不讓網路 I/O 佔著
寫入交易,更關鍵的是:一個橫跨整趟執行(可能數小時)的交易會把 xmin horizon 壓住,期間
**全庫**產生的 dead tuple 都無法被 autovacuum 回收。每批放掉,交易就只剩那一句 SELECT
與那一批 UPDATE 的長度。

## 為什麼不走 alembic

migration 內做大量外部網路 I/O 不可控(單批可能跑數十分鐘、失敗難以回復),且會綁架
CI 的 `alembic upgrade head` round-trip(`04-databases/08-alembic.md`)。本遷移是一次性
資料搬運,不是 schema 變更,落在 script 才可分批 / 可中止 / 可重跑。

規範:`04-databases/04-sql-safety.md`(raw SQL 一律 `text(...).bindparams(...)`,
禁字串拼接)、`04-databases/07-connection.md`、`03-backend/03-async-and-tx.md`、
`03-backend/05-exceptions-and-logging.md`、`90-third-party-service/09-object-storage.md`。

## 使用方式

```bash
# 部署環境(容器內)—— 一律走 `-m`;`python scripts/xxx.py` 會因為 /app 不在 sys.path 而
# ModuleNotFoundError: No module named 'app'
cd /app
python -m scripts.migrate_base64_to_s3 --dry-run    # 只報數字
python -m scripts.migrate_base64_to_s3              # 實際搬運 + 改寫
python -m scripts.migrate_base64_to_s3 --limit 50   # 只處理前 50 列(小範圍試跑)

# 長時間執行丟背景(容器 terminal 斷線會帶走前景 process)
nohup python -m scripts.migrate_base64_to_s3 > /tmp/migrate.log 2>&1 &
tail -f /tmp/migrate.log

# 本機開發
cd backend && uv run python scripts/migrate_base64_to_s3.py --dry-run
```

`--after-pid` / `--before-pid` 可把一趟切成幾個獨立 process(上界含、下界不含,兩窗以
同一個 pid 接軌即不重不漏);正常情況不需要。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.clients.s3 import S3Client, S3ConfigError, S3Error, get_s3_client
from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.attachment import (
    build_object_key,
    content_type_for_mime,
    is_remote_url,
    parse_data_uri,
)

logger = get_logger(__name__)

__all__ = [
    "AttachmentRef",
    "MigrationPreconditionError",
    "MigrationReport",
    "PendingRow",
    "UsageLogRow",
    "fetch_batch",
    "format_report",
    "iter_image_attachments",
    "migration_object_key",
    "run_migration",
    "scan_end_pid",
]

# `pid` 上界的哨兵值(BIGINT 上限,`pid` 是 BIGSERIAL)。
_MAX_PID = 9223372036854775807

# 掃描:純 `pid` 範圍,**不篩內容**(理由見檔頭「為什麼掃描不加 LIKE 篩選」)。
# 游標分批(`pid > :after_pid ORDER BY pid LIMIT :batch_size`)而非 OFFSET:OFFSET 在大表上
# 每批都要重掃前綴,且中途有新列插入時會漏列(`04-databases/09-indexes-and-perf.md`)。
_SCAN_SQL = text(
    """
    SELECT pid, usage_log_uid, request_content, created_at, updated_at
    FROM usage_logs
    WHERE pid > :after_pid
      AND pid <= :before_pid
    ORDER BY pid
    LIMIT :batch_size
    """
)

# 掃描終點:走 PK,秒級返回(不碰 `request_content`,不會 detoast)。
_MAX_PID_SQL = text("SELECT max(pid) FROM usage_logs WHERE pid <= :before_pid")

# 單點置換:只動 `path` 指到的那一個字串節點。
# - `jsonb_set(..., create_missing => false)`:路徑不存在就原樣返回,絕不長出新節點。
# - `AND request_content #>> path = :expected`:樂觀鎖 —— 掃描後值被別人改過就不套用
#   (rowcount=0),不會把別人的新值蓋掉。
# - `updated_at = :updated_at`:顯式寫回掃描時讀到的原值。
_UPDATE_SQL = text(
    """
    UPDATE usage_logs
    SET request_content = jsonb_set(
            request_content, CAST(:path AS text[]), to_jsonb(CAST(:value AS text)), false
        ),
        updated_at = :updated_at
    WHERE pid = :pid
      AND request_content #>> CAST(:path AS text[]) = :expected
    RETURNING pid
    """
)

# 停用本交易內的 user trigger(含 `trg_usage_logs_updated_at`);`SET LOCAL` 於交易結束
# 自動還原,不影響其他連線。詳見檔頭「為什麼要 session_replication_role」。
_TRIGGER_BYPASS_SQL = text("SET LOCAL session_replication_role = replica")

_REASON_UPLOAD_FAILED = "s3_upload_failed"
_REASON_HEAD_FAILED = "s3_head_failed"
_REASON_S3_UNAVAILABLE = "s3_unavailable"
_REASON_MALFORMED = "malformed_data_uri"
_REASON_VALUE_CHANGED = "row_value_changed"

# 每批 50 列。why 不更大:含圖的列 JSONB 可能是 MB 級,一批全部讀進 Python 記憶體 ——
# 腳本跑在 backend 容器內、與線上 API 共用 memory limit,批次開太大時 OOM killer 可能連帶
# 把線上服務打掉。且每批是一個 transaction,批小則鎖的列少、對線上寫入干擾小。
_DEFAULT_BATCH_SIZE = 50

# 單一附件的處理結果。
ItemOutcome = Literal[
    "uploaded", "existing", "planned", "remote", "already_path", "invalid", "failed"
]


@dataclass(frozen=True, slots=True)
class AttachmentRef:
    """`request_content` 內單一圖片值的位置與內容。

    Attributes:
        index: **走訪序號**(自 0 起),直接餵給 `build_object_key(index=...)`。
        path: 該字串值在 `request_content` 內的完整路徑,例如 `("images", 0)` 或
            `("messages", 0, "content", 1, "image_url", "url")` —— 改寫時的定位資訊。
        value: 原始字串值(base64 data URI / S3 路徑 / 遠端 URL)。
    """

    index: int
    path: tuple[str | int, ...]
    value: str


@dataclass(frozen=True, slots=True)
class UsageLogRow:
    """掃描到的單列 `usage_logs`(唯讀快照,不對應 ORM 實體)。

    Attributes:
        created_at: 該筆紀錄**當初的建立時間** —— S3 的日期資料夾取自它。
        updated_at: 掃描當下的原值;UPDATE 顯式寫回它。
    """

    pid: int
    usage_log_uid: str
    request_content: dict[str, object]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class PendingRow:
    """某個附件值這次沒被處理完,以及為什麼。

    `reason` 為 `_REASON_*` 短代碼。除了 `malformed_data_uri`(該值本身沒有內容可搬,
    不阻斷同列其他附件),其餘都會讓**整列**不被改寫。
    """

    pid: int
    usage_log_uid: str
    index: int
    reason: str
    detail: str


@dataclass(slots=True)
class MigrationReport:
    """一次執行的統計。

    - `rows_scanned`:掃過的列數(含完全沒有附件的列)。
    - `rows_with_base64`:其中含 base64 附件的列數。
    - `uploaded` / `existing`:實際上傳的物件數 / `head_object` 命中而跳過的數(冪等)。
    - `planned`:dry-run 下「本來會上傳並改寫」的數量(非 dry-run 恆為 0)。
    - `rewritten` / `rows_rewritten`:改寫成路徑的值數 / 完成改寫的列數。
    - `rows_skipped`:因為有附件沒搬成功而**整列**跳過的列數。
    - `still_base64`:掃描結束時仍含 base64 的列數(**由本次掃描直接算出**,不另發查詢)。
    - `last_pid`:最後處理到的 `pid` —— 中斷後餵給 `--after-pid` 續跑。
    """

    rows_scanned: int = 0
    rows_with_base64: int = 0
    images_seen: int = 0
    remote_skipped: int = 0
    already_path: int = 0
    invalid: int = 0
    uploaded: int = 0
    existing: int = 0
    planned: int = 0
    rewritten: int = 0
    rows_rewritten: int = 0
    rows_skipped: int = 0
    still_base64: int = 0
    last_pid: int = 0
    pending: list[PendingRow] = field(default_factory=list)


class MigrationPreconditionError(RuntimeError):
    """前置條件不足,**不得**降級續跑(例:無權停用 `updated_at` trigger)。"""


@dataclass(frozen=True, slots=True)
class _PlannedUpdate:
    """單一「已確認物件在 S3」的改寫動作。"""

    ref: AttachmentRef
    key: str


@dataclass(slots=True)
class _RowPlan:
    """一列的處理計畫 —— **先全列處理完再寫**,不邊傳邊寫。

    `blockers` 非空 = 該列**整列**不改寫(見檔頭「安全保證」)。
    `notes` 是不阻斷的問題(畸形值本來就無內容可搬),只記入待處理清單供人工複核。
    """

    row: UsageLogRow
    updates: list[_PlannedUpdate] = field(default_factory=list)
    blockers: list[PendingRow] = field(default_factory=list)
    notes: list[PendingRow] = field(default_factory=list)
    images_seen: int = 0
    base64_seen: int = 0
    already_path: int = 0
    remote: int = 0
    invalid: int = 0
    uploaded: int = 0
    existing: int = 0
    planned: int = 0

    @property
    def blocked(self) -> bool:
        return bool(self.blockers)

    @property
    def still_has_base64(self) -> bool:
        """本列處理後是否仍含 base64(畸形值算,因為它確實還留在庫裡)。"""
        if self.blocked:
            return self.base64_seen > 0
        return self.invalid > 0


def iter_image_attachments(request_content: Mapping[str, object]) -> Iterator[AttachmentRef]:
    """走訪一列 `request_content` 內所有圖片值,依序配發走訪序號。

    支援兩種既有快照形狀(`proxy._build_request_log`):

    1. 單輪模式:`{"model": ..., "text": ..., "images": ["data:image/png;base64,...", ...]}`
    2. messages 模式:`{"messages": [{"content": [{"type": "image_url",
       "image_url": {"url": "data:..."}}, ...]}]}`

    ⚠️ **序號規則**:

    - 順序固定為「先 `images[]`,再 `messages[]` 的 content 出現順序」。
    - **每個走訪到的圖片值都佔一個序號**,含遠端 URL、已改寫的路徑與畸形值 —— 序號代表
      「位置」而非「第幾個成功上傳的」。否則同一列內只要有一張畸形值,重跑時算出的序號就會
      整排位移,同一份內容會被上傳到兩個不同的 key。
    - `files` 不走訪:歷史紀錄的 `files` 只留檔名、從未留過內容,無從回填(§D.3)。

    Yields:
        `AttachmentRef`;非字串 / 結構不符的節點一律安靜略過(歷史資料不保證形狀)。
    """
    index = 0

    images = request_content.get("images")
    if isinstance(images, list):
        for position, value in enumerate(images):
            if isinstance(value, str):
                yield AttachmentRef(index=index, path=("images", position), value=value)
                index += 1

    messages = request_content.get("messages")
    if not isinstance(messages, list):
        return
    for m_pos, message in enumerate(messages):
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for c_pos, part in enumerate(content):
            if not isinstance(part, dict) or part.get("type") != "image_url":
                continue
            inner = part.get("image_url")
            if not isinstance(inner, dict):
                continue
            url = inner.get("url")
            if not isinstance(url, str):
                continue
            yield AttachmentRef(
                index=index,
                path=("messages", m_pos, "content", c_pos, "image_url", "url"),
                value=url,
            )
            index += 1


def migration_object_key(
    *,
    usage_log_uid: str,
    index: int,
    content: bytes,
    mime: str,
    key_prefix: str,
    occurred_at: datetime,
) -> str:
    """算出歷史附件的物件 key —— **唯一入口**,禁在別處組。

    只是把參數轉交 task-524 的 `build_object_key(scope="chat", ...)`,存在的意義是讓
    「用哪個 scope、日期取自哪個欄位」在程式碼層只有**一個**決定點。

    key 形態:`<prefix>/chat/<YYYY>/<MM>/<DD>/<usage_log_uid>/<index>-<sha256[:16]>.<ext>`

    why `scope="chat"` 而不是 `legacy`:日期分層(`<YYYY>/<MM>/<DD>`)只有 `chat` 有,而
    日期資料夾正是本遷移要的 —— 歷史附件因此落在與新請求**一致**的目錄結構下,而不是另闢
    一個 legacy 區。`occurred_at` 餵該列的 `created_at`,所以分到的是「當初那天」的資料夾,
    不是遷移執行日。副檔名一律經白名單推導(`build_object_key` 內部處理)。
    """
    return build_object_key(
        scope="chat",
        owner_uid=usage_log_uid,
        index=index,
        content=content,
        mime=mime,
        key_prefix=key_prefix,
        occurred_at=occurred_at,
    )


def _coerce_request_content(raw: object) -> dict[str, object]:
    """把 driver 回傳的 `request_content` 正規化為 dict。

    SQLAlchemy 的 asyncpg dialect 一般已裝 JSON codec(拿到的就是 dict);此處仍容錯
    字串型態,避免換 driver 或走 raw connection 時整批靜默掃不到東西。
    """
    if isinstance(raw, dict):
        return {str(k): v for k, v in raw.items()}
    if isinstance(raw, str | bytes | bytearray):
        try:
            parsed = json.loads(raw)
        except ValueError, TypeError:
            return {}
        if isinstance(parsed, dict):
            return {str(k): v for k, v in parsed.items()}
    return {}


async def fetch_batch(
    session: AsyncSession,
    *,
    after_pid: int,
    batch_size: int,
    before_pid: int = _MAX_PID,
) -> list[UsageLogRow]:
    """以 `pid` 游標撈下一批列(**唯讀**,不篩內容)。

    SQL 走 `text(...).bindparams(...)`,**禁**字串拼接(`04-databases/04-sql-safety.md`)。
    """
    result = await session.execute(
        _SCAN_SQL.bindparams(
            after_pid=after_pid,
            before_pid=before_pid,
            batch_size=batch_size,
        )
    )
    return [
        UsageLogRow(
            pid=int(pid),
            usage_log_uid=str(usage_log_uid),
            request_content=_coerce_request_content(request_content),
            created_at=created_at,
            updated_at=updated_at,
        )
        for pid, usage_log_uid, request_content, created_at, updated_at in result.all()
    ]


async def scan_end_pid(session: AsyncSession, *, before_pid: int = _MAX_PID) -> int:
    """本次掃描的終點 `pid`(`min(max(pid), before_pid)`)—— 走 PK,秒級返回。

    有了終點才能在啟動時就印出「要掃到哪裡」與逐批的百分比,而不是跑到撈不到列才發現結束。
    """
    row = (await session.execute(_MAX_PID_SQL.bindparams(before_pid=before_pid))).first()
    return int(row[0]) if row is not None and row[0] is not None else 0


def _pending(row: UsageLogRow, index: int, reason: str, detail: str) -> PendingRow:
    """組待處理條目並記結構化 log。

    log **只**帶 pid / 序號 / 原因代碼 / AWS 錯誤碼與例外類別名:S3 原始訊息可能夾帶憑證或
    簽章,本專案 log 無機密過濾層(見 `app/clients/s3/errors.py` 檔頭)。
    """
    logger.warning(
        "遷移跳過附件 pid=%s index=%s reason=%s detail=%s", row.pid, index, reason, detail
    )
    return PendingRow(
        pid=row.pid, usage_log_uid=row.usage_log_uid, index=index, reason=reason, detail=detail
    )


def _is_base64_value(value: str) -> bool:
    """值是否是 base64 data URI(`data:` 開頭)。其餘一律視為「已是路徑 / 不需處理」。"""
    return value.strip().lower().startswith("data:")


async def _plan_row(
    row: UsageLogRow,
    *,
    client: S3Client | None,
    key_prefix: str,
    dry_run: bool,
) -> _RowPlan:
    """處理一列:走訪 → 上傳 → 產出改寫計畫。**不寫 DB**。

    每個附件值的判定順序:遠端 URL → 已是路徑 → 畸形值 → 算 key → `head_object` → 上傳。

    Raises:
        S3ConfigError: 憑證 / bucket 設定錯 —— 這類錯誤每一列都會重演,繼續跑只會刷出滿版
            失敗清單,故視為致命、直接中止整批。
    """
    plan = _RowPlan(row=row)
    for ref in iter_image_attachments(row.request_content):
        plan.images_seen += 1

        if is_remote_url(ref.value):
            # 呼叫端原本就送遠端 URL → 原樣保留、不代抓(避免 SSRF 面,§D.2)。
            plan.remote += 1
            continue
        if not _is_base64_value(ref.value):
            # 已是 S3 路徑(或其他非 base64 值)→ 冪等跳過。
            plan.already_path += 1
            continue

        plan.base64_seen += 1
        parsed = parse_data_uri(ref.value)
        if parsed is None:
            # 畸形值沒有可搬的內容,改不了但也不該擋住同列其他附件;記入待處理清單。
            plan.invalid += 1
            plan.notes.append(_pending(row, ref.index, _REASON_MALFORMED, "-"))
            continue

        key = migration_object_key(
            usage_log_uid=row.usage_log_uid,
            index=ref.index,
            content=parsed.content,
            mime=parsed.mime,
            key_prefix=key_prefix,
            occurred_at=row.created_at,
        )

        if client is None:
            # 無 client = 無法確認物件真的在 S3 → 一律視為阻斷,絕不盲寫路徑。
            # (只有 dry-run 到得了這裡;實跑取不到 client 會在啟動時就 fail-fast。)
            plan.planned += 1
            plan.blockers.append(_pending(row, ref.index, _REASON_S3_UNAVAILABLE, "-"))
            continue

        try:
            exists = await client.head_object(key)
        except S3ConfigError:
            raise
        except S3Error as err:
            detail = f"{type(err).__name__}/{err.aws_code or '-'}"
            plan.blockers.append(_pending(row, ref.index, _REASON_HEAD_FAILED, detail))
            continue

        if exists:
            # 冪等:同一把 key 已在 S3(前一趟傳過)→ 不重傳,但仍要改寫這個值。
            plan.existing += 1
            plan.updates.append(_PlannedUpdate(ref=ref, key=key))
            continue

        if dry_run:
            plan.planned += 1
            continue

        try:
            await client.put_object(key, parsed.content, content_type_for_mime(parsed.mime))
        except S3ConfigError:
            raise
        except S3Error as err:
            detail = f"{type(err).__name__}/{err.aws_code or '-'}"
            plan.blockers.append(_pending(row, ref.index, _REASON_UPLOAD_FAILED, detail))
            continue
        except Exception as err:  # noqa: BLE001 - 單一附件的未預期例外不得中斷整批
            plan.blockers.append(
                _pending(row, ref.index, _REASON_UPLOAD_FAILED, type(err).__name__)
            )
            continue

        plan.uploaded += 1
        plan.updates.append(_PlannedUpdate(ref=ref, key=key))

    return plan


def _absorb_plan(report: MigrationReport, plan: _RowPlan) -> None:
    """把單列的計畫結果併進報表(不含實際改寫數,那由寫入階段累加)。"""
    report.images_seen += plan.images_seen
    report.already_path += plan.already_path
    report.remote_skipped += plan.remote
    report.invalid += plan.invalid
    report.uploaded += plan.uploaded
    report.existing += plan.existing
    report.planned += plan.planned
    if plan.base64_seen:
        report.rows_with_base64 += 1
    if plan.still_has_base64:
        report.still_base64 += 1
    report.pending.extend(plan.notes)
    if plan.blocked:
        report.rows_skipped += 1
        report.pending.extend(plan.blockers)


async def _bypass_updated_at_trigger(session: AsyncSession) -> None:
    """停用本交易內的 user trigger,讓 `updated_at` 不被 DB trigger 覆寫。

    Raises:
        MigrationPreconditionError: 權限不足。**刻意不降級續跑** —— 一旦續跑,全庫
            `updated_at` 會被推成今天,而這件事沒有回頭路(除非還原備份)。
    """
    try:
        await session.execute(_TRIGGER_BYPASS_SQL)
    except DBAPIError as err:
        raise MigrationPreconditionError(
            "無法設定 session_replication_role=replica(需 superuser 或 "
            "GRANT SET ON PARAMETER session_replication_role);"
            "不停用 trg_usage_logs_updated_at 就無法保留 updated_at,已中止。"
            f"({type(err.orig).__name__ if err.orig else type(err).__name__})"
        ) from err


async def _apply_batch(
    session: AsyncSession, plans: Sequence[_RowPlan], report: MigrationReport
) -> None:
    """把一批計畫寫入 DB —— **每批一個 transaction**。

    只處理「有東西要改且未被阻斷」的列;整批無事可做時直接 rollback(不留空交易)。
    """
    applicable = [plan for plan in plans if plan.updates and not plan.blocked]
    if not applicable:
        await session.rollback()
        return

    await _bypass_updated_at_trigger(session)
    for plan in applicable:
        row_complete = True
        for update in plan.updates:
            result = await session.execute(
                _UPDATE_SQL.bindparams(
                    pid=plan.row.pid,
                    path=[str(part) for part in update.ref.path],
                    value=update.key,
                    expected=update.ref.value,
                    updated_at=plan.row.updated_at,
                )
            )
            if result.first() is None:
                # 樂觀鎖沒中:掃描後該節點被改過(或路徑已不存在)→ 不套用,記待處理。
                row_complete = False
                report.pending.append(
                    _pending(plan.row, update.ref.index, _REASON_VALUE_CHANGED, "-")
                )
                continue
            report.rewritten += 1
        if row_complete:
            report.rows_rewritten += 1
        else:
            # 有值沒套用成功 → 該列仍留著 base64,計入「仍含 base64」。
            report.still_base64 += 1
    await session.commit()


def _print_progress(line: str) -> None:
    """輸出一行進度到 stdout。

    why `print(flush=True)` 而不是 logger:這是給人在 `nohup ... > log` 後 `tail -f` 看的,
    要的是即時、無格式雜訊、與最終報表同一個 stream。
    """
    print(line, flush=True)


def _pct(cursor: int, start: int, end: int) -> str:
    """掃描進度百分比(以 `pid` 位置估算)。"""
    span = end - start
    if span <= 0:
        return "100%"
    return f"{min(100.0, max(0.0, (cursor - start) / span * 100)):.1f}%"


async def run_migration(
    session: AsyncSession,
    *,
    client: S3Client | None,
    key_prefix: str,
    batch_size: int = _DEFAULT_BATCH_SIZE,
    limit: int = 0,
    dry_run: bool = False,
    after_pid: int = 0,
    before_pid: int = _MAX_PID,
) -> MigrationReport:
    """主流程:每批 50 列 → 上傳有 base64 的附件 → 就地改寫成路徑 → 印一行進度。

    Args:
        session: 可寫的 async session(呼叫端負責開 / 關)。本函式**每批都會 commit /
            rollback**,因此呼叫端若把 session 接在自己的外層交易上,需用
            `join_transaction_mode="create_savepoint"`。
        client: S3 client;`None` 僅 dry-run 允許(此時一律不改寫)。
        key_prefix: `S3_KEY_PREFIX`,test / prod 各自 bucket 內的前綴。
        batch_size: 每批撈幾列。
        limit: 最多處理幾列;`0` 表不限。
        dry_run: 只報統計,**不上傳、不寫 DB**。
        after_pid: 從哪個 `pid` 之後開始(續跑 / 分窗下界)。
        before_pid: 掃描到哪個 `pid` 為止(含;分窗上界)。

    Returns:
        `MigrationReport`;單列 / 單附件問題只記入 `pending`,不中斷整批。

    Raises:
        MigrationPreconditionError: 無權停用 `updated_at` trigger。
        S3ConfigError: S3 憑證 / bucket 設定錯。
    """
    report = MigrationReport(last_pid=after_pid)
    remaining = limit if limit > 0 else None
    started = time.monotonic()
    batch_no = 0

    cursor = after_pid
    scan_end = await scan_end_pid(session, before_pid=before_pid)
    await session.rollback()
    _print_progress(
        f"[migrate] 開始:掃描 pid {cursor + 1}~{scan_end},每批 {batch_size} 列"
        f"{'(dry-run:不上傳、不寫 DB)' if dry_run else ''}"
    )

    while cursor < scan_end:
        size = batch_size if remaining is None else min(batch_size, remaining)
        if size <= 0:
            break

        batch_no += 1
        batch_started = time.monotonic()

        rows = await fetch_batch(session, after_pid=cursor, before_pid=before_pid, batch_size=size)
        # 讀完立刻結束交易,不要帶著它去打 S3(理由見檔頭「每批放掉交易」)。
        await session.rollback()
        if not rows:
            break

        cursor = rows[-1].pid
        report.rows_scanned += len(rows)
        report.last_pid = cursor
        if remaining is not None:
            remaining -= len(rows)

        plans = [
            await _plan_row(row, client=client, key_prefix=key_prefix, dry_run=dry_run)
            for row in rows
        ]
        for plan in plans:
            _absorb_plan(report, plan)

        if not dry_run:
            await _apply_batch(session, plans, report)

        _print_progress(
            f"[migrate] #{batch_no} pid {cursor}/{scan_end}({_pct(cursor, after_pid, scan_end)})"
            f" 掃描 {report.rows_scanned} 列 / 含圖 {report.rows_with_base64} 列"
            f" / 上傳 {report.uploaded} / 已存在 {report.existing}"
            f" / {'預計改寫 ' + str(report.planned) if dry_run else '已改寫 ' + str(report.rewritten)}"
            f" / 整列跳過 {report.rows_skipped}"
            f" · 本批 {time.monotonic() - batch_started:.1f}s"
            f" 累計 {time.monotonic() - started:.1f}s"
        )

    return report


def format_report(report: MigrationReport, *, dry_run: bool) -> str:
    """把報表排成人看的文字;待處理清單含 `pid` 與原因供人工複核。"""
    lines = [
        "",
        f"=== 遷移完成{'(dry-run:未上傳、未寫 DB)' if dry_run else ''} ===",
        f"掃描列數        : {report.rows_scanned}(其中含 base64 {report.rows_with_base64} 列)",
        f"走訪圖片值      : {report.images_seen}",
        f"上傳 S3         : {report.uploaded}",
        f"已存在(冪等)   : {report.existing}",
    ]
    if dry_run:
        lines.append(f"預計上傳並改寫  : {report.planned}")
    lines += [
        f"改寫成路徑      : {report.rewritten}",
        f"完成改寫列數    : {report.rows_rewritten}",
        f"整列跳過(安全網): {report.rows_skipped}",
        f"已是路徑略過    : {report.already_path}",
        f"遠端 URL 略過   : {report.remote_skipped}",
        f"畸形值略過      : {report.invalid}",
        f"仍含 base64 列數: {report.still_base64}(期望 0;畸形值會永久留在此數)",
        f"待處理清單      : {len(report.pending)} 筆",
        f"最後處理 pid    : {report.last_pid}(續跑:--after-pid {report.last_pid})",
    ]
    if report.pending:
        lines.append("待處理清單(pid / 序號 / 原因 / 細節):")
        lines += [
            f"  - pid={p.pid} index={p.index} reason={p.reason} detail={p.detail}"
            for p in report.pending
        ]
    lines.append("")
    return "\n".join(lines)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="migrate_base64_to_s3",
        description="把 usage_logs.request_content 內的 base64 圖片搬到 S3 並就地改寫成路徑。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只報統計:不上傳、不寫 DB",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=_DEFAULT_BATCH_SIZE,
        help=f"每批撈幾列(pid 游標),預設 {_DEFAULT_BATCH_SIZE}。不是總量上限 —— "
        "腳本會一直迴圈到掃完為止,每批印一行進度",
    )
    parser.add_argument("--limit", type=int, default=0, help="最多處理幾列;0=不限")
    parser.add_argument(
        "--after-pid", type=int, default=0, help="從此 pid 之後開始(續跑 / 分窗下界)"
    )
    parser.add_argument(
        "--before-pid",
        type=int,
        default=0,
        help="掃描到此 pid 為止(含;分窗上界)。0=不限",
    )
    parser.add_argument("--database-url", default="", help="覆寫 DATABASE_URL(預設取 Settings)")
    return parser.parse_args(argv)


def _resolve_client(*, dry_run: bool) -> S3Client | None:
    """取 S3 client;dry-run 下取不到就降級為「只報數字」。

    why 對 dry-run 放寬:dry-run 的用途是「先看有多少東西要搬」,在還沒配 AWS 憑證的環境也
    該跑得起來;實跑則必須 fail-fast,否則會安靜地什麼都沒搬。
    """
    try:
        return get_s3_client()
    except S3Error as err:
        if not dry_run:
            raise
        print(f"[warn] 取不到 S3 client({type(err).__name__});dry-run 續跑,不做存在檢查")
        return None


async def _amain(args: argparse.Namespace) -> int:
    before_pid = args.before_pid if args.before_pid > 0 else _MAX_PID
    if 0 < args.before_pid <= args.after_pid:
        print(f"[error] --before-pid({args.before_pid})必須大於 --after-pid({args.after_pid})")
        return 2

    settings = get_settings()
    database_url = args.database_url or settings.DATABASE_URL
    client = _resolve_client(dry_run=args.dry_run)

    engine = create_async_engine(database_url, echo=False, pool_pre_ping=True)
    maker = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        async with maker() as session:
            report = await run_migration(
                session,
                client=client,
                key_prefix=settings.S3_KEY_PREFIX,
                batch_size=args.batch_size,
                limit=args.limit,
                dry_run=args.dry_run,
                after_pid=args.after_pid,
                before_pid=before_pid,
            )
    finally:
        await engine.dispose()

    print(format_report(report, dry_run=args.dry_run))
    return 1 if report.pending else 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        return asyncio.run(_amain(args))
    except MigrationPreconditionError as err:
        print(f"[error] 前置條件不足:{err}")
        return 2
    except S3Error as err:
        print(f"[error] S3 不可用({type(err).__name__}/{err.aws_code or '-'}),已中止")
        return 1


if __name__ == "__main__":
    sys.exit(main())
