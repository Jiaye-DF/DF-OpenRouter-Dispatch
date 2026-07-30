# Runbook — v2.2.1 歷史 base64 附件遷移(兩階段)

> **對應**:[`propose-v2.2.1.md`](./propose-v2.2.1.md) §B.3 / §D.6 / §D.7、task-530(Phase 1)、task-531(Phase 2)
> **執行對象**:`backend/scripts/migrate_base64_to_s3.py`
> **適用環境**:dev / staging 演練 → production 正式遷移

---

## 🔴 執行前必讀:回退只能靠備份還原,沒有其他退路

**Phase 2(`--delete`)是本版唯一不可逆的操作。**

它把 `usage_logs.request_content` 內的 base64 就地覆寫成 S3 物件路徑。**原始 base64 在覆寫後不存在於資料庫任何地方** —— 沒有暫存欄位、沒有影子表、沒有 mapping 檔(這是刻意的設計:本專案 [`AGENTS.md § 毀滅性操作禁止`](../../../AGENTS.md) 禁 `DROP COLUMN`,加了暫存欄位就沒有乾淨的退場路徑,詳見 propose §D.6)。

因此:

- **唯一的回退手段是還原 `pg_dump` 備份。** 沒有 `alembic downgrade`、沒有反向 script、沒有「從 S3 倒推回 base64」的自動流程。
- 備份「有跑過 dump」**不算數**,必須**實際驗證還原得起來**(見 §2)。
- Phase 1(`--upload`)則完全安全:它對 DB 只有 SELECT,跑到一半中止零副作用,可以放心先跑。

> 只跑 Phase 1 而不跑 Phase 2 是一個**完全合法的中間狀態**:S3 有副本、DB 照舊、系統行為等同現況。若對驗收結果有任何疑慮,停在這裡就好。

---

## 1. 前置檢查清單

**六項全過才准跑 Phase 2。跳過任一項,propose §風險所列的三層保護等於沒有。**

| # | 檢查項 | 判準 | 證據留存 |
| --- | --- | --- | --- |
| 1 | Phase 1 物件數比對 | Phase 1 報表「應上傳 N」== S3 實際物件數 | 報表輸出 + `aws s3 ls` 計數 |
| 2 | byte-for-byte 抽樣 **≥ 10 筆** | S3 物件內容 == 原 base64 decode 結果;涵蓋單輪 / messages 兩形狀、單圖 / 多圖 | 比對腳本輸出 |
| 3 | presigned URL 實開 | 抽樣物件以 presigned URL 開啟,圖片正常顯示 | 截圖 / 確認紀錄 |
| 4 | `pg_dump` 備份**且驗證可還原** | 備份檔還原到暫時 DB 後,`usage_logs` 筆數與抽樣內容相符 | §2 的還原驗證輸出 |
| 5 | `S3_STORAGE_ENABLED` 狀態確認 | 見下方說明 | `docker compose exec` 輸出 |
| 6 | DB 權限確認 | 執行帳號可設定 `session_replication_role`(見下方說明) | SQL 輸出 |

### 1-1 環境與參數一致性(最容易出錯的地方)

Phase 2 靠**重算**取得 Phase 1 用過的同一把 key。以下任一項與 Phase 1 不同,重算出的 key 就會對不上,結果是**整批被安全網擋下**(不會寫錯資料,但等於白跑):

```bash
docker compose -f docker-compose-prod.yml exec backend env | grep -E '^(S3_BUCKET|S3_KEY_PREFIX|S3_STORAGE_ENABLED|AWS_REGION)='
```

- `S3_KEY_PREFIX` **必須與 Phase 1 執行時完全相同**(它是 key 的第一段)。
- `S3_BUCKET` / `AWS_REGION` 必須指向 Phase 1 上傳的同一個 bucket。
- `S3_STORAGE_ENABLED`:**不影響**本 script(script 直接取 S3 client,不看這個開關)。但它決定**新請求**是否寫路徑;正式遷移前建議先開,否則遷移完成後新進來的請求又會寫入 base64,舊資料又長回來。
- `AWS_*` 金鑰只透過 env 注入,**禁**出現在指令列或 log(對齊 `00-overview/02-secrets.md`)。

### 1-2 DB 權限確認(Phase 2 專屬)

`usage_logs` 上掛著 DB 層 trigger `trg_usage_logs_updated_at`(`BEFORE UPDATE` 無條件 `NEW.updated_at = NOW()`)。要讓遷移**不污染 `updated_at`**(§D.7),script 會在每個寫入交易內送出:

```sql
SET LOCAL session_replication_role = replica;
```

這需要 **superuser**(或 PG15+ 由 DBA 執行 `GRANT SET ON PARAMETER session_replication_role TO <role>`)。權限不足時 script 會**直接中止**(exit code 2),不會退而求其次去污染 `updated_at`。

先確認:

```bash
docker compose -f docker-compose-prod.yml exec postgres \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
  "SELECT current_user, usesuper FROM pg_user WHERE usename = current_user;"
```

`usesuper = t` 即可。若為 `f`,請 DBA 先授權,**不要**改用「先 `ALTER TABLE ... DISABLE TRIGGER`」的做法 —— 那是全域生效 + ACCESS EXCLUSIVE lock,會擋住線上寫入,且 script 中斷時 trigger 會停在關閉狀態。

### 1-3 抽樣比對怎麼做(檢查項 2)

Phase 1 的 key 規則:`<S3_KEY_PREFIX>/legacy/<usage_log_uid>/<走訪序號>-<sha256(bytes)[:16]>.<副檔名>`。抽樣時:

1. 從 DB 撈候選列(含兩種形狀):

```bash
docker compose -f docker-compose-prod.yml exec postgres \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -c \
  "SELECT pid, usage_log_uid,
          (request_content ? 'messages') AS is_messages
   FROM usage_logs
   WHERE request_content::text LIKE '%data:%base64,%'
   ORDER BY random() LIMIT 12;"
```

2. 對每筆抽樣:把該 `usage_log_uid` 底下的 S3 物件抓下來,與原 base64 decode 後的 bytes 做 `sha256` 比對。key 檔名內的 16 碼本身就是內容 sha256 前綴,對得上即為 byte-for-byte 一致。

```bash
aws s3 ls "s3://$S3_BUCKET/$S3_KEY_PREFIX/legacy/<usage_log_uid>/"
```

3. 三種形狀各至少一筆:單輪單圖、單輪多圖、messages 模式。

---

## 2. `pg_dump` 備份與還原驗證

**備份是人工前置,script 不會、也不該代跑。**

### 2-1 備份

```bash
# 只備份 usage_logs(遷移只動這張表;還原時範圍最小、最快)
docker compose -f docker-compose-prod.yml exec -T postgres \
  pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
          --format=custom --table=usage_logs \
  > backup-usage_logs-$(date +%Y%m%d-%H%M).dump

# 建議另做一份全庫備份(遷移期間若有其他異動,全庫備份才救得回來)
docker compose -f docker-compose-prod.yml exec -T postgres \
  pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom \
  > backup-full-$(date +%Y%m%d-%H%M).dump

ls -lh backup-*.dump    # 檔案大小合理(base64 尚未退場,usage_logs 應為 MB~GB 級)
```

### 2-2 還原驗證(**這一步不能省**)

還原到**另一個暫時資料庫**,不碰正式庫:

```bash
# 1) 建暫時 DB
docker compose -f docker-compose-prod.yml exec postgres \
  psql -U "$POSTGRES_USER" -d postgres -c 'CREATE DATABASE restore_check;'

# 2) 還原(usage_logs 有 FK 指向 users / departments / models,單表還原用 --data-only 會
#    因外鍵失敗;驗證還原能力用 --no-owner --clean 還原到空庫即可)
docker compose -f docker-compose-prod.yml exec -T postgres \
  pg_restore -U "$POSTGRES_USER" -d restore_check --no-owner \
  < backup-full-$(date +%Y%m%d-%H%M).dump

# 3) 比對筆數與抽樣內容
docker compose -f docker-compose-prod.yml exec postgres psql -U "$POSTGRES_USER" -At \
  -d restore_check -c "SELECT count(*) FROM usage_logs;"
docker compose -f docker-compose-prod.yml exec postgres psql -U "$POSTGRES_USER" -At \
  -d "$POSTGRES_DB"  -c "SELECT count(*) FROM usage_logs;"
# ↑ 兩個數字必須相同

docker compose -f docker-compose-prod.yml exec postgres psql -U "$POSTGRES_USER" -At \
  -d restore_check -c \
  "SELECT count(*) FROM usage_logs WHERE request_content::text LIKE '%data:%base64,%';"
# ↑ 與正式庫的同一查詢結果必須相同(這是遷移前的基準數字,記下來)
```

> 驗證完 `restore_check` 可留著(直到遷移完成並觀察無誤再處理)。**本 runbook 不指示刪除任何資料庫** —— 依 `AGENTS.md § 毀滅性操作禁止`,`DROP DATABASE` 屬人類決策,需另行確認。

**把「遷移前含 base64 的列數」記下來**,§6 的完成判準要用:

```
BASE_ROWS = <上一步查到的數字>
```

---

## 3. 完整執行序列(Phase 1 → 驗收 → Phase 2,一律先 dry-run)

所有指令在 backend 容器內執行。**一律用 `-m` 模組形式**;`python scripts/migrate_base64_to_s3.py`
會因為 `/app` 不在 `sys.path` 而 `ModuleNotFoundError: No module named 'app'`。`-u` 讓逐批
進度即時吐出來(否則 buffer 住,`tail -f` 看不到東西)。

Coolify(正式站)—— 進 backend 容器 terminal:

```bash
cd /app
CMD="python -u -m scripts.migrate_base64_to_s3"
```

自建 docker compose:

```bash
CMD="docker compose -f docker-compose-prod.yml exec backend python -u -m scripts.migrate_base64_to_s3"
```

**長時間執行請丟背景**,容器 terminal 斷線會帶走前景 process(redeploy / 容器重啟仍會殺掉它,
但兩個 phase 都冪等,直接重跑即可):

```bash
nohup $CMD --upload > /tmp/migrate-upload.log 2>&1 &
tail -f /tmp/migrate-upload.log
```

每批會輸出一行進度,可據此判斷「在跑」與「卡死」:

```
[upload] 批次 #3 pid<=48213 掃描 150 列 / 圖片 190 / 上傳 188 / 已存在 2 / 失敗 0 · 本批 4.2s 累計 61.0s
```

每批預設 **50 列**,掃完自動結束 —— 不需要外部迴圈,也不需要記錄跑到哪裡。

### 3-1 `--upload` · 只上傳(DB 零變更)

```bash
# (a) 先 dry-run:只報數字,不上傳、不寫 DB
$CMD --upload --dry-run

# (b) 小範圍試跑:只處理前 50 列,確認 key / 內容正確
$CMD --upload --limit 50

# (c) 全量上傳
$CMD --upload
```

報表關鍵欄位:`應上傳 N` / `實際上傳 M` / `已存在 K` / `失敗`。
**`失敗` 不為 0 → 先查清楚再重跑**(重跑會自動跳過已上傳者,見 §4)。

> (a) 的 dry-run **可以省**:它的成本與實跑一樣(掃描才是瓶頸,不是上傳),而實跑的報表同樣
> 會給你「應上傳 N」。`--upload` 對 DB 只有 SELECT,跑一半中止零副作用。真正非跑不可的
> dry-run 是 §3-3 的 `--delete --dry-run`。

### 3-2 ✋ 人工驗收關卡

回到 **§1 前置檢查清單**,六項逐一打勾。**沒有全過就不要往下走。**

### 3-3 `--delete` · 移除 DB 內的 base64(不可逆)

```bash
# (a) 必跑 dry-run:報「可改寫 N / 待改寫」,不送出任何 UPDATE
$CMD --delete --dry-run

# (b) 小範圍實跑:先改 20 列,到明細頁確認圖片顯示正常
$CMD --delete --limit 20

# (c) 全量改寫
$CMD --delete
```

`--delete` 的行為保證:

- 每個 base64 值都會**重算** key(與 Phase 1 同一份實作)→ `head_object` 確認物件存在 → **才**改寫。
- **物件不存在 → 該列整列跳過**,並列入報表的「待處理清單」。**絕不**寫出指向不存在物件的路徑。
- 同一列只要有一張沒搬成功,**整列**都不改(避免半路徑半 base64 的中間態)。
- 改寫是 `jsonb_set` **單點置換**:`text` / `messages` 文字 / `tools` / 生成參數 / 記帳欄位一律不動。
- `updated_at` 顯式寫回原值 + 交易內停用 trigger(§1-2)。
- 每批一個 transaction;`head_object` 在交易之外進行(不佔長交易)。

Exit code:`0` = 全數完成、`1` = 有待處理項目(見 §4)、`2` = 前置條件不足(權限 / 環境)。

---

## 4. 中斷 / 失敗時的處置與重跑

### 4-1 重跑是安全的(兩個 phase 皆為冪等)

- **Phase 1 重跑**:上傳前先 `head_object`,已存在者跳過 → 第二次跑 `實際上傳 M = 0`、`已存在 K` = 全部。
- **Phase 2 重跑**:已改寫的列不再符合掃描條件(`request_content::text LIKE '%data:%base64,%'`),下一次**根本掃不到** → 「連跑兩次第二次 0 列」與「中斷後只補未完成列」是同一個機制,**不需要進度檔、不需要手動記錄跑到哪裡**。

因此:**Ctrl-C 中斷後,原指令直接重跑即可。** 只有想加速時才需要 `--after-pid`(報表末行的
「最後處理 pid」就是要餵給它的值):

```bash
$CMD --delete --after-pid 123456
```

### 4-4 大表分窗執行(`--before-pid`,選用)

正式站一趟全量可能數十分鐘到數小時 —— 掃描條件 `LIKE '%data:%base64,%'` 走不到索引,整表
JSONB 都得從 TOAST 拉出來轉 text。

**多數情況不需要分窗**:每批 50 列已經是可控的分期付款(每批一行進度、交易只有一句 SELECT
的長度),中斷後原指令直接重跑即可補完。分窗只在「想把一趟切成幾個獨立 process、各自跑完
就收工」時才用得上。

切法按 `pid`(`BIGSERIAL PRIMARY KEY`、單調遞增等同時間序,也是唯一走得到索引的切法 ——
`usage_logs` 沒有單獨的 `created_at` 索引)。兩窗以**同一個 pid** 接軌即不重不漏
(`--before-pid` 含上界、`--after-pid` 不含下界):

```bash
$CMD --upload --before-pid 100000
# 報表末行:「最後處理 pid : 99987」→ 直接當下一窗的下界
$CMD --upload --after-pid 99987 --before-pid 200000
$CMD --upload --after-pid 199932            # 尾段不設上界
```

分窗的額外好處:每一窗是獨立 process,記憶體在窗之間釋放。

**`--delete` 分窗務必加 `--skip-remaining-count`**:完成判準是一次**全表** count,每一窗都付
一次很浪費(而且它算的是全表、不是本窗)。全部窗跑完再依 §6-1 單獨查一次:

```bash
$CMD --delete --before-pid 100000 --skip-remaining-count
```

窗要開多大:`--upload` 的成本主要在掃描,窗小一點(數千 pid)沒關係;`--delete` 每窗有
process 啟動與連線建立的固定成本,窗開大一些較划算 —— 真正要控的「單一 transaction 大小」
是 `--batch-size` 在管,不是窗。

### 4-2 待處理清單的原因代碼

報表末尾的「待處理清單」逐筆列出 `pid` / 走訪序號 / 原因 / 細節:

| 原因代碼 | 意義 | 處置 |
| --- | --- | --- |
| `s3_object_missing` | **安全網生效**:重算出的 key 在 S3 不存在 → 整列未改寫 | 回去補跑 Phase 1(`--upload`),再重跑 Phase 2。若補跑後仍缺,檢查 `S3_KEY_PREFIX` / `S3_BUCKET` 是否與 Phase 1 一致 |
| `s3_head_failed` | `head_object` 呼叫失敗(逾時 / 權限) | 排除 S3 問題後直接重跑 |
| `s3_unavailable` | 取不到 S3 client(dry-run 才會出現) | 補上 `AWS_*` env 再跑 |
| `malformed_data_uri` | 該值本身不是合法 base64 data URI(歷史髒資料) | **無內容可搬,無法改寫**。不擋同列其他附件;需人工判斷是否保留原值(見 §6 註記) |
| `row_value_changed` | 掃描後該節點被其他寫入改過(樂觀鎖沒中) | 極罕見。直接重跑即可 |

### 4-3 執行到一半 DB / S3 掛掉

- 已 commit 的批次是完整的(每批一個 transaction,不會有寫到一半的列)。
- 未 commit 的批次自動 rollback。
- 直接重跑,不需要任何清理動作。

---

## 5. 回退程序(**只能靠備份還原**)

> 再說一次:**沒有其他退路。** 沒有 `alembic downgrade`、沒有反向 script、沒有從 S3 倒推回 base64 的流程。

### 5-1 判斷是否需要回退

| 情況 | 要回退嗎 |
| --- | --- |
| 待處理清單有項目,但已改寫的列都正常 | **不用**。排除原因後重跑補完即可(§4) |
| 明細頁圖片顯示不出來,但 S3 物件存在 | **不用**。屬讀取端問題(presigned URL / 前端),走一般修復流程 |
| 改寫後發現 key 指向的物件內容錯誤(搬錯內容) | **要**。這是資料正確性問題 |
| `updated_at` 被大量污染 | **要**。該欄位語意已壞,無法就地修回 |

### 5-2 還原步驟

```bash
# 1) 先停掉會寫入 usage_logs 的服務(避免還原期間有新寫入)
docker compose -f docker-compose-prod.yml stop backend taskiq-worker taskiq-scheduler

# 2) 還原(單表:先還原到暫時 DB,再把 usage_logs 搬回去,避免 --clean 影響其他表)
docker compose -f docker-compose-prod.yml exec postgres \
  psql -U "$POSTGRES_USER" -d postgres -c 'CREATE DATABASE rollback_src;'
docker compose -f docker-compose-prod.yml exec -T postgres \
  pg_restore -U "$POSTGRES_USER" -d rollback_src --no-owner < backup-full-<timestamp>.dump

# 3) 由 DBA 確認後,把 usage_logs 的 request_content 逐列搬回正式庫
#    ⚠️ 這一步會覆寫正式資料,必須有人類明確確認;請 DBA 依當下狀況擬定
#       UPDATE 範圍(建議以 pid 區間限縮到本次遷移確實改過的列)。

# 4) 服務啟回
docker compose -f docker-compose-prod.yml start backend taskiq-worker taskiq-scheduler
```

**注意**:還原後 S3 上的物件仍然存在(它們不佔 DB、不影響正確性),**不需要刪除** —— 留著反而讓下次重跑直接命中 `已存在 K`。

### 5-3 回退後的 follow-up

對齊 `06-Coolify-CD/06-rollback.md`,24 小時內:寫 `fixed.md`(根因 / 影響範圍 / 修正計畫)、開重跑 task、評估是否升規。

---

## 6. 完成判準與收尾驗證

### 6-1 完成判準

```bash
docker compose -f docker-compose-prod.yml exec postgres \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -c \
  "SELECT count(*) FROM usage_logs WHERE request_content::text LIKE '%data:%base64,%';"
```

- **期望值 0。**
- 若不為 0,先看 Phase 2 報表的待處理清單:`malformed_data_uri`(歷史髒資料,無內容可搬)**永遠**會殘留在這個查詢裡,因為畸形值本身仍長得像 `data:...base64,`。此時把畸形值列數扣掉後應為 0:

```bash
docker compose -f docker-compose-prod.yml exec postgres \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -c \
  "SELECT pid, usage_log_uid FROM usage_logs
   WHERE request_content::text LIKE '%data:%base64,%' ORDER BY pid;"
```
  逐筆與報表的待處理清單核對,確認**每一筆都有對應的原因代碼**;有任何一筆對不上,代表有列被漏掉,**不要**宣告完成。

### 6-2 收尾驗證(全部要做)

```bash
# (1) updated_at 未被污染:遷移不該讓「最後異動時間」跳到今天
docker compose -f docker-compose-prod.yml exec postgres \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -c \
  "SELECT count(*) FROM usage_logs WHERE updated_at::date = CURRENT_DATE;"
# ↑ 應與遷移前的同一查詢結果相同(遷移前先記下基準數字)

# (2) 沒有指向不存在物件的路徑:抽樣 ≥ 10 筆,逐一 head-object
docker compose -f docker-compose-prod.yml exec postgres \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -c \
  "SELECT jsonb_array_elements_text(request_content -> 'images')
   FROM usage_logs
   WHERE request_content ? 'images' ORDER BY random() LIMIT 10;" \
| while read -r key; do aws s3api head-object --bucket "$S3_BUCKET" --key "$key" >/dev/null \
    && echo "OK   $key" || echo "MISS $key"; done
# ↑ 不得出現任何 MISS

# (3) 資料量下降(JSONB 由 MB 級降為 KB 級)
docker compose -f docker-compose-prod.yml exec postgres \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -c \
  "SELECT pg_size_pretty(pg_total_relation_size('usage_logs'));"
# ↑ TOAST 空間要等 VACUUM 才會釋出;必要時由 DBA 安排 VACUUM(不要在遷移中順手跑)
```

### 6-3 人工驗收

- 明細頁 `usage-logs/<uid>` 抽樣 **≥ 10 筆**(涵蓋單輪 / messages、單圖 / 多圖):圖片正常顯示,且內容與遷移前一致。
- 未遷移列(若有殘留畸形值)與已遷移列**同頁並存不互相干擾**。
- AI 評估 / 重跑鏈路對含圖紀錄照常運作。

### 6-4 收尾

1. 把 Phase 1 / Phase 2 的**完整報表輸出**、四條前置驗收證據、§6-1 / §6-2 的查詢結果貼進 PR 描述。
2. 備份檔依公司備份政策歸檔(**不要**在遷移完成當天就清掉)。
3. 確認 `S3_STORAGE_ENABLED=true` 已生效,否則新請求又會寫入 base64。
4. 更新 `docs/Tasks/v2.2/tasks-v2.2.1.md` 的 checkbox 與頂部狀態。

---

## 附錄:script 參數速查

| 參數 | 說明 |
| --- | --- |
| `--upload` / `--delete` | **互斥且必填**。`--upload` = 只上傳(DB 零變更);`--delete` = 移除 DB 欄位內的 base64、換成物件路徑(**不可逆**;不刪 S3 物件)。兩個都給或都不給,argparse 直接擋 |
| `--dry-run` | 只報統計:`--upload` 不上傳、`--delete` 不送出任何 UPDATE |
| `--batch-size N` | 每批撈幾列(`pid` 游標),**預設 50**;`--delete` 每批一個 transaction。**注意這不是總量上限**,腳本會一直迴圈到撈不到列為止,每批印一行進度 |
| `--limit N` | 最多處理幾列,`0` = 不限。小範圍試跑用 |
| `--after-pid N` | 從此 `pid` 之後開始(**不含**;續跑 / 分窗下界) |
| `--before-pid N` | 處理到此 `pid` 為止(**含**;分窗上界),`0` = 不限。見 §4-4 |
| `--skip-remaining-count` | **僅 `--delete`**:略過收尾的全表 count 完成判準;分窗執行時必加,見 §4-4 |
| `--concurrency N` | **僅 `--upload`**:同時進行的 S3 呼叫數上限,預設 1(循序) |
| `--database-url URL` | 覆寫 `DATABASE_URL`(預設取 `Settings`) |

Exit code:`0` = 無待處理 / 無失敗;`1` = 有失敗或待處理項目;`2` = 前置條件不足(如無權停用 `updated_at` trigger)。
