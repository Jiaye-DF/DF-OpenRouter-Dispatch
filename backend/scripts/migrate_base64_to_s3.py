"""歷史 base64 附件遷移 script(v2.2.1;propose §B.3 / §D.6)。

把 `usage_logs.request_content` 內既有的 base64 圖片搬到 S3。依 user 定案
(原話:「base64 先暫時不動,等確定移轉成功後再棄用」)拆成**兩個獨立可跑的階段**,
中間卡一道人工驗收:

- **`--upload`(task-530)**:只把 base64 圖片上傳到 S3,**DB 一個 byte 都不改**。
  跑完 base64 仍原封不動留在庫裡,系統行為完全等同現況,隨時可中止、零副作用。
- **`--delete`(task-531)**:重掃一次、重算同一把 key、`head_object` 確認物件存在後,
  才把 DB 欄位裡的 base64 換成物件路徑(**不刪 S3 物件**)。
  **這是本版唯一不可逆的操作**,執行前必須有已驗證可還原的 `pg_dump`
  (操作手冊:`docs/Tasks/v2.2/runbook-v2.2.1-migration.md`)。

兩個 mode **互斥且必填**(argparse 強制)。文件與註解裡的「Phase 1 / Phase 2」等同
`--upload` / `--delete`,是 propose / task 文件的既有稱法,保留以便對照。

## 為什麼不需要 mapping 表 / 暫存欄位 / migration

key 是**內容決定**的純函式輸出(`app.services.attachment.build_object_key`):
`<prefix>/legacy/<usage_log_uid>/<走訪序號>-<sha256(bytes)[:16]>.<ext>`。Phase 2 只要以
**同一組走訪規則**重跑一次,就能重算出 Phase 1 用過的同一把 key,兩階段因此完全解耦。

這也是本檔**唯一不可妥協的設計**:key 與走訪序號的邏輯**只有一份**,分別是
`app.services.attachment.build_object_key`(task-524 匯出)與本檔的
`iter_image_attachments()`。Phase 2 **必須** import 這兩者,**禁**另寫一份 ——
兩份實作一旦漂移,Phase 2 會改寫出指向不存在物件的路徑,而且不會有任何錯誤訊息。

## 為什麼不走 alembic

migration 內做大量外部網路 I/O 不可控(單批可能跑數十分鐘、失敗難以回復),且會綁架
CI 的 `alembic upgrade head` round-trip(`04-databases/08-alembic.md`)。本遷移是一次性
資料搬運,不是 schema 變更,落在 script 才可分批 / 可中止 / 可重跑。

## 兩個 phase 的 DB 交易設定**刻意分開**

- **Phase 1**:對 DB **只有 SELECT**,沒有任何寫入語句、不 commit;`_amain()` 另在 engine
  上掛連線層 `default_transaction_read_only=on`,讓「不寫 DB」由 Postgres 端再保證一次
  (而非只靠人工 code review)。用連線層而非交易層(`postgresql_readonly` execution
  option)的理由見 `_amain()`。
- **Phase 2**:要寫入,故**不可**套用上述唯讀設定 —— 但也**不可**把 Phase 1 的唯讀保護
  拿掉。兩者各自建 engine / session,設定不共用。

## 兩個 phase 都「每批放掉交易」

`rows = fetch_batch(...)` 之後**立刻** `rollback()`,S3 呼叫一律在交易外進行。Phase 2 是
為了不讓 `head_object` 佔著寫入交易;Phase 1 則是為了不要在整趟執行期間(可能數小時)
持有一個交易 —— 那會把 xmin horizon 壓住,期間**全庫**的 dead tuple 都無法被 autovacuum
回收,正式站跑越久 bloat 累積越多。Phase 1 的 `rollback()` 沒有任何東西要回滾,它的作用
純粹是「放掉交易」。

## Phase 2 為什麼要 `session_replication_role = replica`

`usage_logs` 上掛著 DB 層 trigger `trg_usage_logs_updated_at`
(`BEFORE UPDATE ... NEW.updated_at = NOW()`,見 `alembic/baseline_sql/V6__usage_logs.sql`)。
它是 **DB 端**行為,**不是** ORM 的 `onupdate` —— 因此「改走 raw SQL + 顯式寫回原值」
(propose §D.7 原本的假設)**擋不住**它:trigger 在 BEFORE 階段覆寫 `NEW.updated_at`,
語句寫什麼都沒用(已實測)。

要讓 `updated_at` 不跳動,只能在**本次交易內**停掉 trigger:
`SET LOCAL session_replication_role = replica`(交易結束自動還原,不影響其他連線;
對照 `ALTER TABLE ... DISABLE TRIGGER` 是全域生效 + ACCESS EXCLUSIVE lock,會擋住線上寫入)。
此設定需 superuser(或 PG15+ 由 DBA `GRANT SET ON PARAMETER`);權限不足時本檔**直接中止**
(`RewritePreconditionError`),不會退而求其次去污染 `updated_at`。

UPDATE 語句仍**顯式**寫回原 `updated_at`:trigger 若哪天被移除,語句本身也保證語意正確。

## Phase 2 的「只動附件」保證

改寫用 `jsonb_set(request_content, <AttachmentRef.path>, ...)` 做**單點置換**,由 Postgres
在 server 端動那一個節點 —— 整份文件不經 Python 重新序列化,`text` / `messages` 文字 /
`tools` / 生成參數等節點連 parse 都不會被 parse(避開 JSON 數值 round-trip 失真的風險)。
另以 `AND request_content #>> <path> = :expected` 做樂觀鎖:值在掃描後被別人改過就不套用。

規範:`04-databases/04-sql-safety.md`(raw SQL 一律 `text(...).bindparams(...)`,
禁字串拼接)、`04-databases/07-connection.md`、`03-backend/03-async-and-tx.md`、
`03-backend/05-exceptions-and-logging.md`、`90-third-party-service/09-object-storage.md`。

## 使用方式

每批預設 50 列,每批處理完印一行進度;掃完自動結束,不需要外部迴圈。

本機開發:

```bash
cd backend
uv run python scripts/migrate_base64_to_s3.py --upload --dry-run     # 只報數字
uv run python scripts/migrate_base64_to_s3.py --upload               # 實際上傳
uv run python scripts/migrate_base64_to_s3.py --upload --limit 50    # 只掃前 50 列

# ⚠️ --delete 不可逆,執行前務必先看 docs/Tasks/v2.2/runbook-v2.2.1-migration.md
uv run python scripts/migrate_base64_to_s3.py --delete --dry-run     # 只報數字
uv run python scripts/migrate_base64_to_s3.py --delete               # 實際移除
```

部署環境(容器內)一律走 `-m`;`python scripts/migrate_base64_to_s3.py` 會因為
`/app` 不在 `sys.path` 而 `ModuleNotFoundError: No module named 'app'`。`-u` 讓進度即時吐出:

```bash
cd /app && python -u -m scripts.migrate_base64_to_s3 --upload
```

## 大表分窗:`--after-pid` / `--before-pid`

掃描條件 `LIKE '%data:%base64,%'` 走不到索引,整表 JSONB 都得從 TOAST 拉出來轉 text,
正式站一趟可能數十分鐘到數小時。想切成可控的分期付款就按 `pid` 分窗 —— `pid` 是
`BIGSERIAL PRIMARY KEY`、單調遞增(等同時間序),也是唯一走得到索引的切法
(`usage_logs` 沒有單獨的 `created_at` 索引)。

正常情況**不需要**分窗 —— 每批 50 列已經是可控的分期付款,中斷後原指令直接重跑即可
(兩個 mode 都冪等)。分窗只在「想把一趟切成幾個獨立 process、各自跑完就收工」時才需要。

兩窗以**同一個 pid** 接軌即不重不漏(上界含、下界不含):

```bash
python -u -m scripts.migrate_base64_to_s3 --upload --before-pid 100000
python -u -m scripts.migrate_base64_to_s3 --upload --after-pid 100000 --before-pid 200000
python -u -m scripts.migrate_base64_to_s3 --upload --after-pid 200000   # 尾段不設上界
```

窗界不必事先算,報表末行會給你「最後處理 pid」直接當下一窗的 `--after-pid`。

分窗跑 `--delete` 時記得加 `--skip-remaining-count`:完成判準是一次**全表** count,
每一窗都付一次很浪費(而且它算的是全表、不是本窗)。全部窗跑完再單獨查一次。
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
    "Failure",
    "MigrationReport",
    "PendingRow",
    "RewritePreconditionError",
    "RewriteReport",
    "UsageLogRow",
    "count_remaining_base64_rows",
    "fetch_batch",
    "format_report",
    "format_rewrite_report",
    "iter_image_attachments",
    "legacy_object_key",
    "run_rewrite",
    "run_upload",
]

# 掃描條件:JSONB 轉 text 後含 base64 data URI 的列。
# why 用 `::text LIKE`:圖片可能落在單輪 `images[]` 或 messages 模式的巢狀 content 內,
# 用 JSON path 表達要寫兩套且易漏;先以字串粗篩把候選列撈出來,精確判定交給
# `iter_image_attachments()` + `parse_data_uri()`(寧可多撈,不可漏撈)。
_LIKE_PATTERN = "%data:%base64,%"

# `pid` 上界的哨兵值(BIGINT 上限,`pid` 是 BIGSERIAL)。
# why 綁常數而不是讓 SQL 有兩種形狀:掃描語句兩個 phase 共用、只有一份是刻意的設計
# (見檔頭),多一個 `AND` 分支就多一處會漂移的地方。綁一個必然大於任何 pid 的值,
# 查詢計畫仍是 PK 範圍掃描,語句形狀不變。
_MAX_PID = 9223372036854775807

# 兩個 phase 共用**同一條**掃描語句 —— WHERE 條件只有一份,不會漂移。
# `updated_at` 只有 Phase 2 用得到(顯式寫回原值);Phase 1 撈了不用,代價是一個欄位,
# 換來「兩階段掃的是同一批列」這件事在程式碼層不需要靠註解維持。
# `pid > :after_pid AND pid <= :before_pid` 是**分窗**的依據:`pid` 單調遞增(等同時間序),
# 且是唯一走得到索引的切法(`usage_logs` 沒有單獨的 `created_at` 索引)。
_SCAN_SQL = text(
    """
    SELECT pid, usage_log_uid, request_content, updated_at
    FROM usage_logs
    WHERE pid > :after_pid
      AND pid <= :before_pid
      AND request_content::text LIKE :pattern
    ORDER BY pid
    LIMIT :batch_size
    """
)

# 收尾驗證(propose §驗收「Phase 2 後應回 0」)。與掃描共用 `_LIKE_PATTERN`。
_REMAINING_SQL = text(
    """
    SELECT count(*)
    FROM usage_logs
    WHERE request_content::text LIKE :pattern
    """
)

# Phase 2 的單點置換:只動 `path` 指到的那一個字串節點。
# - `jsonb_set(..., create_missing => false)`:路徑不存在就原樣返回,絕不長出新節點。
# - `AND request_content #>> path = :expected`:樂觀鎖 —— 掃描後值被別人改過就不套用
#   (rowcount=0),不會把別人的新值蓋掉。
# - `updated_at = :updated_at`:顯式寫回掃描時讀到的原值(§D.7)。
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
# 自動還原,不影響其他連線。詳見檔頭「Phase 2 為什麼要 session_replication_role」。
_TRIGGER_BYPASS_SQL = text("SET LOCAL session_replication_role = replica")

# 附件處理結果。`planned` = dry-run 下「本來會上傳」;`remote` = 已是遠端 URL(不代抓,§D.2)。
ItemOutcome = Literal["uploaded", "existing", "planned", "remote", "invalid", "failed"]

_REASON_S3_FAILED = "s3_upload_failed"
_REASON_HEAD_FAILED = "s3_head_failed"
# Phase 2 專用的待處理原因代碼。
_REASON_OBJECT_MISSING = "s3_object_missing"
_REASON_S3_UNAVAILABLE = "s3_unavailable"
_REASON_MALFORMED = "malformed_data_uri"
_REASON_VALUE_CHANGED = "row_value_changed"

# 每批 50 列。why 不是更大:含圖的列 JSONB 可能是 MB 級,一批全部讀進 Python 記憶體 ——
# 腳本跑在 backend 容器內、與線上 API 共用 memory limit,批次開太大時 OOM killer 可能連帶
# 把線上服務打掉。`--delete` 另有一層理由:每批是一個 transaction,批小則鎖的列少、
# 對線上寫入干擾小。
_DEFAULT_BATCH_SIZE = 50


@dataclass(frozen=True, slots=True)
class AttachmentRef:
    """`request_content` 內單一圖片值的位置與內容。

    Attributes:
        index: **走訪序號**(自 0 起),直接餵給 `build_object_key(index=...)`。
            序號規則見 `iter_image_attachments()` —— Phase 2 必須沿用同一份實作。
        path: 該字串值在 `request_content` 內的完整路徑,例如
            `("images", 0)` 或 `("messages", 0, "content", 1, "image_url", "url")`。
            Phase 1 用不到;**這是留給 Phase 2 改寫 JSONB 的定位資訊**。
        value: 原始字串值(base64 data URI 或遠端 URL)。
    """

    index: int
    path: tuple[str | int, ...]
    value: str


@dataclass(frozen=True, slots=True)
class UsageLogRow:
    """掃描到的單列 `usage_logs`(唯讀快照,不對應 ORM 實體)。

    Attributes:
        updated_at: 掃描當下的原值;Phase 2 的 UPDATE 顯式寫回它(§D.7)。Phase 1 不使用。
    """

    pid: int
    usage_log_uid: str
    request_content: dict[str, object]
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class Failure:
    """單一附件的失敗紀錄(失敗列不擋整批,結束時彙總)。"""

    pid: int
    index: int
    reason: str
    detail: str


@dataclass(slots=True)
class MigrationReport:
    """一次執行的統計。

    - `eligible`:**應上傳** N(可解析的 base64 圖片數)。
    - `uploaded`:**實際上傳** M。
    - `existing`:**已存在** K(`head_object` 命中,冪等跳過)。
    - `planned`:dry-run 下「本來會上傳」的數量(非 dry-run 恆為 0)。
    - `last_pid`:最後處理到的 `pid` —— 中斷後直接餵給 `--after-pid` 續跑。
    """

    rows_scanned: int = 0
    rows_with_image: int = 0
    images_seen: int = 0
    remote_skipped: int = 0
    invalid: int = 0
    eligible: int = 0
    uploaded: int = 0
    existing: int = 0
    planned: int = 0
    last_pid: int = 0
    failures: list[Failure] = field(default_factory=list)

    @property
    def failed(self) -> int:
        return len(self.failures)


@dataclass(frozen=True, slots=True)
class PendingRow:
    """Phase 2 的**待處理清單**條目:某個附件值這次沒被改寫,以及為什麼。

    `reason` 為 `_REASON_*` 短代碼;`s3_object_missing` 代表安全網生效
    (Phase 1 沒搬成功 / 物件被刪),該**整列**都不會被改寫。
    """

    pid: int
    usage_log_uid: str
    index: int
    reason: str
    detail: str


@dataclass(slots=True)
class RewriteReport:
    """Phase 2 的一次執行統計。

    - `eligible`:可改寫的 base64 值數。
    - `rewritten`:實際改寫成路徑的值數(非 dry-run)。
    - `planned`:dry-run 下「本來會改寫」的值數。
    - `rows_rewritten` / `rows_skipped`:成功改寫的列數 / 因安全網整列跳過的列數。
    - `remaining`:執行後仍含 base64 的列數(完成判準,應為 0);`-1` = 未計算。
    - `last_pid`:最後處理到的 `pid` —— 中斷後直接餵給 `--after-pid` 續跑。
    """

    rows_scanned: int = 0
    rows_with_image: int = 0
    images_seen: int = 0
    already_path: int = 0
    remote_skipped: int = 0
    invalid: int = 0
    eligible: int = 0
    rewritten: int = 0
    planned: int = 0
    rows_rewritten: int = 0
    rows_skipped: int = 0
    remaining: int = -1
    last_pid: int = 0
    pending: list[PendingRow] = field(default_factory=list)


class RewritePreconditionError(RuntimeError):
    """Phase 2 前置條件不足,**不得**降級續跑(例:無權停用 `updated_at` trigger)。"""


@dataclass(frozen=True, slots=True)
class _ItemResult:
    outcome: ItemOutcome
    failure: Failure | None = None


@dataclass(frozen=True, slots=True)
class _PlannedUpdate:
    """單一「已驗證物件存在」的改寫動作。"""

    ref: AttachmentRef
    key: str


@dataclass(slots=True)
class _RowPlan:
    """一列的改寫計畫 —— **先全列驗完再寫**,不邊驗邊寫。

    `blockers` 非空 = 該列**整列**不改寫(propose §B.3「物件不存在 → 跳過該列」):
    只改一半會讓同一列同時存在路徑與 base64,後續重跑無從分辨是「沒搬完」還是「本來如此」。
    `notes` 是不阻斷的問題(畸形值本來就無內容可搬),只記入待處理清單供人工複核。
    """

    row: UsageLogRow
    updates: list[_PlannedUpdate] = field(default_factory=list)
    blockers: list[PendingRow] = field(default_factory=list)
    notes: list[PendingRow] = field(default_factory=list)
    images_seen: int = 0
    already_path: int = 0
    remote: int = 0
    invalid: int = 0

    @property
    def blocked(self) -> bool:
        return bool(self.blockers)


def iter_image_attachments(request_content: Mapping[str, object]) -> Iterator[AttachmentRef]:
    """走訪一列 `request_content` 內所有圖片值,依序配發走訪序號。

    支援兩種既有快照形狀(`proxy._build_request_log`):

    1. 單輪模式:`{"model": ..., "text": ..., "images": ["data:image/png;base64,...", ...]}`
    2. messages 模式:`{"messages": [{"content": [{"type": "image_url",
       "image_url": {"url": "data:..."}}, ...]}]}`

    ⚠️ **序號規則是兩階段遷移的契約,改動即破壞 Phase 2**:

    - 順序固定為「先 `images[]`,再 `messages[]` 的 content 出現順序」。
    - **每個走訪到的圖片值都佔一個序號**,含遠端 URL 與畸形值 —— 序號代表「位置」
      而非「上傳成功的第幾張」,否則同一列內只要有一張畸形值,Phase 2 重算的序號就會
      整排位移。
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


def legacy_object_key(
    *,
    usage_log_uid: str,
    index: int,
    content: bytes,
    mime: str,
    key_prefix: str,
) -> str:
    """算出歷史附件的 legacy key —— **兩階段共用的唯一入口**。

    只是把參數轉交 task-524 的 `build_object_key(scope="legacy", ...)`;存在的意義是
    讓「Phase 1 與 Phase 2 用同一把 key」這件事在程式碼層只有**一個**呼叫點,
    而不是兩處各自組參數(參數組錯與複製實作一樣會讓 Phase 2 對不上)。

    key 形態:`<prefix>/legacy/<usage_log_uid>/<index>-<sha256(content)[:16]>.<ext>`;
    副檔名一律經 `extension_for_mime()` 推導(`build_object_key` 內部處理),
    **禁**自行 `mimetypes.guess_extension`。
    """
    return build_object_key(
        scope="legacy",
        owner_uid=usage_log_uid,
        index=index,
        content=content,
        mime=mime,
        key_prefix=key_prefix,
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
    """以 `pid` 游標撈下一批候選列(**唯讀**)。

    游標分批(`pid > :after_pid ORDER BY pid LIMIT :batch_size`)而非 OFFSET:
    OFFSET 在大表上每批都要重掃前綴,且中途有新列插入時會漏列
    (`04-databases/09-indexes-and-perf.md`)。

    Args:
        before_pid: `pid` 上界(含)。分窗執行用 —— 兩窗以 `--before-pid X` /
            `--after-pid X` 接軌即**不重不漏**(兩邊都以同一個 X 為界,一邊含、一邊不含)。

    SQL 走 `text(...).bindparams(...)`,**禁**字串拼接(`04-databases/04-sql-safety.md`)。
    """
    result = await session.execute(
        _SCAN_SQL.bindparams(
            after_pid=after_pid,
            before_pid=before_pid,
            pattern=_LIKE_PATTERN,
            batch_size=batch_size,
        )
    )
    rows: list[UsageLogRow] = []
    for pid, usage_log_uid, request_content, updated_at in result.all():
        rows.append(
            UsageLogRow(
                pid=int(pid),
                usage_log_uid=str(usage_log_uid),
                request_content=_coerce_request_content(request_content),
                updated_at=updated_at,
            )
        )
    return rows


async def count_remaining_base64_rows(session: AsyncSession) -> int:
    """仍含 base64 data URI 的列數 —— Phase 2 的完成判準(應為 0)。"""
    result = await session.execute(_REMAINING_SQL.bindparams(pattern=_LIKE_PATTERN))
    return int(result.scalar_one())


async def _process_attachment(
    row: UsageLogRow,
    ref: AttachmentRef,
    *,
    client: S3Client | None,
    key_prefix: str,
    dry_run: bool,
) -> _ItemResult:
    """處理單一圖片值:解析 → 算 key → 存在檢查 → 上傳。

    Returns:
        `_ItemResult`;**除設定錯以外不拋例外**,單一附件失敗只回 `failed`,由呼叫端
        記錄後續跑下一個(失敗列不擋整批)。

    Raises:
        S3ConfigError: 憑證 / bucket 設定錯 —— 這類錯誤每一列都會重演,繼續跑只會刷出
            滿版失敗清單,故視為致命、直接中止整批。
    """
    if is_remote_url(ref.value):
        # §D.2:遠端 URL 原樣保留、不代抓(避免 SSRF 面)。
        return _ItemResult("remote")

    parsed = parse_data_uri(ref.value)
    if parsed is None:
        # 畸形值不算失敗(本來就沒有可搬的內容),只計數供人工複核。
        return _ItemResult("invalid")

    key = legacy_object_key(
        usage_log_uid=row.usage_log_uid,
        index=ref.index,
        content=parsed.content,
        mime=parsed.mime,
        key_prefix=key_prefix,
    )

    if client is None:
        # dry-run 且環境沒有可用的 S3 client:只算「應上傳」,略過存在檢查。
        return _ItemResult("planned")

    try:
        exists = await client.head_object(key)
    except S3ConfigError:
        raise
    except S3Error as err:
        return _ItemResult("failed", _failure(row, ref, _REASON_HEAD_FAILED, err))

    if exists:
        # 冪等:同一把 key 已在 S3 → 直接跳過(重跑第二次應全數落在此分支)。
        return _ItemResult("existing")

    if dry_run:
        return _ItemResult("planned")

    try:
        await client.put_object(key, parsed.content, content_type_for_mime(parsed.mime))
    except S3ConfigError:
        raise
    except S3Error as err:
        return _ItemResult("failed", _failure(row, ref, _REASON_S3_FAILED, err))
    except Exception as err:  # noqa: BLE001 - 單一附件的未預期例外同樣不得中斷整批
        return _ItemResult("failed", _failure(row, ref, _REASON_S3_FAILED, type(err).__name__))

    return _ItemResult("uploaded")


def _failure(
    row: UsageLogRow,
    ref: AttachmentRef,
    reason: str,
    err: S3Error | str,
) -> Failure:
    """組失敗紀錄並記結構化 log。

    log **只**帶 pid / 序號 / 原因代碼 / AWS 錯誤碼與例外類別名:S3 原始訊息可能夾帶
    憑證或簽章,本專案 log 無機密過濾層(見 `app/clients/s3/errors.py` 檔頭)。
    """
    detail = err if isinstance(err, str) else f"{type(err).__name__}/{err.aws_code or '-'}"
    logger.warning(
        "遷移附件失敗 pid=%s index=%s reason=%s detail=%s",
        row.pid,
        ref.index,
        reason,
        detail,
    )
    return Failure(pid=row.pid, index=ref.index, reason=reason, detail=detail)


def _apply(report: MigrationReport, result: _ItemResult) -> None:
    if result.outcome == "uploaded":
        report.eligible += 1
        report.uploaded += 1
    elif result.outcome == "existing":
        report.eligible += 1
        report.existing += 1
    elif result.outcome == "planned":
        report.eligible += 1
        report.planned += 1
    elif result.outcome == "failed":
        report.eligible += 1
        if result.failure is not None:
            report.failures.append(result.failure)
    elif result.outcome == "remote":
        report.remote_skipped += 1
    else:
        report.invalid += 1


async def _process_items(
    items: Sequence[tuple[UsageLogRow, AttachmentRef]],
    *,
    client: S3Client | None,
    key_prefix: str,
    dry_run: bool,
    concurrency: int,
) -> list[_ItemResult]:
    """處理一批附件。

    預設 `concurrency=1`(單執行緒循序,安全優先);`>1` 時以 semaphore 限制同時進行的
    S3 呼叫數,結果仍依原順序回傳,報表數字不受併發影響。
    """
    if concurrency <= 1:
        return [
            await _process_attachment(
                row, ref, client=client, key_prefix=key_prefix, dry_run=dry_run
            )
            for row, ref in items
        ]

    semaphore = asyncio.Semaphore(concurrency)

    async def _guarded(row: UsageLogRow, ref: AttachmentRef) -> _ItemResult:
        async with semaphore:
            return await _process_attachment(
                row, ref, client=client, key_prefix=key_prefix, dry_run=dry_run
            )

    return list(await asyncio.gather(*(_guarded(row, ref) for row, ref in items)))


def _print_progress(line: str) -> None:
    """輸出一行進度到 stdout。

    why 用 `print(flush=True)` 而不是 logger:這是給人在 `nohup ... > log` 後 `tail -f`
    看的,要的是即時、無格式雜訊、與最終報表同一個 stream。全量掃描動輒數十分鐘且
    `LIKE '%data:%base64,%'` 走不到索引,沒有逐批輸出時完全無法分辨「在跑」與「卡死」。
    """
    print(line, flush=True)


async def run_upload(
    session: AsyncSession,
    *,
    client: S3Client | None,
    key_prefix: str,
    batch_size: int = _DEFAULT_BATCH_SIZE,
    limit: int = 0,
    dry_run: bool = False,
    concurrency: int = 1,
    after_pid: int = 0,
    before_pid: int = _MAX_PID,
) -> MigrationReport:
    """Phase 1 主流程:掃描 → 上傳 → 彙總報表。**全程對 DB 只有 SELECT**。

    每批的節奏是「讀 → 放掉交易 → 打 S3」(與 Phase 2 一致):`put_object` / `head_object`
    是網路 I/O,不能在持有交易時做。**這不只是效能問題** —— 一個橫跨整趟執行(可能數小時)
    的交易會把 xmin horizon 壓住,期間**全庫**產生的 dead tuple 都無法被 autovacuum 回收,
    正式站跑越久 bloat 累積越多。每批放掉,交易就只剩那一句 SELECT 的長度。

    Args:
        session: 唯讀用的 async session(呼叫端負責開 / 關)。本函式**每批結束會 rollback**
            (Phase 1 沒有任何寫入,rollback 純粹是「放掉交易」),因此呼叫端若把 session
            接在自己的外層交易上,需用 `join_transaction_mode="create_savepoint"`。
        client: S3 client;`None` 表「無可用 client」,僅 dry-run 允許(此時略過存在檢查)。
        key_prefix: `S3_KEY_PREFIX`,test / prod 各自 bucket 內的前綴。
        batch_size: 每批撈幾列(`pid` 游標)。
        limit: 最多處理幾列;`0` 表不限。
        dry_run: 只報統計,**不呼叫** `put_object`。
        concurrency: 同時進行的 S3 呼叫數上限;預設 1(循序)。
        after_pid: 從哪個 `pid` 之後開始(續跑 / 分窗下界)。
        before_pid: 處理到哪個 `pid` 為止(含;分窗上界)。

    Returns:
        `MigrationReport`;單列 / 單附件失敗只記入 `failures`,不中斷整批。
    """
    report = MigrationReport(last_pid=after_pid)
    cursor = after_pid
    remaining = limit if limit > 0 else None
    started = time.monotonic()
    batch_no = 0

    while True:
        size = batch_size if remaining is None else min(batch_size, remaining)
        if size <= 0:
            break

        rows = await fetch_batch(session, after_pid=cursor, before_pid=before_pid, batch_size=size)
        # 讀完立刻結束交易,不要帶著它去打 S3(理由見 docstring)。
        await session.rollback()
        if not rows:
            break

        batch_no += 1
        batch_started = time.monotonic()
        cursor = rows[-1].pid
        report.rows_scanned += len(rows)
        report.last_pid = cursor
        if remaining is not None:
            remaining -= len(rows)

        items: list[tuple[UsageLogRow, AttachmentRef]] = []
        for row in rows:
            refs = list(iter_image_attachments(row.request_content))
            if refs:
                report.rows_with_image += 1
            report.images_seen += len(refs)
            items.extend((row, ref) for ref in refs)

        for result in await _process_items(
            items,
            client=client,
            key_prefix=key_prefix,
            dry_run=dry_run,
            concurrency=concurrency,
        ):
            _apply(report, result)

        _print_progress(
            f"[upload] 批次 #{batch_no} pid<={cursor} 掃描 {report.rows_scanned} 列"
            f" / 圖片 {report.images_seen} / 上傳 {report.uploaded}"
            f" / 已存在 {report.existing} / 失敗 {report.failed}"
            f" · 本批 {time.monotonic() - batch_started:.1f}s"
            f" 累計 {time.monotonic() - started:.1f}s"
        )

    return report


def format_report(report: MigrationReport, *, dry_run: bool) -> str:
    """把報表排成人看的文字(給 stdout;失敗清單含 `pid` 供人工複核)。"""
    lines = [
        "",
        "=== --upload 完成(只上傳,DB 零變更)===",
        f"模式          : {'dry-run(不上傳)' if dry_run else '實際上傳'}",
        f"掃描列數      : {report.rows_scanned}(其中含圖片 {report.rows_with_image} 列)",
        f"走訪圖片值    : {report.images_seen}",
        f"應上傳 N      : {report.eligible}",
        f"實際上傳 M    : {report.uploaded}",
        f"已存在 K      : {report.existing}",
    ]
    if dry_run:
        lines.append(f"待上傳(預估) : {report.planned}")
    lines += [
        f"遠端 URL 略過 : {report.remote_skipped}",
        f"畸形值略過    : {report.invalid}",
        f"失敗          : {report.failed}",
        f"最後處理 pid  : {report.last_pid}(續跑 / 下一窗:--after-pid {report.last_pid})",
    ]
    if report.failures:
        lines.append("失敗清單(pid / 序號 / 原因 / 細節):")
        lines += [
            f"  - pid={f.pid} index={f.index} reason={f.reason} detail={f.detail}"
            for f in report.failures
        ]
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Phase 2:改寫 JSONB(本版唯一不可逆的操作)
# ---------------------------------------------------------------------------


def _pending(row: UsageLogRow, index: int, reason: str, detail: str) -> PendingRow:
    """組待處理條目並記結構化 log(log 不帶附件內容,對齊 `_failure()`)。"""
    logger.warning(
        "Phase 2 跳過附件 pid=%s index=%s reason=%s detail=%s",
        row.pid,
        index,
        reason,
        detail,
    )
    return PendingRow(
        pid=row.pid,
        usage_log_uid=row.usage_log_uid,
        index=index,
        reason=reason,
        detail=detail,
    )


def _is_already_rewritten(value: str) -> bool:
    """值是否已非 base64(S3 路徑 / 其他)→ 視為已完成(冪等,`_run_rewrite` 守則 5)。"""
    return not value.strip().lower().startswith("data:")


async def _plan_row(
    row: UsageLogRow,
    *,
    client: S3Client | None,
    key_prefix: str,
) -> _RowPlan:
    """驗證整列、產出改寫計畫,**完全不寫 DB**。

    每個附件值的判定順序(與 `iter_image_attachments()` 的序號規則搭配使用):
    遠端 URL → 已是路徑 → 畸形值 → 重算 key → `head_object`。

    Raises:
        S3ConfigError: 憑證 / bucket 設定錯,每列都會重演 → 視為致命,直接中止。
    """
    plan = _RowPlan(row=row)
    for ref in iter_image_attachments(row.request_content):
        plan.images_seen += 1

        if is_remote_url(ref.value):
            plan.remote += 1
            continue
        if _is_already_rewritten(ref.value):
            plan.already_path += 1
            continue

        parsed = parse_data_uri(ref.value)
        if parsed is None:
            # 畸形值沒有可搬的內容,改不了但也不該擋住同列其他附件;記入待處理清單。
            plan.invalid += 1
            plan.notes.append(_pending(row, ref.index, _REASON_MALFORMED, "-"))
            continue

        if client is None:
            # 無 client = 無法驗證物件是否存在 → 一律視為阻斷,絕不盲寫路徑。
            plan.blockers.append(_pending(row, ref.index, _REASON_S3_UNAVAILABLE, "-"))
            continue

        key = legacy_object_key(
            usage_log_uid=row.usage_log_uid,
            index=ref.index,
            content=parsed.content,
            mime=parsed.mime,
            key_prefix=key_prefix,
        )
        try:
            exists = await client.head_object(key)
        except S3ConfigError:
            raise
        except S3Error as err:
            detail = f"{type(err).__name__}/{err.aws_code or '-'}"
            plan.blockers.append(_pending(row, ref.index, _REASON_HEAD_FAILED, detail))
            continue

        if not exists:
            # 🔴 安全網:Phase 1 沒搬成功(或物件被刪)→ 整列跳過,絕不寫出指向空物件的路徑。
            plan.blockers.append(_pending(row, ref.index, _REASON_OBJECT_MISSING, key))
            continue

        plan.updates.append(_PlannedUpdate(ref=ref, key=key))

    return plan


def _absorb_plan(report: RewriteReport, plan: _RowPlan) -> None:
    """把單列的計畫結果併進報表(不含實際改寫數,那由寫入階段累加)。"""
    if plan.images_seen:
        report.rows_with_image += 1
    report.images_seen += plan.images_seen
    report.already_path += plan.already_path
    report.remote_skipped += plan.remote
    report.invalid += plan.invalid
    report.eligible += len(plan.updates)
    report.pending.extend(plan.notes)
    if plan.blocked:
        report.rows_skipped += 1
        report.pending.extend(plan.blockers)


async def _bypass_updated_at_trigger(session: AsyncSession) -> None:
    """停用本交易內的 user trigger,讓 `updated_at` 不被 DB trigger 覆寫(§D.7)。

    Raises:
        RewritePreconditionError: 權限不足。**刻意不降級續跑** —— 一旦續跑,
            全庫 `updated_at` 會被推成今天,而這件事沒有回頭路(除非還原備份)。
    """
    try:
        await session.execute(_TRIGGER_BYPASS_SQL)
    except DBAPIError as err:
        raise RewritePreconditionError(
            "無法設定 session_replication_role=replica(需 superuser 或 "
            "GRANT SET ON PARAMETER session_replication_role);"
            "不停用 trg_usage_logs_updated_at 就無法保留 updated_at,已中止。"
            f"({type(err.orig).__name__ if err.orig else type(err).__name__})"
        ) from err


async def _apply_batch(
    session: AsyncSession,
    plans: Sequence[_RowPlan],
    report: RewriteReport,
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
    await session.commit()


async def run_rewrite(
    session: AsyncSession,
    *,
    client: S3Client | None,
    key_prefix: str,
    batch_size: int = _DEFAULT_BATCH_SIZE,
    limit: int = 0,
    dry_run: bool = False,
    after_pid: int = 0,
    before_pid: int = _MAX_PID,
    skip_remaining_count: bool = False,
) -> RewriteReport:
    """Phase 2 主流程:掃描 → 重算 key → `head_object` 驗證 → 改寫 JSONB。

    每批的節奏刻意是「讀 → 放掉交易 → 打 S3 → 開寫入交易」:`head_object` 是網路 I/O,
    不能在持有交易時做(長交易會卡 autovacuum 與線上寫入)。

    重跑語意:已改寫的列不再符合 `LIKE '%data:%base64,%'`,下次掃描根本撈不到 ——
    因此「連跑兩次第二次 0 列」與「中斷後重跑只補未完成列」是同一個機制,不需要進度檔。

    Args:
        session: 可寫的 async session(**不可**套 Phase 1 的唯讀設定)。
        client: S3 client;`None` 時所有候選一律列入待處理,不會寫出任何路徑。
        key_prefix: `S3_KEY_PREFIX`,須與 Phase 1 跑的時候完全相同。
        batch_size: 每批撈幾列(`pid` 游標),每批一個 transaction。
        limit: 最多處理幾列;`0` 表不限。
        dry_run: 只報統計,**不執行任何 UPDATE**。
        after_pid: 從哪個 `pid` 之後開始(續跑 / 分窗下界)。
        before_pid: 處理到哪個 `pid` 為止(含;分窗上界)。
        skip_remaining_count: 略過收尾的完成判準查詢。那是一次**全表** count,分窗執行時
            每一窗都要付一次(且算的是全表、不是本窗),分窗跑完再單獨查一次即可。

    Returns:
        `RewriteReport`;單列問題只記入 `pending`,不中斷整批。

    Raises:
        RewritePreconditionError: 無權停用 `updated_at` trigger。
        S3ConfigError: S3 憑證 / bucket 設定錯。
    """
    report = RewriteReport(last_pid=after_pid)
    cursor = after_pid
    remaining = limit if limit > 0 else None
    started = time.monotonic()
    batch_no = 0

    while True:
        size = batch_size if remaining is None else min(batch_size, remaining)
        if size <= 0:
            break

        rows = await fetch_batch(session, after_pid=cursor, before_pid=before_pid, batch_size=size)
        # 讀完立刻結束唯讀交易:接下來的 head_object 是網路 I/O,不該佔著交易。
        await session.rollback()
        if not rows:
            break

        batch_no += 1
        batch_started = time.monotonic()
        cursor = rows[-1].pid
        report.rows_scanned += len(rows)
        report.last_pid = cursor
        if remaining is not None:
            remaining -= len(rows)

        plans = [await _plan_row(row, client=client, key_prefix=key_prefix) for row in rows]
        for plan in plans:
            _absorb_plan(report, plan)

        if dry_run:
            report.planned += sum(len(plan.updates) for plan in plans if not plan.blocked)
        else:
            await _apply_batch(session, plans, report)

        done = f"預計移除 {report.planned}" if dry_run else f"已移除 {report.rewritten}"
        _print_progress(
            f"[delete] 批次 #{batch_no} pid<={cursor} 掃描 {report.rows_scanned} 列"
            f" / 圖片 {report.images_seen} / {done}"
            f" / 整列跳過 {report.rows_skipped} / 待處理 {len(report.pending)}"
            f" · 本批 {time.monotonic() - batch_started:.1f}s"
            f" 累計 {time.monotonic() - started:.1f}s"
        )

    if not skip_remaining_count:
        report.remaining = await count_remaining_base64_rows(session)
        await session.rollback()
    return report


def format_rewrite_report(report: RewriteReport, *, dry_run: bool) -> str:
    """把 Phase 2 報表排成人看的文字;待處理清單含 `pid` 與原因供人工複核。"""
    lines = [
        "",
        "=== --delete 完成(移除 DB 內的 base64,不可逆)===",
        f"模式            : {'dry-run(不寫入)' if dry_run else '實際改寫'}",
        f"掃描列數        : {report.rows_scanned}(其中含圖片 {report.rows_with_image} 列)",
        f"走訪圖片值      : {report.images_seen}",
        f"可改寫 N        : {report.eligible}",
        f"實際改寫 M      : {report.rewritten}",
    ]
    if dry_run:
        lines.append(f"待改寫(預估)   : {report.planned}")
    lines += [
        f"已是路徑(冪等) : {report.already_path}",
        f"遠端 URL 略過   : {report.remote_skipped}",
        f"畸形值略過      : {report.invalid}",
        f"完成改寫列數    : {report.rows_rewritten}",
        f"整列跳過(安全網): {report.rows_skipped}",
        f"待處理清單      : {len(report.pending)} 筆",
        f"最後處理 pid    : {report.last_pid}(續跑 / 下一窗:--after-pid {report.last_pid})",
    ]
    if report.pending:
        lines.append("待處理清單(pid / 序號 / 原因 / 細節):")
        lines += [
            f"  - pid={p.pid} index={p.index} reason={p.reason} detail={p.detail}"
            for p in report.pending
        ]
    label = "尚待改寫列數(dry-run 前值)" if dry_run else "剩餘含 base64 列數(應為 0)"
    value = "未計算(--skip-remaining-count)" if report.remaining < 0 else str(report.remaining)
    lines += [f"{label}: {value}", ""]
    return "\n".join(lines)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="migrate_base64_to_s3",
        description="把 usage_logs.request_content 內的 base64 圖片搬到 S3(兩階段)。",
    )
    # 兩個 mode **互斥且必填**:argparse 會擋掉「兩個都給」與「都不給」。
    # why 不給預設 mode:`--delete` 不可逆,少打一個參數就跑掉是不能接受的失敗模式。
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--upload",
        action="store_true",
        help="階段一:把 base64 圖片上傳到 S3。**對 DB 只有 SELECT**,隨時可中止、零副作用",
    )
    mode.add_argument(
        "--delete",
        action="store_true",
        help="階段二:把 DB 欄位裡的 base64 換成 S3 物件路徑(**不可逆**,先看 runbook)。"
        "只動 usage_logs.request_content,不刪 S3 物件",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=_DEFAULT_BATCH_SIZE,
        help=f"每批撈幾列(pid 游標),預設 {_DEFAULT_BATCH_SIZE}。"
        "不是總量上限 —— 腳本會一直迴圈到撈不到列為止,每批印一行進度",
    )
    parser.add_argument("--limit", type=int, default=0, help="最多處理幾列;0=不限")
    parser.add_argument("--dry-run", action="store_true", help="只報統計,不上傳、不寫 DB")
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="同時進行的 S3 呼叫數上限;預設 1(循序,安全優先)。**僅 --upload 生效**;"
        "--delete 一律循序(寫入端維持每批一個 transaction)",
    )
    parser.add_argument(
        "--after-pid", type=int, default=0, help="從此 pid 之後開始(續跑 / 分窗下界)"
    )
    parser.add_argument(
        "--before-pid",
        type=int,
        default=0,
        help="處理到此 pid 為止(含;分窗上界)。0=不限。"
        "分窗以 --before-pid X / 下一窗 --after-pid X 接軌,不重不漏",
    )
    parser.add_argument(
        "--skip-remaining-count",
        action="store_true",
        help="**僅 --delete**:略過收尾的完成判準查詢(那是一次全表 count,分窗時每窗都要付"
        "一次且算的是全表);分窗全跑完再單獨查一次即可",
    )
    parser.add_argument(
        "--database-url",
        default="",
        help="覆寫 DATABASE_URL(預設取 Settings)",
    )
    return parser.parse_args(argv)


def _resolve_client(*, dry_run: bool) -> S3Client | None:
    """取 S3 client;dry-run 下取不到就降級為「不做存在檢查」。

    why 對 dry-run 放寬:dry-run 的用途是「先看有多少東西要搬」,在還沒配 AWS 憑證的
    dev 環境也該跑得起來;實跑則必須 fail-fast,否則會安靜地什麼都沒搬。
    """
    try:
        return get_s3_client()
    except S3Error as err:
        if not dry_run:
            raise
        print(f"[warn] 取不到 S3 client({type(err).__name__});dry-run 續跑,略過存在檢查")
        return None


def _resolve_before_pid(args: argparse.Namespace) -> int:
    """`--before-pid 0`(預設)= 不限 → 換成哨兵值。"""
    return args.before_pid if args.before_pid > 0 else _MAX_PID


async def _run_rewrite(args: argparse.Namespace, *, database_url: str, key_prefix: str) -> int:
    """Phase 2 進入點(task-531)。

    守則(對應 530 預留接入點時列的六條):

    1. key 由本檔的 `legacy_object_key()` + `iter_image_attachments()` **重算**,不另寫實作。
    2. 改寫前必先 `head_object`;不存在 → **整列**跳過並記入待處理清單。
    3. 寫回位置用 `AttachmentRef.path`;每批一個 transaction。
    4. `updated_at` 顯式寫回原值 + 交易內停用 DB trigger(見檔頭)。
    5. 值已非 `data:` 開頭 → 視為已完成,跳過(冪等)。
    6. 執行前須有已驗證可還原的 `pg_dump` —— 屬人工前置,寫在 runbook,本檔不代跑。

    本函式**自建** engine / session:Phase 1 的 `postgresql_readonly` 交易設定屬於
    Phase 1,**不可**套到這裡(這裡要寫入),也**不可**因為這裡要寫就把那邊的保護拿掉。
    """
    client = _resolve_client(dry_run=args.dry_run)
    engine = create_async_engine(database_url, echo=False, pool_pre_ping=True)
    maker = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        async with maker() as session:
            report = await run_rewrite(
                session,
                client=client,
                key_prefix=key_prefix,
                batch_size=args.batch_size,
                limit=args.limit,
                dry_run=args.dry_run,
                after_pid=args.after_pid,
                before_pid=_resolve_before_pid(args),
                skip_remaining_count=args.skip_remaining_count,
            )
    finally:
        await engine.dispose()

    print(format_rewrite_report(report, dry_run=args.dry_run))
    return 1 if report.pending else 0


async def _amain(args: argparse.Namespace) -> int:
    if 0 < args.before_pid <= args.after_pid:
        print(
            f"[error] --before-pid({args.before_pid})必須大於 --after-pid({args.after_pid}),"
            "否則這一窗永遠是空的"
        )
        return 2

    settings = get_settings()
    database_url = args.database_url or settings.DATABASE_URL
    if args.delete:
        return await _run_rewrite(
            args, database_url=database_url, key_prefix=settings.S3_KEY_PREFIX
        )

    client = _resolve_client(dry_run=args.dry_run)

    # 讓「Phase 1 不寫 DB」由 Postgres 端再保證一次:本 engine 的任何連線上任何寫入都會被
    # server 直接拒絕,而不是只靠 code review。
    # why 用連線層 GUC 而不是交易層的 `postgresql_readonly` execution option:Phase 1 現在
    # 每批讀完就 rollback 放掉交易(見 `run_upload`),交易層的設定在下一批就失效了;
    # `default_transaction_read_only` 綁在連線上,pool 裡每一條連線、每一個交易都適用。
    engine = create_async_engine(
        database_url,
        echo=False,
        pool_pre_ping=True,
        connect_args={"server_settings": {"default_transaction_read_only": "on"}},
    )
    maker = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    try:
        async with maker() as session:
            report = await run_upload(
                session,
                client=client,
                key_prefix=settings.S3_KEY_PREFIX,
                batch_size=args.batch_size,
                limit=args.limit,
                dry_run=args.dry_run,
                concurrency=args.concurrency,
                after_pid=args.after_pid,
                before_pid=_resolve_before_pid(args),
            )
    finally:
        await engine.dispose()

    print(format_report(report, dry_run=args.dry_run))
    return 1 if report.failures else 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        return asyncio.run(_amain(args))
    except RewritePreconditionError as err:
        print(f"[error] Phase 2 前置條件不足:{err}")
        return 2
    except S3Error as err:
        print(f"[error] S3 不可用({type(err).__name__}/{err.aws_code or '-'}),已中止")
        return 1


if __name__ == "__main__":
    sys.exit(main())
