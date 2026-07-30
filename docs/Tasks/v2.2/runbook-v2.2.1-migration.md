# Runbook — v2.2.1 歷史 base64 附件遷移

> **對應**:[`propose-v2.2.1.md`](./propose-v2.2.1.md) §B.3 / §D.6 / §D.7、task-530、task-531
> **執行對象**:`backend/scripts/migrate_base64_to_s3.py`
> **適用環境**:dev / staging 演練 → production 正式遷移

一支指令走完:掃描 → 上傳 S3 → 就地把 base64 改寫成物件路徑。

```bash
cd /app && python -m scripts.migrate_base64_to_s3
```

> **2026-07-30 改版**:原本的兩階段(`--phase upload` / `--phase rewrite`,後改為
> `--upload` / `--delete`)已合併為單一流程,mode 參數全部移除。舊的兩階段設計把「上傳」與
> 「改寫」拆開是為了中間卡一道人工驗收;現在改為**上傳成功才改寫該值、同列有任何附件沒搬
> 成功就整列不改**,安全性由這條保證接手,驗收改在 `--dry-run` 與 `--limit` 小範圍試跑做。

---

## 🔴 執行前必讀:回退只能靠備份還原

改寫是**就地覆寫**:原始 base64 在覆寫後不存在於資料庫任何地方 —— 沒有暫存欄位、沒有影子
表、沒有 mapping 檔(這是刻意的設計:本專案 [`AGENTS.md § 毀滅性操作禁止`](../../../AGENTS.md)
禁 `DROP COLUMN`,加了暫存欄位就沒有乾淨的退場路徑,詳見 propose §D.6)。

- **唯一的回退手段是還原 `pg_dump` 備份。** 沒有 `alembic downgrade`、沒有反向 script、
  沒有「從 S3 倒推回 base64」的自動流程。
- 備份「有跑過 dump」**不算數**,必須**實際驗證還原得起來**(見 §2)。
- `--dry-run` 完全安全:不上傳、不寫 DB,跑到一半中止零副作用。

---

## 1. 前置檢查(四項全過才准跑)

| # | 檢查項 | 判準 |
| --- | --- | --- |
| 1 | S3 權限探測 | `head_object` 對不存在的 key 回 `False`(**不是**拋 403) |
| 2 | 環境變數 | `S3_BUCKET` / `S3_KEY_PREFIX` / `AWS_REGION` / 憑證皆有值 |
| 3 | DB 權限 | 執行帳號可設定 `session_replication_role` |
| 4 | `pg_dump` 備份**且驗證可還原** | 見 §2 |

### 1-1 S3 權限探測(最容易錯的一項)

```bash
cd /app
python -c "
import asyncio
from app.clients.s3 import get_s3_client
async def main():
    c = get_s3_client()
    print('head_object(不存在的 key) =', await c.head_object('probe/definitely-not-there'))
asyncio.run(main())
"
```

**期望 `False`。** 拋 403 / AccessDenied 就是 IAM policy 寫錯:`s3:ListBucket` 是 bucket
層級,Resource 必須是 `arn:aws:s3:::<bucket>`,**結尾不可有斜線、也不可是 `/*`**;物件層級
動作(`GetObject` / `PutObject`)才配 `/*`。寫錯不會有明確錯誤,只會讓 `head_object` 對不
存在的物件回 403 而非 404,遷移腳本會把**每一列**都判成失敗。拆成兩個 Statement 最不易錯。

> 為什麼要單獨探測:`--dry-run` 在取不到 S3 client 時只會印個 warn 就繼續跑 ——
> **dry-run 跑得動不代表權限是對的**。

### 1-2 環境變數

```bash
env | grep -E '^(APP_ENV|S3_STORAGE_ENABLED|S3_BUCKET|S3_KEY_PREFIX|AWS_REGION)='
[ -n "$AWS_ACCESS_KEY_ID" ] && echo "AWS_ACCESS_KEY_ID: set" || echo "AWS_ACCESS_KEY_ID: EMPTY"
```

金鑰**禁**出現在指令列或 log(對齊 `00-overview/02-secrets.md`)。

`S3_STORAGE_ENABLED` **不影響**本 script(它直接取 S3 client,不看這個開關),但它決定
**新請求**是否寫路徑;遷移前建議先開,否則遷移完成後新進來的請求又會寫入 base64。

### 1-3 DB 權限

`usage_logs` 掛著 DB 層 trigger `trg_usage_logs_updated_at`(`BEFORE UPDATE` 無條件
`NEW.updated_at = NOW()`)。要讓遷移**不污染 `updated_at`**,script 會在每個寫入交易內送出
`SET LOCAL session_replication_role = replica`。這需要 **superuser**(或 PG15+ 由 DBA 執行
`GRANT SET ON PARAMETER session_replication_role TO <role>`)。權限不足時 script **直接中止**
(exit code 2),不會退而求其次去污染 `updated_at`。

```bash
python -c "
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import get_settings
async def main():
    e = create_async_engine(get_settings().DATABASE_URL)
    async with e.connect() as c:
        print((await c.execute(text('SELECT current_user, usesuper FROM pg_user WHERE usename = current_user'))).one())
    await e.dispose()
asyncio.run(main())
"
```

`usesuper = True` 即可。若為 `False`,請 DBA 先授權,**不要**改用
`ALTER TABLE ... DISABLE TRIGGER` —— 那是全域生效 + ACCESS EXCLUSIVE lock,會擋住線上寫入,
且 script 中斷時 trigger 會停在關閉狀態。

### 1-4 磁碟餘量

改寫是 UPDATE:寫新版本、舊版本留成 dead tuple。全量改寫等於整張表含 TOAST 重寫一遍,
**VACUUM 前磁碟用量會接近兩倍**。餘量不足就用 `--before-pid` 分段跑,中間讓 autovacuum 追上。

```bash
python -c "
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import get_settings
async def main():
    e = create_async_engine(get_settings().DATABASE_URL)
    async with e.connect() as c:
        print('usage_logs =', (await c.execute(text(\"SELECT pg_size_pretty(pg_total_relation_size('usage_logs'))\"))).scalar_one())
    await e.dispose()
asyncio.run(main())
"
df -h /var/lib/postgresql/data     # 在 DB 主機 / 容器內
```

---

## 2. `pg_dump` 備份與還原驗證

**備份是人工前置,script 不會、也不該代跑。**

```bash
# 全庫備份(遷移期間若有其他異動,全庫備份才救得回來)
docker compose -f docker-compose-prod.yml exec -T postgres \
  pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom \
  > backup-full-$(date +%Y%m%d-%H%M).dump
ls -lh backup-*.dump
```

**還原驗證(這一步不能省)** —— 還原到另一個暫時資料庫,不碰正式庫:

```bash
docker compose -f docker-compose-prod.yml exec postgres \
  psql -U "$POSTGRES_USER" -d postgres -c 'CREATE DATABASE restore_check;'
docker compose -f docker-compose-prod.yml exec -T postgres \
  pg_restore -U "$POSTGRES_USER" -d restore_check --no-owner < backup-full-<timestamp>.dump

# 兩個數字必須相同
docker compose -f docker-compose-prod.yml exec postgres psql -U "$POSTGRES_USER" -At \
  -d restore_check -c "SELECT count(*) FROM usage_logs;"
docker compose -f docker-compose-prod.yml exec postgres psql -U "$POSTGRES_USER" -At \
  -d "$POSTGRES_DB"  -c "SELECT count(*) FROM usage_logs;"
```

> 本 runbook **不指示刪除任何資料庫** —— 依 `AGENTS.md § 毀滅性操作禁止`,`DROP DATABASE`
> 屬人類決策,需另行確認。

---

## 3. 執行

```bash
cd /app

# (a) 先看數字:不上傳、不寫 DB
python -m scripts.migrate_base64_to_s3 --dry-run

# (b) 小範圍實跑:只處理前 50 列,到明細頁確認圖片顯示正常
python -m scripts.migrate_base64_to_s3 --limit 50

# (c) 全量(長時間執行丟背景 —— 容器 terminal 斷線會帶走前景 process)
nohup python -m scripts.migrate_base64_to_s3 > /tmp/migrate.log 2>&1 &
tail -f /tmp/migrate.log
```

**一律用 `-m` 模組形式**;`python scripts/migrate_base64_to_s3.py` 會因為 `/app` 不在
`sys.path` 而 `ModuleNotFoundError: No module named 'app'`。

每批 50 列印一行進度:

```
[migrate] 開始:掃描 pid 1~482913,每批 50 列
[migrate] #1 pid 50/482913(0.0%) 掃描 50 列 / 含圖 3 列 / 上傳 4 / 已存在 0 / 已改寫 4 / 整列跳過 0 · 本批 1.2s 累計 1.2s
```

**跑的期間不要 redeploy** —— 會把容器換掉、process 一起沒。真被殺掉也沒關係,原指令直接
重跑即可(見 §4)。

Exit code:`0` = 無待處理;`1` = 有待處理項目;`2` = 前置條件不足(權限 / 環境)。

### 行為保證

- 上傳成功才改寫該值;`put_object` / `head_object` 失敗 → 不改寫。
- **同一列有任何附件沒搬成功 → 整列都不改**(避免半路徑半 base64 的中間態)。
- 改寫是 `jsonb_set` **單點置換**:`text` / `messages` 文字 / `tools` / 生成參數 / 記帳欄位
  一律不動;另以 `#>> path = :expected` 做樂觀鎖。
- `updated_at` 顯式寫回原值 + 交易內停用 trigger(§1-3)。
- 每批一個 transaction;S3 呼叫在交易之外(不佔長交易)。
- 物件 key 依該列**當初的 `created_at`** 分層:
  `<prefix>/chat/<YYYY>/<MM>/<DD>/<usage_log_uid>/<走訪序號>-<sha256[:16]>.<ext>`

---

## 4. 中斷 / 失敗時的處置

### 4-1 重跑是安全的(冪等)

- 已改寫的值不是 `data:` 開頭 → 直接跳過。
- 已上傳的物件 `head_object` 命中 → 不重傳。

**Ctrl-C 中斷後,原指令直接重跑即可。** 想跳過已處理區段就用報表末行給的「最後處理 pid」:

```bash
python -m scripts.migrate_base64_to_s3 --after-pid 123456
```

### 4-2 待處理清單的原因代碼

| 原因代碼 | 意義 | 處置 |
| --- | --- | --- |
| `s3_upload_failed` | `put_object` 失敗 → 整列未改寫 | 排除 S3 問題後直接重跑 |
| `s3_head_failed` | `head_object` 呼叫失敗(逾時 / 權限) | 同上;先確認 §1-1 探測仍是 `False` |
| `s3_unavailable` | 取不到 S3 client(只有 dry-run 會出現) | 補上 `AWS_*` env 再跑 |
| `malformed_data_uri` | 該值本身不是合法 base64 data URI(歷史髒資料) | **無內容可搬,無法改寫**。不擋同列其他附件;需人工判斷是否保留原值 |
| `row_value_changed` | 掃描後該節點被其他寫入改過(樂觀鎖沒中) | 極罕見。直接重跑即可 |

### 4-3 執行到一半 DB / S3 掛掉

已 commit 的批次是完整的(每批一個 transaction),未 commit 的自動 rollback。直接重跑,
不需要任何清理動作。

### 4-4 分段執行(選用)

`--after-pid` / `--before-pid` 可把一趟切成幾個獨立 process(上界含、下界不含,兩窗以同一個
pid 接軌即不重不漏)。正常情況不需要 —— 每批 50 列已經是可控的分期付款,且中斷可重跑。
磁碟餘量不足時分段跑、中間讓 autovacuum 追上,是它主要的用途。

```bash
python -m scripts.migrate_base64_to_s3 --before-pid 100000
python -m scripts.migrate_base64_to_s3 --after-pid 100000 --before-pid 200000
python -m scripts.migrate_base64_to_s3 --after-pid 200000     # 尾段不設上界
```

---

## 5. 回退(**只能靠備份還原**)

| 情況 | 要回退嗎 |
| --- | --- |
| 待處理清單有項目,但已改寫的列都正常 | **不用**。排除原因後重跑補完(§4) |
| 明細頁圖片顯示不出來,但 S3 物件存在 | **不用**。屬讀取端問題,走一般修復流程 |
| 改寫後發現 key 指向的物件內容錯誤 | **要**。資料正確性問題 |
| `updated_at` 被大量污染 | **要**。該欄位語意已壞,無法就地修回 |

```bash
# 1) 先停掉會寫入 usage_logs 的服務
docker compose -f docker-compose-prod.yml stop backend taskiq-worker taskiq-scheduler

# 2) 還原到暫時 DB
docker compose -f docker-compose-prod.yml exec postgres \
  psql -U "$POSTGRES_USER" -d postgres -c 'CREATE DATABASE rollback_src;'
docker compose -f docker-compose-prod.yml exec -T postgres \
  pg_restore -U "$POSTGRES_USER" -d rollback_src --no-owner < backup-full-<timestamp>.dump

# 3) ⚠️ 由 DBA 確認後,把 usage_logs 的 request_content 逐列搬回正式庫。
#    這一步會覆寫正式資料,必須有人類明確確認;建議以 pid 區間限縮到本次確實改過的列。

# 4) 服務啟回
docker compose -f docker-compose-prod.yml start backend taskiq-worker taskiq-scheduler
```

還原後 S3 上的物件仍然存在(不佔 DB、不影響正確性),**不需要刪除** —— 留著反而讓下次重跑
直接命中「已存在」。

回退後 24 小時內依 `06-Coolify-CD/06-rollback.md` 寫 `fixed.md`(根因 / 影響範圍 / 修正計畫)。

---

## 6. 完成判準與收尾驗證

報表末行的 **`仍含 base64 列數`** 就是完成判準,**由本次掃描直接算出**,不需要另外查詢。

- **期望 0。**
- 不為 0 時,逐筆與待處理清單核對:`malformed_data_uri`(歷史髒資料,無內容可搬)會**永久**
  留在這個數字裡,屬資料現實非遷移失敗。有任何一筆對不上清單,代表有列被漏掉,
  **不要**宣告完成。

收尾驗證(全部要做):

```bash
# (1) updated_at 未被污染:遷移不該讓「最後異動時間」跳到今天
docker compose -f docker-compose-prod.yml exec postgres \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -c \
  "SELECT count(*) FROM usage_logs WHERE updated_at::date = CURRENT_DATE;"
# ↑ 應與遷移前的同一查詢結果相同(遷移前先記下基準數字)

# (2) 沒有指向不存在物件的路徑:抽樣 ≥ 10 筆逐一 head-object
docker compose -f docker-compose-prod.yml exec postgres \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -c \
  "SELECT jsonb_array_elements_text(request_content -> 'images')
   FROM usage_logs WHERE request_content ? 'images' ORDER BY random() LIMIT 10;"
# ↑ 逐一確認物件存在,不得有缺

# (3) 資料量下降(JSONB 由 MB 級降為 KB 級)
docker compose -f docker-compose-prod.yml exec postgres \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -c \
  "SELECT pg_size_pretty(pg_total_relation_size('usage_logs'));"
# ↑ TOAST 空間要等 VACUUM 才會釋出;必要時由 DBA 安排(不要在遷移中順手跑)
```

人工驗收:

- 明細頁 `usage-logs/<uid>` 抽樣 **≥ 10 筆**(涵蓋單輪 / messages、單圖 / 多圖):圖片正常
  顯示,且內容與遷移前一致。
- AI 評估 / 重跑鏈路對含圖紀錄照常運作。

收尾:

1. 把完整報表輸出、前置驗收證據、§6 的查詢結果貼進 PR 描述。
2. 備份檔依公司備份政策歸檔(**不要**在遷移完成當天就清掉)。
3. 確認 `S3_STORAGE_ENABLED=true` 已生效,否則新請求又會寫入 base64。
4. 更新 `docs/Tasks/v2.2/tasks-v2.2.1.md` 的 checkbox 與頂部狀態。

---

## 附錄:參數速查

| 參數 | 說明 |
| --- | --- |
| `--dry-run` | 只報統計:不上傳、不寫 DB |
| `--batch-size N` | 每批撈幾列(`pid` 游標),**預設 50**,每批一個 transaction。不是總量上限 —— 腳本會一直迴圈到掃完為止,每批印一行進度 |
| `--limit N` | 最多處理幾列,`0` = 不限。小範圍試跑用 |
| `--after-pid N` | 從此 `pid` 之後開始(**不含**;續跑 / 分段下界) |
| `--before-pid N` | 掃描到此 `pid` 為止(**含**;分段上界),`0` = 不限 |
| `--database-url URL` | 覆寫 `DATABASE_URL`(預設取 `Settings`) |

Exit code:`0` = 無待處理;`1` = 有待處理項目;`2` = 前置條件不足(如無權停用 `updated_at` trigger)。
