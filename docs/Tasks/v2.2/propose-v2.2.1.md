[//]: # (此檔為 v2.2.1 任務提案,實作前先由使用者確認範圍與設計取捨。Agent 草擬、User 拍板。)

# Propose v2.2.1 · 圖片 / 檔案改存 S3,DB 只留物件路徑(base64 棄用)

> 此為 **proposal**(詳設母本),確認後即據以拆 `tasks/`。
>
> 本版一支主題、兩個工作面,彼此有先後相依(先有寫入端與物件儲存能力,才能跑歷史遷移):
> 1. **寫入端改道**:今後所有含圖片 / 檔案的代理請求,附件一律落 **S3(`df-openrouter-dispatch-prod`)**,`usage_logs.request_content` 只留**物件路徑**。
> 2. **歷史資料遷移(兩階段)**:既有 `request_content` 內的 base64(data URI)圖片先**全數搬上 S3 但不動 DB**,人工驗收確認搬遷成功後,才改寫成路徑 —— **base64 於第二階段才退場**。
>
> **狀態**:**✅ 範圍與設計取捨已鎖定,可拆 tasks**(2026-07-29)。§D.3 / D.4 / D.5 / D.6 + 「先補 Design-Base 物件儲存規範檔」由 user 逐項拍板;D.1 / D.2 / D.7 / D.8 / D.9 採 Agent 建議為實作預設(未反對即採)。唯一待辦前置:上線前 rotate AWS 金鑰 + IAM 權限收斂(決議表 #13)。
>
> **本版的一句話邊界(user 定調)**:**「改的只是平台後端 log 儲存路徑而已。」** 送給下游模型的東西、回給 SDK 呼叫端的東西,**一律不動**。任何 task 若觸及下游 payload 或對外回應,即為越界。

---

## ⚠️ 版號判定註記

依 [`01-propose/05-version-bump.md`](../../Design-Base/01-propose/05-version-bump.md) 判準:

- **對外 API 契約不變**:`POST /api/v1/model/chat`(與 deprecated alias)的 request schema 完全不動 —— 呼叫端**仍可照舊送 base64 data URI**,不需要改任何 SDK 端程式碼。無 endpoint 移除 / 改名、無必填欄位新增、無 DB column 移除或改型別 → **不是 breaking**。
- 有變的是 **`usage_logs.request_content` JSONB 內的值語意**(`images[]` / `image_url.url` 由「base64 data URI」變成「S3 物件路徑」),以及用量明細 API 回吐該欄位的內容形狀。這是**管理端可見**的資料層變更,但不是 schema 變更(欄位型別、欄位名皆不動)。
- 綜合:功能為既有能力的儲存介質置換 + 一次性資料遷移,**向下相容** → 落 **v2.2.1**(user 指定)。
- **格式偏離註記**:`01-propose-format.md` 寫「patch 不獨立 propose」。本 repo 既有 `propose-v1.6.1` / `v1.9.1` / `v1.9.2` / `v2.0.1~3` / `v2.1.1` / `v2.1.2` 慣例已確立(`.Z` 用於 `.Y` 之下的小功能增修,非純 bug fix),本檔沿用該慣例。

## ⚠️ 規範層級註記

已檢查 `docs/Design-Base/*`,**本版有一處觸及地板,須先改規範再開工**:

- 🔴 **新第三方服務 AWS S3 在 Design-Base 無對應規範檔(✅ user 定案 2026-07-29:開工前先補)**。`90-third-party-service/` 現有 `03-smtp` / `04-sso-azure-ad` / `05-payment` / `06-monitoring` / `07-lint-bot` / `08-df-sso` / `50-openrouter`,**沒有物件儲存**。依 [`01-propose/07-rule-evolution.md`](../../Design-Base/01-propose/07-rule-evolution.md)「要改規則先改 Design-Base」,本版**第一個 task** 應為新增 `90-third-party-service/09-object-storage.md`(S3 client 落點 / 命名 / 錯誤轉換 / 物件 key 規則 / presigned URL TTL / 加密與存取權 / 禁公開讀),並同步 `Design-Base/README.md` 與 `AGENTS.md § Just-in-time Loading` 兩處對照表。
- 🟡 **覆寫 v2.1.2 的既有決策(已拍板)**:目前 `files`(PDF 等)**刻意只記檔名、不記 `file_data`**,原因註明為「法務考量」(見 [`proxy.py:196`](../../../backend/app/services/proxy.py#L196)、`_snapshot_message`)。本版把檔案實體存進 S3 → **推翻該決策**。**✅ user 定案(2026-07-29):檔案要存**;此變更須於 commit / task doc 明確註明「推翻 v2.1.2 §D.4 法務考量決策」,並回頭在 `docs/Tasks/v2.1/propose-v2.1.2.md` 的變更紀錄補一行指向本版。
- 其餘相依錨點(皆落在既有規範內,無需改地板):
  - S3 client 落點 / 錯誤轉換:[`90-third-party-service/00-overview.md`](../../Design-Base/90-third-party-service/00-overview.md)(`app/clients/s3/`、`S3Client`、`S3Error`)+ [`01-client-design.md`](../../Design-Base/90-third-party-service/01-client-design.md) + [`03-backend/06-clients.md`](../../Design-Base/03-backend/06-clients.md)。
  - AWS 憑證:[`00-overview/02-secrets.md`](../../Design-Base/00-overview/02-secrets.md) + [`03-env-layers.md`](../../Design-Base/00-overview/03-env-layers.md) + [`06-Coolify-CD/04-env-and-secrets.md`](../../Design-Base/06-Coolify-CD/04-env-and-secrets.md)(**僅** env 注入,禁 commit)。
  - 上傳為阻塞 I/O + 不可拖垮 event loop:[`03-backend/03-async-and-tx.md`](../../Design-Base/03-backend/03-async-and-tx.md) + [`08-performance.md`](../../Design-Base/03-backend/08-performance.md)。
  - 歷史遷移批次:[`04-databases/08-alembic.md`](../../Design-Base/04-databases/08-alembic.md)(遷移**不**走 alembic 的理由見 §D.6)+ [`09-indexes-and-perf.md`](../../Design-Base/04-databases/09-indexes-and-perf.md)。
  - 代理輸入白名單邊界(確認本版未擴大):[`90-third-party-service/50-openrouter.md`](../../Design-Base/90-third-party-service/50-openrouter.md) § 6。
  - 前端明細頁渲染:[`02-frontend/00-overview.md`](../../Design-Base/02-frontend/00-overview.md) + [`91-project-ui-ux.md`](../../Design-Base/02-frontend/91-project-ui-ux.md)。
  - 對外文件同步:`docs/INTEGRATION.md` + 前端 `user-guide` 頁(SDK 呼叫鏈路語意有變 → 必須連帶更新)。

---

## 版本目標

把「使用者上傳的圖片 / 檔案」從 **Postgres JSONB 裡的 base64 字串**搬到 **S3 物件儲存**,DB 只留路徑:

1. **止血**:base64 進 JSONB 讓單筆 `usage_logs` 可達數 MB,直接推高 DB 體積、備份 / 還原時間、明細查詢與 JSONB 序列化成本,且是 v2.2.0 那筆「NUL 導致整筆記帳靜默寫入失敗」的同源風險面(大而髒的 JSONB)。改存路徑後單筆快照回到 KB 級。
2. **解鎖**:附件有了正規儲存位置,`files` 才可能從「只留檔名、看不到內容」升級為「留得住、點得開」,後續縮圖 / 重跑帶圖 / 對話記憶多輪附件都有地基。

## In Scope

### 工作面一 · 寫入端改道(新請求)

- **物件儲存能力**(§B.1):新增 S3 client(`app/clients/s3/`),提供上傳 / 產生短期讀取 URL / 刪除;bucket 固定 **`df-openrouter-dispatch-prod`**,region 依 env。物件一律 **private**(禁公開讀),對外一律走 presigned URL。
- **代理請求落地**(§B.2):`run_chat` / `run_chat_stream` 收到請求後,把附件先落 S3,再組下游 payload 與用量快照:
  - **單輪模式** `images[]`:data URI → 上傳 → 快照存路徑。
  - **messages 直傳模式** `image_url.url` 為 data URI → 同上,逐 part 改寫。
  - **`files[]`**(PDF 等):實體上傳 S3,快照由「只有 `filename`」升級為「`filename` + 路徑」(**✅ 已定案,§D.3**)。此為**新功能**,只對新請求生效——既有歷史紀錄本來就沒留檔案內容,**無從回填、也不回填**(user 接受)。
  - 已是 `http(s)://` 遠端 URL 的輸入是否也代抓落 S3:§D.2。
- **下游 payload 完全不動**(§B.2 / §D.4):送 OpenRouter / internal 的 `image_url.url` / `file_data` **維持現行 base64 或原始 URL,一個 byte 都不改**(**✅ 已定案,§D.4**)。本版只改「寫進 DB 的 log 快照」這一層。
- **presigned URL 功能保留**(§B.1 / §B.4 / §D.9):S3 client 仍須提供簽發能力,用途收斂為**管理端明細頁顯示圖片 / 開啟檔案**(不用於下游模型)。
- **失敗語意 = best-effort**(§B.2 / §D.5,**✅ 已定案**):S3 上傳失敗 → **不擋請求**(代理照常呼叫下游、照常回應、`usage_logs` 照常寫入)、**不降級回 base64**、**只記結構化 log**;該附件在快照中記為帶 metadata 的失敗標記(`upload_failed` + mime / bytes / sha256)。隨附硬規則:**`file_data` 的 base64 任何情況下都不得寫入 `usage_logs.request_content`**。
- **總開關 env**(§C):`S3_STORAGE_ENABLED`,預設 `false`(對齊 `AI_EVAL_ENABLED` / `MODEL_SYNC_SCHEDULE_ENABLED` 慣例:新外部相依預設關,由環境顯式開)。關閉時行為與現況完全一致。

### 工作面二 · 歷史 base64 遷移(**兩階段**,✅ §D.6 已定案)

user 定案:**base64 先不動,確認搬遷成功後才棄用**。因此遷移拆成兩支獨立可跑、可重跑的階段,中間卡一道人工驗收:

- **Phase 1 · 只上傳,不動 DB**(§B.3):掃 `usage_logs.request_content`,找出兩種形狀裡所有 `data:*;base64,*` 圖片(單輪 `images[]` 與 messages 模式的 `image_url.url`),**上傳 S3 後即結束** —— DB 一個 byte 都不改。跑完 base64 仍原封不動在庫裡,系統行為完全等同現況。
- **驗證關卡**(§B.3):比對「應上傳物件數 vs S3 實際物件數」、抽樣 ≥ 10 筆做 **byte-for-byte** 比對(S3 物件 = 原 base64 decode 結果)、抽樣以 presigned URL 實際開得起來。**通過才准跑 Phase 2**。
- **Phase 2 · 改寫 JSONB**(§B.3):重掃一次,對每個 data URI 重算出同一把 key(key 為 **deterministic**:`usage_log_uid + 位置 + 內容 sha256`),先 `head_object` 確認物件確實存在,**才**把該值改寫成路徑;物件不存在 → 跳過該列並記入待處理清單,絕不寫出指向空物件的路徑。
- **不需要新欄位 / 新表 / migration**:因為 key 可由內容重算,Phase 1 與 Phase 2 之間**不必存 mapping**,自然達成「先搬、後棄用」而不必雙寫或加欄位(這點很重要——本專案 [`AGENTS.md § 毀滅性操作禁止`](../../../AGENTS.md) 禁 `DROP COLUMN`,一旦加了暫存欄位就沒有乾淨的退場路徑)。
- **可重跑 / 可分批 / 可續跑**(§B.3):兩階段皆以 `pid` 游標分批、Phase 2 每批獨立 transaction;中斷後重跑只處理尚未完成的列,重複執行結果一致(冪等)。
- **只動附件、不動其他**:`text` / `messages` 文字 / `tools` / 生成參數 / 記帳欄位一律不改;`updated_at` 不隨遷移跳動(§D.7)。
- **Phase 2 前仍先備份**(§B.3):Phase 2 是就地覆寫,執行前必須有可還原的 `pg_dump` 並驗證備份可還原。此時 S3 已有經驗證的副本,雙保險。
- **完成判準**:Phase 2 後全庫掃描應為「零筆 `request_content` 仍含 `data:` base64 圖片」;抽樣列於明細頁能正常顯示。

### 工作面三 · 讀取端與周邊

- **用量明細**(§B.4 / §E):明細頁 `usage-logs/[uid]` 圖片改以後端簽發的短期 URL 顯示;既有「base64 → Blob URL」渲染路徑退場,但**保留對舊形狀的容錯**(遷移期間新舊並存,且不能因為一列沒搬完就整頁壞掉)。
- **快照正規化層**(§B.4):`app/services/request_snapshot.py` 擴充為認得第三種附件形態(路徑),AI 評估 / 重跑鏈路(`ai_model_eval*`)取用圖片時一併對齊。
- **設定 / 部署**(§C):新增 AWS 相關 env,`.env.example` 補齊、dev / test / prod 三層分工說明、Coolify 注入清單更新;`docker-compose*.yml` 兩份都要讓 backend(以及會跑遷移的容器)拿得到新 env。
- **文件同步**:`docs/INTEGRATION.md` + 前端 `user-guide` 頁補「附件儲存位置與保存政策」;`.env.example` 註解齊備。

## Out of Scope

- **不改 chat API 對外契約**:不要求呼叫端改送 URL、不新增必填欄位、不動 response 形狀。
- **不做 CDN / 公開 bucket / 自訂網域**:一律 private + presigned。
- **不做圖片處理**:不轉檔、不壓縮、不產縮圖、不做 EXIF 清洗。
- **不動記帳與配額邏輯**:`usage_logs` 其他欄位、計費、速率限制一律不碰。
- **不動下游 payload**:送 OpenRouter / internal 的請求內容維持現行(§D.4);`_rewrite_request` 不應有 diff。
- **不改 AI 評估 / 重跑的判分邏輯**:只讓它取得到圖片,不改 prompt 與評分。
- **不搬回應端產出物**:目前回應只存文字,無附件可搬。
- **不回填歷史檔案**:既有 `files` 紀錄只有檔名、系統從未留過內容,**無從回填**;檔案儲存自本版起對新請求生效(✅ user 接受,§D.3)。
- **不做 S3 生命週期 / 自動刪除 / 保存期限清理**(§D.8 若拍板要,才落本版)。
- **不做多 provider 物件儲存抽象**(不預留 MinIO / GCS 切換層;有需要再說)。

## 對外承諾

- `POST /api/v1/model/chat` 與 `POST /api/v1/model/openrouter/chat`(deprecated alias)的 **request / response schema 完全不變**;既有 SDK 呼叫端**零改動**即可繼續運作,含繼續送 base64 data URI。
- **送給模型的內容與現行完全相同**(下游 payload 不動,§D.4)→ 模型回應品質不受本版影響,無須擔心「換了圖片傳法導致輸出劣化」。
- 用量明細頁的圖片**在遷移前後皆可正常顯示**,包含全部歷史紀錄。
- 用量明細 API 回吐的 `request_content` 內,圖片元素語意由「base64 data URI 或遠端 URL」變更為「可直接顯示的短期 URL」;**這是管理端可見的行為變更**,須寫進 CHANGELOG 與 `INTEGRATION.md`。
- 上傳的檔案 / 圖片存放於公司自有 AWS S3(`df-openrouter-dispatch-prod`,private),不對外公開;取用一律經後端簽發的短期連結。
- **檔案(PDF 等)自本版起才留存內容**:本版之前的歷史紀錄只有檔名、沒有檔案內容,不會、也無法補上。
- **代理服務可用性不受 S3 影響**:S3 故障 / 逾時不會讓任何代理請求失敗(§D.5 best-effort);最壞情況只是該筆紀錄的附件沒留存,對外行為完全正常。

## 資料流

### 新請求(工作面一)

```
SDK 呼叫端
  → POST /api/v1/model/chat  { model, text, images:[data URI...], files:[{filename,file_data}] }
  → sdk_auth 解析 caller(部門 / 專案 / 使用者)
  → [新] 附件落地:每個 data URI → decode → 上傳 S3
        key: <prefix>/chat/<YYYY>/<MM>/<DD>/<request_uid>/<idx>-<sha256[:16]>.<ext>
        → 得到 object key 清單(與原順序一一對應)
        → 失敗者不中斷:記 upload_failed 標記 + metadata、寫 log,繼續往下(§D.5)
  → _rewrite_request(...)   下游 payload【完全不動,照現行送 base64 / 原始 URL】
  → OpenRouter / internal /chat/completions
  → _build_request_log(...) 快照【本版唯一改動點】:寫「物件路徑」;上傳失敗者寫 upload_failed 標記
  → usage_logs INSERT(JSONB 由 MB 級降為 KB 級)
```

### 歷史遷移(工作面二,兩階段)

```
[Phase 1] 只上傳,DB 完全不動
  → SELECT pid, uid, request_content FROM usage_logs
      WHERE request_content::text LIKE '%data:%base64,%'   （游標分批,每批 N 列）
  → 逐列走訪 JSONB:單輪 images[] + messages[].content[].image_url.url
  → 對每個 data URI:decode → key = <prefix>/legacy/<usage_log_uid>/<idx>-<sha256[:16]>.<ext>
                     → head_object 已存在則跳過,否則 put_object
  → 報表:應上傳 N 個 / 實際上傳 M 個 / 已存在 K 個 / 失敗清單
  ✋ DB 未改一個 byte;此刻中止 = 完全沒有副作用

──────── 人工驗收關卡 ────────
  · 物件數比對(應上傳 = S3 實際)
  · 抽樣 ≥ 10 筆 byte-for-byte 比對(涵蓋單輪 / messages、單圖 / 多圖)
  · 抽樣 presigned URL 實際開得起來
  · pg_dump 備份完成且驗證可還原
  ✅ 全過才准跑 Phase 2

[Phase 2] 改寫 JSONB(base64 於此刻才退場)
  → 重掃同一 WHERE 條件(游標分批,每批一個 transaction)
  → 對每個 data URI:重算出同一把 key（deterministic,不需 mapping）
                     → head_object 確認存在 → 才以路徑取代原值
                     → 物件不存在 → 跳過該列、記入待處理清單(絕不寫出空指標)
  → UPDATE usage_logs SET request_content = <改寫後> WHERE pid = ...（不動 updated_at）
  → 收尾驗證:同一 WHERE 條件應回 0 列
```

### 讀取(工作面三)

```
管理端明細頁 GET /api/v1/usage-logs/{uid}
  → 後端讀 usage_logs.request_content
  → [新] 走訪附件路徑 → 為每個 key 簽 presigned GET URL(TTL 見 §C)
  → 回吐給前端 → <img src=...> 直接顯示(不再走 base64 → Blob 轉換)
  → 舊形狀(仍是 data URI)→ 原樣回吐,前端既有渲染路徑保底
```

## 後端(§B)

### B.1 S3 client(`app/clients/s3/`)

- 目錄結構依 `90-third-party-service/00-overview.md`:`client.py`(`S3Client`)/ `errors.py`(`S3Error` + `S3UploadError` / `S3NotFoundError`)/ `README.md`(quirk 紀錄)。
- 能力:`put_object(key, body, content_type)`、`presign_get(key, ttl)`、`delete_object(key)`、`head_object(key)`。
- **短 timeout + 低重試上限**(§D.5):上傳失敗不擋請求,但會拖延遲 → connect / read timeout 取秒級、重試 ≤ 1 次,逾時即視為失敗並記 log。
- 依賴:`boto3`(或 `aioboto3`)—— **是否引入新套件、選哪一支,見 §D.1**;boto3 為同步 SDK,呼叫必 `asyncio.to_thread` 包裹(對齊 `03-async-and-tx.md`,禁阻塞 event loop)。
- 錯誤一律轉 `S3Error` 子類,**禁**讓 `botocore.exceptions.*` 流到 service / api 層。
- 設定走 `Settings`(`03-backend/04-config.md`);production 缺 bucket / 憑證且 `S3_STORAGE_ENABLED=true` → **啟動 fail-fast**。

### B.2 代理寫入端(`app/services/proxy.py`)

- 新增附件落地層(建議獨立模組 `app/services/attachment.py`,不把 S3 細節灌進 proxy):輸入 `images` / `files` / `messages`,**只輸出「快照用路徑」**(下游素材不經手 —— 下游吃的仍是原始輸入)。
- **`_rewrite_request` 本次不應有任何 diff**;只有 `_build_request_log` 改吃路徑。這是本版最好用的 review 判準:PR 若動到 `_rewrite_request`,就是走偏了。
- data URI 解析:`^data:([^;]+);base64,(.*)$` → mime → 副檔名;**非法 / 解不開的 data URI** 依 §D.5 語意處理。
- 串流路徑(`run_chat_stream`)與非串流路徑共用同一落地層,**不可只改一條**。
- 上傳失敗**不中斷主流程**(§D.5):逐附件獨立處理,成功者記路徑、失敗者記 `upload_failed` 標記 + metadata,兩者可並存於同一則快照;下游呼叫與回應完全不受影響。
- 上傳與下游呼叫的先後:附件落地在組 payload 之前完成(快照要用其結果),但**不因失敗而中止**;S3 慢 / 逾時即放棄該附件,不拖住請求(§B.1 短 timeout)。
- **兩層值嚴格分離**(§D.4 / §D.5):`_rewrite_request` 拿的是**原始輸入值**(base64 / 原始 URL,**完全不動**),`_build_request_log` 拿的是「快照用值」(**永遠只有 S3 路徑**)。`_rewrite_request` 本次**不應有任何 diff** —— 若 PR 動到它,就是走偏了。
- **硬規則**:`file_data` 的 base64 內容**任何情況下**都不得進入 `usage_logs.request_content`(v2.1.2 起的法務理由 + 本版的資料量理由,雙重約束)。此點需有專門測試守住。

### B.3 歷史遷移批次(兩階段)

- 落點建議 `backend/scripts/migrate_base64_to_s3.py`,以 **`--phase upload|rewrite`** 切換兩階段(另有 `--batch-size` / `--dry-run` / `--limit`);**不**走 alembic(理由見 §D.6)。
- **key 必須 deterministic**:`<prefix>/legacy/<usage_log_uid>/<idx>-<sha256(bytes)[:16]>.<ext>`。這是兩階段解耦的關鍵——Phase 2 靠重算取得同一把 key,不需要任何 mapping 表 / 暫存欄位 / 中繼檔。
- 冪等:Phase 1 上傳前 `head_object` 跳過已存在;Phase 2 改寫前判斷該值是否已是路徑。`--dry-run` 只報統計不寫入、不上傳。
- 併發:預設單執行緒循序(安全優先);Phase 1 上傳可小幅併發,Phase 2 的 DB 寫入維持每批一個 transaction。
- 失敗列不擋整批:記錄 `pid` 到失敗清單、繼續下一列,結束時彙總報表。
- Phase 2 的 `UPDATE` 需**顯式保留 `updated_at`**(§D.7);若 ORM 層有 `onupdate` 自動覆寫,改走 raw SQL(對齊 [`04-databases/04-sql-safety.md`](../../Design-Base/04-databases/04-sql-safety.md),禁字串拼接)。

### B.4 讀取端

- `app/services/request_snapshot.py`:新增「附件值 → (是 data URI / 是 S3 路徑 / 是遠端 URL)」判別,讓正規化層認得第三種形態。`replay_messages` 目前單輪不重放圖片、messages 模式剔除 file part,**本版不擴大重跑行為**,只確保新形狀不會被誤判為內容。
- 用量明細 API:回吐前把路徑換成 presigned URL(§D.9 決定是「回吐時直接換」還是「另開 `GET /attachments/{...}` 302 導轉」)。
- AI 評估 / 重跑:`replay_messages` 目前單輪模式不重放圖片、messages 模式剔除 file part —— **本版不擴大重跑行為**,只確保不因形狀改變而壞掉。

## 前端(§E)

- `usage-logs/[uid]/page.tsx`:`ImageItem` 增加「值已是 http(s) URL → 直接 `src`」分支;既有 data URI → Blob 的路徑保留(遷移期 / 開關關閉時的舊列)。
- 標示由「(base64) / (URL)」改為能反映儲存位置的標示(§D.9 定案後決定文案)。
- 需處理 **presigned URL 過期**(停留超過 TTL 後圖片破圖)→ 破圖時顯示可重新載入的提示,而非空白。
- 需處理 **`upload_failed` 標記**(§D.5):顯示「圖片 #N:上傳失敗,內容未留存」+ 可得的 metadata(大小 / 型別),而非破圖或整段空白。
- `user-guide` 頁附件說明段同步更新。

## 設定(環境變數)(§C)

| 變數 | 層級 | 預設 | 說明 |
| --- | --- | --- | --- |
| `S3_STORAGE_ENABLED` | BOTH | `false` | 總開關;`false` → 完全維持現行 base64 行為(零風險回退) |
| `AWS_ACCESS_KEY_ID` | **COOLIFY / 機密** | 空 | IAM 存取金鑰;**禁 commit 實值** |
| `AWS_SECRET_ACCESS_KEY` | **COOLIFY / 機密** | 空 | IAM 密鑰;**禁 commit 實值**、禁入 log |
| `AWS_REGION` | BOTH | `ap-northeast-1` | bucket 所在 region |
| `S3_BUCKET` | BOTH | `df-openrouter-dispatch-prod` | 物件 bucket(user 指定) |
| `S3_KEY_PREFIX` | BOTH | 依環境 | key 前綴,用於區隔 dev / test / prod(§D.8:是否共用同一 bucket) |
| `S3_PRESIGN_TTL_SECONDS` | BOTH | `900` | presigned URL 有效期(15 分鐘)。**僅用於管理端明細頁顯示**,不用於下游模型(§D.4)。SigV4 + 長期 IAM 憑證下上限為 7 天 |

- `.env.example` 需新增上述鍵(機密留空 + 註解標 `[COOLIFY]`),並更新檔尾「Coolify 注入機密」清單加入 `AWS_SECRET_ACCESS_KEY`。
- prod compose 無 `env_file`,新 env 須明列於 backend 服務(以及跑遷移的容器)的 `environment:`;dev 走 `env_file: .env` 自動可見。

> ⚠️ **本次 user 於對話中直接貼出了一組 AWS access key / secret**。該組憑證只能落在**未進版控的 `.env`** 與 Coolify Secrets;本檔與任何 commit 內容一律只寫鍵名。既然明文已離開受控環境,建議**上線前先 rotate 一次**,並把該 IAM user 的權限收斂到「僅 `df-openrouter-dispatch-prod` 這一個 bucket 的 `PutObject` / `GetObject` / `DeleteObject` / `ListBucket`」。

## D. 設計取捨(D.3 / D.4 / D.5 / D.6 已拍板,餘項為實作預設)

### D.1 S3 SDK 選型 — 建議「`boto3` + `asyncio.to_thread`」

- `boto3` 為 AWS 官方、最穩、社群資源最多,但**同步**;本專案全 async,故所有呼叫必 `asyncio.to_thread` 包裹。
- 替代案 A:`aioboto3`(原生 async,但為第三方包裝、版本追 boto3 有延遲)。
- 替代案 B:不引 SDK,直接以既有 `httpx` 自簽 AWS SigV4(零新依賴,但簽章自幹易錯、不划算)。
- **建議 `boto3` + `to_thread`**;需同步更新 `00-overview/01-versions.md` 的版本鎖清單。

### D.2 遠端 URL 輸入是否也代抓落 S3 — 建議「不代抓,原樣保留」

- 呼叫端若已送 `https://...` 圖片 URL,代抓會引入 SSRF 面、外部站台可用性風險與額外流量成本。
- 建議**原樣保留**(快照就記那個 URL);缺點是該圖的長期可讀性不由我方掌握。
- 替代案:一律代抓(快照完整、可長期回溯,但需 SSRF 防護 + 大小 / 型別限制)。

### D.3 `files`(PDF 等)是否存實體 — ✅ **user 定案(2026-07-29):存**

- 現行**刻意不存 `file_data`**,理由註明「避免將使用者上傳的檔案內容留存於系統(法務考量)」。本版**推翻**該決策。
- **✅ user 定案:檔案要存,且視為「新功能」** —— 只對新請求生效;既有歷史紀錄本來就只有檔名、沒有內容,**不存在也沒關係、不回填**(user 明示接受)。
- 隨之而來的責任:公司開始長期持有使用者上傳的原始文件 → 保存期限 / 存取控管 / 刪除請求成為新的維運面。本版先不設 lifecycle(§D.8),但**建議下一版就補保存政策**。
- 落實要求:此決策變更須在 commit / task doc 明寫「推翻 v2.1.2 §D.4」,並回頭在 `propose-v2.1.2.md` 變更紀錄補一行指向本版(避免日後有人照舊註解又把 `file_data` 拿掉)。

### D.4 送下游模型的形式 — ✅ **user 定案(2026-07-29):下游 payload 完全不動**

- **✅ 定案(2026-07-29,推翻本檔稍早的 presigned URL 方案)**:user 明示 —— **「全部都不管下游給使用者的資訊,因為我改的只是平台後端 log 儲存路徑而已」**。
- 因此:`_rewrite_request` 組出的下游 payload **一個 byte 都不改**,`images` / `file_data` 照現行送 base64 或原始 URL 給 OpenRouter / internal。本版的變更**只發生在 `_build_request_log`(寫進 DB 的快照)這一層**。
- 這讓本版的風險面大幅收斂,直接消掉三項原本要處理的東西:
  - OpenRouter 對「帶長 query 簽章 URL」的相容性未知 → **不再是問題**(根本不送)。
  - internal 地端 provider 連不到外網 → **不再是問題**。
  - presign 失敗要不要 fallback、fallback 值會不會滲進快照 → **不再是問題**(下游根本不吃 S3 值)。
- **presigned URL 的用途收斂為單一場景**:管理端用量明細頁顯示圖片(§D.9)。
- 保留給後續版本:若日後真要靠 presigned URL 縮小下游 payload,再獨立評估(需先實測 OpenRouter 相容性與 internal 的連外能力)。**本版不做**。
- presigned URL 可行性(user 提問,結論留檔):S3 原生支援。`boto3.generate_presigned_url('get_object', ...)` 是**本地以金鑰計算 SigV4 簽章**,不呼叫 AWS API、不計費、毫秒級;bucket 維持 **Block Public Access 全開**照樣可用(presigned 是「帶簽章的授權請求」,不是公開讀取)。TTL 自訂,長期 IAM 憑證下 SigV4 上限 7 天(本版取 15 分鐘,§C)。注意其權限**繼承簽發者的 IAM 權限** → 那把 key 必須收斂到單一 bucket(見 §風險)。

### D.5 S3 上傳失敗的語意 — ✅ **user 定案(2026-07-29,修訂):不擋請求、不降級、只記 log**

- **✅ 定案(user 原話)**:「**如果上傳失敗就失敗,幫我寫入 log 即可,不要降級成 base64,也不要擋死。**」
- 即 **best-effort 語意**,三條同時成立:
  1. **不擋死** —— 代理請求照常呼叫下游、照常回應給 SDK 呼叫端,`usage_logs` 照常寫入。附件上傳失敗**不影響任何對外行為**。
  2. **不降級** —— 該附件**絕不**改寫 base64 進 `usage_logs.request_content`。
  3. **記 log** —— 失敗落結構化 log(含 usage_log uid / 附件 index / mime / byte 大小 / sha256 / 錯誤原因),供事後追查與補救。
- 這才與 §D.4「本版只改 log 儲存路徑」自洽:**記帳層不該有權力擋掉一個本來會成功的請求**。稍早版本曾定為「擋下回 5xx」,已由 user 於同日修訂推翻。
- **快照該怎麼記**(§B.2):保留該附件的**位置與 metadata**、只是沒有內容 —— 建議記為 `{"type": "image_url", "upload_failed": true, "mime": "...", "bytes": N, "sha256": "..."}`。理由:
  - 直接略過會讓「這則請求原本有幾張圖」的資訊消失,明細頁與統計都會失真。
  - 留 `sha256` + `bytes` 讓日後真要補救時有對照依據。
  - 明細頁據此顯示「圖片 #2:上傳失敗,內容未留存」(§E),而不是破圖或空白。
- **由此衍生的硬規則(§B.2 必須落實)**:

  > **`file_data` 的 base64 內容,任何情況下都不得寫入 `usage_logs.request_content`。**

  這條在 v2.1.2 就成立(當時理由是法務),本版理由再加一條(資料量:user 明示「file 寫進 DB 會炸」),且**不因 S3 失敗而例外** —— 失敗就記標記,不是改寫 base64 進 DB。
- 邊界釐清:**下游 payload 帶 base64 完全不在此限**(那是既有行為、不落 DB,且本版根本不動,見 §D.4)。這條硬規則只約束**寫進 DB** 的那一層。
- **延遲保護**(§B.1):既然失敗不擋請求,S3 就更不該拖慢請求 —— client 須設**短 timeout + 低重試上限**,逾時即視為失敗、記 log、繼續跑。
- 不影響 `S3_STORAGE_ENABLED=false` 的完全回退能力:開關關閉時走的是「完全等同 v2.2.0」的既有路徑(圖片 base64 入 JSONB、檔案只記檔名)。

### D.6 遷移執行方式與原資料保留 — ✅ **user 定案(2026-07-29):兩階段,base64 先不動**

- **不走 alembic**:migration 內做大量外部網路 I/O 不可控、失敗難回滾、CI 的 `alembic upgrade head` round-trip 會被外部服務綁架。改為獨立可重跑 script(§B.3)。
- **✅ 定案:兩階段 + 中間人工驗收**(user 原話:「base64 先暫時不動,等確定移轉成功後再棄用」):
  - **Phase 1** 只上傳 S3,DB 完全不動 → 此時中止零副作用,系統行為等同現況。
  - **驗收關卡**:物件數比對 + byte-for-byte 抽樣 + presigned URL 實開 + `pg_dump` 備份可還原。
  - **Phase 2** 才改寫 JSONB;改寫前逐一 `head_object` 確認物件存在,base64 於此刻退場。
- **關鍵設計:key 為 deterministic(內容 sha256 參與)**,所以兩階段之間**不需要任何 mapping**。這讓我們避開了「加暫存欄位保留 base64」的方案 —— 那需要一支 migration 加欄位,而本專案 [`AGENTS.md § 毀滅性操作禁止`](../../../AGENTS.md) **禁 `DROP COLUMN`**,加了就沒有乾淨的退場路徑(只能 `SET NULL` 留著空欄,DB 體積也不會降)。
- 被否決的替代案:一次性就地覆寫(較快,但沒有「確認搬遷成功」的觀察點,與 user 要求相左);新增 `request_content_legacy` 欄位雙寫(見上,退場路徑不乾淨)。

### D.7 遷移是否更新 `updated_at` — 建議「不更新」

- 遷移是系統內部搬家,不是業務資料異動;更新 `updated_at` 會污染「最後異動時間」語意與依此排序 / 篩選的畫面。
- 建議 UPDATE 時顯式保留原 `updated_at`(需確認 ORM / DB 層沒有 `onupdate` 自動覆寫;有的話走 raw SQL)。

### D.8 bucket 分層與保存期限 — 建議「單一 bucket + 環境前綴,暫不設自動刪除」

- user 只指定一個 bucket `df-openrouter-dispatch-prod`(名字帶 `prod`)。dev / test 若共用,必須靠 `S3_KEY_PREFIX` 隔離(例 `dev/` / `test/` / `prod/`),避免測試物件污染正式資料。
- 替代案:另開 `-dev` / `-test` bucket(乾淨,但要多開 bucket 與權限)。
- **保存期限**:建議本版**不設** lifecycle 自動刪除(先把東西存住、觀察量體);若 §D.3 採「存檔案實體」,則建議下一版就補保存政策。

### D.9 明細頁取圖方式 — 建議「API 回吐時直接換成 presigned URL」

- 選項 A(建議):明細 API 組回應時就把 key 換成 presigned URL,前端拿到即可顯示。最簡單,但 URL 會隨回應外流(TTL 短、bucket private,風險可控)。
- 選項 B:回吐 key,另開 `GET /api/v1/usage-logs/{uid}/attachments/{idx}` 端點做 302 導轉。權限每次現查、URL 不外流,但多一支端點與一輪往返。
- 兩案都要處理「頁面停留超過 TTL 後圖片失效」的前端表現。

## 風險與相依

- **🔴 憑證外洩面**:AWS key 一旦進 git 或 log 即為公司級事故(對齊 `00-overview/02-secrets.md`,亦正是本平台的立案痛點)。本版必做:`.env` 已 gitignore 驗證、gitleaks 掃過、log 過濾涵蓋 `AWS_*`、IAM 權限最小化到單一 bucket、上線前 rotate(本次金鑰已在對話中明文出現)。
- **🟡 遷移的不可逆點被推遲到 Phase 2**(§D.6 定案後風險已大幅下降):Phase 1 純上傳、零副作用,可放心先跑;真正的不可逆覆寫只在 Phase 2,且此時 S3 已有經 byte-for-byte 驗證的副本 + `pg_dump` 備份 + 逐物件 `head_object` 檢查三層保護。**殘餘風險**:驗收關卡若被跳過(例如「反正 Phase 1 跑完了直接跑 Phase 2」),三層保護等於沒有 → 兩階段須拆成**兩個獨立 task**、Phase 2 的 task 明列前置驗收證據。
- **遷移期新舊形狀並存**:讀取端(明細頁 / `request_snapshot` / AI 評估 / 重跑)在遷移完成前會同時遇到 data URI 與路徑兩種值,**任一讀取端漏改就會靜默壞掉**(v2.1.2 的 messages 形狀就踩過這個坑,見 `request_snapshot.py` 檔頭)。所有讀取端必須列清單逐一驗證。
- **兩條 chat 路徑**:非串流 `run_chat` 與串流 `run_chat_stream` 必須同步改;漏一條 → 串流請求仍寫 base64,遷移完又長回來。
- ~~**下游相容性**~~:**已隨 §D.4 定案消失** —— 下游 payload 不動,OpenRouter / internal 收到的東西與 v2.2.0 完全相同,無相容性風險、無須實測。
- **延遲與成本**:每個請求多一次 S3 PUT(數十~數百 ms,視圖片大小);S3 儲存 + 請求 + 流量費用需估;presign 本身無網路成本。因失敗不擋請求(§D.5),**timeout 必須設短**,否則 S3 慢速會直接反映成代理延遲。
- **附件靜默遺失**(§D.5 best-effort 的代價):S3 失敗時請求照樣成功,使用者不會察覺,只有 log 知道附件沒存到。**必須**有可觀測性 —— 失敗落結構化 log 且可在 Seq 上查詢 / 告警,否則會長期無聲遺失附件而沒人發現。
- **event loop 阻塞**:boto3 同步呼叫若忘記 `to_thread`,單 worker 下會直接卡住所有請求(對齊 `03-backend/08-performance.md`)。
- **大附件的記憶體**:decode base64 → bytes 在記憶體中,巨量圖片 / 大 PDF 需設單檔與總量上限(目前 schema 無上限)。
- **法務**(§D.3):存檔案實體改變公司對使用者上傳內容的持有立場,需 user 明確承擔。
- **presigned URL 的權限繼承**:簽出去的 URL 帶的是簽發者的權限。IAM 若給了 `s3:*` 或跨 bucket 權限,等於把那個範圍的授權暫時外流。**必須**把該 IAM user 收斂到單一 bucket 的 `PutObject` / `GetObject` / `DeleteObject` / `ListBucket`。
- **TTL 與 UX 的取捨**:明細頁停留超過 15 分鐘後圖片會破;前端需有可重新載入的提示,而非空白(§E)。
- **檔案保存責任(§D.3 已拍板)**:自本版起長期持有使用者上傳的原始文件,保存期限 / 刪除請求 / 存取稽核成為新的維運面。本版不設 lifecycle(§D.8),建議下版補保存政策。
- **可回退**:`S3_STORAGE_ENABLED=false` 可讓寫入端瞬間回到現況;Phase 1 跑完亦可完全回退(DB 未動);**只有 Phase 2 之後的歷史列**需靠備份還原 —— 這是本版唯一不可逆的部分。

## 驗收標準

### 工作面一(寫入端)

- `S3_STORAGE_ENABLED=true`:送含 data URI 圖片的 chat 請求(單輪 `images` 與 messages 兩種模式)→ S3 對應 key 出現物件、內容 byte-for-byte 等於原圖;`usage_logs.request_content` 內**不含任何 `data:` base64**,只有路徑;模型回應正常。
- 串流端點(`run_chat_stream`)行為同上(不可只有非串流生效)。
- `files` 依 §D.3 拍板結果驗收:採 (a) → S3 有檔案且快照含路徑 + 檔名;採 (b) → 維持只記檔名。
- `S3_STORAGE_ENABLED=false`:行為與 v2.2.0 完全一致(快照仍為 base64,不呼叫 S3)。
- **S3 上傳失敗(以 mock 注入)**:代理請求**照常成功回應**、下游照常被呼叫、`usage_logs` 照常寫入;該附件在快照中為 `upload_failed` 標記(含 mime / bytes / sha256),**不含 base64**;結構化 log 有對應失敗紀錄。**不得**寫出「快照指向不存在物件」的路徑。
- **S3 逾時 / 完全不可用**:代理服務可用性不受影響(關掉 S3 endpoint 實測),請求延遲增幅在 client timeout 上限內。
- **回歸測試守住硬規則**:對含 `files` 的請求(成功 / S3 失敗 / internal provider 三種路徑),斷言 `usage_logs.request_content` **完全不含 `file_data` 或任何 base64 字串**。
- **下游 payload 零變更驗證**:以 `respx` 攔截下游請求,斷言送出的 body 與 v2.2.0 **逐欄相同**(images 仍是 base64 / 原始 URL、`file_data` 照舊)。
- 單元 / 整合測試:data URI 解析(含畸形值)、key 生成規則、開關短路、`to_thread` 包裹(無阻塞)、兩種內容模式的快照改寫正確、上傳失敗 best-effort(不擋、不降級、有 log、有標記)、部分成功部分失敗可並存於同一則快照;S3 以 stub / mock 替身,**不**打真 AWS。

### 工作面二(歷史遷移,兩階段)

**Phase 1(只上傳)**

- `--dry-run` 能正確報出「待遷移列數 / 待上傳物件數」且**不寫入任何東西、不上傳**。
- 正式跑完後:S3 物件數 = 報表「應上傳數」;**`usage_logs` 完全未被修改**(以 `updated_at` 與內容快照比對驗證),系統行為與跑之前完全一致。
- 重複執行第二次:全部 `head_object` 命中、上傳 0 個(冪等)。
- 中途 Ctrl-C 後重跑:已上傳者跳過、未上傳者補完。

**驗收關卡(人工,通過才准跑 Phase 2)**

- 抽樣 ≥ 10 筆(涵蓋單輪 / messages 兩形狀、單圖 / 多圖)做 **byte-for-byte** 比對:S3 物件 == 原 base64 decode 結果。
- 抽樣以 presigned URL 實際開啟,圖片正常。
- `pg_dump` 備份完成,且**實際驗證過可還原**(不是「有跑過 dump」而已)。

**Phase 2(改寫 JSONB)**

- 執行後:`SELECT count(*) FROM usage_logs WHERE request_content::text LIKE '%data:%base64,%'` = **0**。
- 每個被改寫的值,其 key 在 S3 `head_object` 存在;**零筆**指向不存在物件的路徑。
- 若刻意刪掉某個 S3 物件再跑:該列被跳過並列入待處理清單,**不**被改寫(驗證安全網有效)。
- 重複執行第二次:處理 0 列(冪等)。中途 Ctrl-C 後重跑:已改寫列不重做、未改寫列補完,無資料遺失。
- 抽樣 ≥ 10 筆於明細頁能正常顯示,且圖片內容與遷移前一致。
- `updated_at` 依 §D.7 未被污染;其他欄位(`text` / 記帳 / tools / 生成參數)逐欄比對無變動。

### 工作面三(讀取端與周邊)

- 明細頁:已遷移列(路徑)與未遷移列(data URI)**都能顯示**,不互相干擾。
- AI 評估 / 重跑鏈路:對含圖紀錄照常運作,不因形狀改變而報錯或被當成空輸入。
- `.env.example` 鍵齊、註解齊、機密留空;`docker-compose*.yml` 兩份注入到位;`docs/INTEGRATION.md` 與 `user-guide` 頁已更新。
- CI green:`ruff` / `mypy` / `pytest` / `alembic upgrade head` round-trip;前端 `lint` / `type-check` / `build`。
- gitleaks 掃描無命中;`git log --all -- .env` 為空。

## 設計取捨 / 決議

| # | 議題 | Agent 建議 | 狀態 |
| --- | --- | --- | --- |
| 1 | 範圍 = 寫入端改存 S3 + 歷史 base64 全量遷移(base64 棄用) | — | ✅ user 指定(2026-07-29) |
| 2 | bucket = `df-openrouter-dispatch-prod` | — | ✅ user 指定(2026-07-29) |
| 3 | S3 SDK 選 `boto3` + `asyncio.to_thread` | boto3 | ⬜ 待拍板(§D.1) |
| 4 | 遠端 URL 輸入不代抓,原樣保留 | 不代抓 | ⬜ 待拍板(§D.2) |
| 5 | `files` 存實體(推翻 v2.1.2「僅記檔名」法務決策);視為新功能,歷史紀錄不回填 | 存實體 | ✅ **user 定案(2026-07-29)** |
| 6 | **下游 payload 完全不動**(照現行送 base64 / 原始 URL);presigned URL 僅用於管理端明細頁顯示 | 不動下游 | ✅ **user 定案(2026-07-29,推翻稍早的 presigned 下游方案)** |
| 7 | S3 上傳失敗 → **best-effort**:不擋請求、不降級 base64、只記 log + 快照留 `upload_failed` 標記;`file_data` base64 永不入 DB | best-effort | ✅ **user 定案(2026-07-29,修訂;推翻同日稍早的「擋下回 5xx」)** |
| 8 | 遷移兩階段(Phase 1 只上傳 → 人工驗收 → Phase 2 改寫);base64 於 Phase 2 才退場;走獨立 script(非 alembic) | 兩階段 | ✅ **user 定案(2026-07-29)** |
| 9 | 遷移不更新 `updated_at` | 不更新 | ⬜ 待拍板(§D.7) |
| 10 | 單一 bucket + `S3_KEY_PREFIX` 分環境,本版不設 lifecycle | 單 bucket | ⬜ 待拍板(§D.8) |
| 11 | 明細頁取圖:API 回吐時直接換 presigned URL | 直接換 | ⬜ 待拍板(§D.9) |
| 12 | 先補 Design-Base `90-third-party-service/09-object-storage.md` 再開工(含同步 `Design-Base/README.md` + `AGENTS.md` 兩處對照表) | 先改規範 | ✅ **user 定案(2026-07-29)** |
| 14 | internal provider 收到**檔案**時的下游 payload:維持現行 base64 直送(不落 DB,行為不變) | 維持現行 | ✅ **user 定案(2026-07-29;已被 #6 涵蓋 —— 所有下游 payload 一律不動)** |
| 15 | presigned URL 功能保留,用途收斂為管理端明細頁顯示 / 開啟附件 | 保留 | ✅ **user 定案(2026-07-29)** |
| 13 | 上線前 rotate 本次對話中明文出現的 AWS 金鑰 + IAM 權限收斂到單一 bucket | 建議照做 | ⬜ 待確認 |

## 變更紀錄

| 日期 | 改動 | 理由 |
| --- | --- | --- |
| 2026-07-29 | 初版草擬:圖片 / 檔案改存 S3(`df-openrouter-dispatch-prod`)、DB 只留路徑、歷史 base64 全量遷移並棄用 | user 指示(2026-07-29):❶ 未來含圖片 / 檔案請求全放 S3、DB 只存路徑;❷ 既有 base64 全數轉存 S3 並改為路徑,base64 棄用 |
| 2026-07-29 | §D.3 / §D.4 / §D.6 拍板並改寫對應章節:檔案存實體(視為新功能、歷史不回填);下游採 presigned URL(internal 與失敗時退回 base64);**遷移改為兩階段**(Phase 1 只上傳不動 DB → 人工驗收關卡 → Phase 2 才改寫 JSONB),key 設計為 deterministic 以免除 mapping / 暫存欄位 | user 定案(2026-07-29):❶「是,需要進行儲存,舊檔案不存在沒關係,當成新功能」;❷「base64 先暫時不動,等確定移轉成功後再棄用」;❸ 確認 S3 支援 presigned URL 後採用 |
| 2026-07-29 | §D.5 拍板 + 追加硬規則:上傳失敗擋下回 5xx、不降級;**`file_data` base64 任何情況下不得入 `usage_logs`**(經確認「炸掉」專指寫進 DB 那條路徑);§規範層級註記與決議表 #12 標記為定案 | user 定案(2026-07-29):「擋下請求,如果是 file 轉成 base64 我的系統會炸掉」;「file 寫進 DB 會炸」;「開工之前確實需要補第三方串接規範檔案沒錯」 |
| 2026-07-29 | **§D.4 整條翻案 → 下游 payload 完全不動**:取消「OpenRouter 改送 presigned URL」方案,`_rewrite_request` 本版零 diff;presigned URL 功能保留但用途收斂為管理端明細頁顯示。連帶消除下游相容性風險、fallback 滲入快照風險、internal 連外風險三項;新增「下游 payload 零變更」回歸驗收;決議表 #6 改寫、新增 #15 | user 定調(2026-07-29):「全部都不管下游給使用者的資訊,因為我改的只是平台後端 log 儲存路徑而已」;「還有 pre-signed 功能」(確認 presigned 保留供明細頁使用) |
| 2026-07-29 | **§D.5 修訂 → best-effort**:上傳失敗**不擋請求、不降級 base64、只記 log**;快照該附件留 `upload_failed` + metadata(mime / bytes / sha256),前端顯示「上傳失敗,內容未留存」;S3 client 加短 timeout + 低重試;新增「S3 全掛不影響代理可用性」對外承諾與驗收;風險新增「附件靜默遺失需可觀測」 | user 修訂(2026-07-29):「如果上傳失敗就失敗,幫我寫入 log 即可,不要降級成 base64,也不要擋死」——與 §D.4「只改 log 儲存路徑」自洽:記帳層不該擋掉本來會成功的請求 |
