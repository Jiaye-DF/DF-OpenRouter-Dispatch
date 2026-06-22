# 專案掃描報告 — Issue-Scan-Project-260622052905

> 本報告僅涵蓋**本地開發**範圍(程式碼 + 本地服務組態),不涵蓋部署規範。
> 前次基準:`Issue-Scan-Project-260529150850.md`(v1.6 時點)。本次涵蓋至 v1.10(申請單生命週期 + 規則路由 + AI 驗證自動開通 + M365 開通通知信 + SSO 自動帶部門)。

---

## 0. 與前次差異

以 `R-xxx` / `AD-xxx` ID + 路徑為 key。

| 狀態 | 項目 | 說明 |
| --- | --- | --- |
| ✅ 已修 | R-LOG-004 graceful shutdown | `main.py:31` 已加 `await engine.dispose()`。 |
| ✅ 已修 | R-BE-018 雜湊阻塞 | `auth.py:85,195` 已改 `await asyncio.to_thread(...)`。 |
| ✅ 已修 | R-LOG-001 health 探 DB | `api/v1/health.py:14-21` 已 `SELECT 1`,失敗回 503 `{db:down}`。 |
| ✅ 已修 | R-LOG-005 request_id | `logging.py` `_RequestIdFilter` + `main.py:54-63` middleware 已注入 `request_id`。 |
| 🔄 持續 | R-BE-008 CORS 萬用字元回退 | `main.py:48` 仍 `or ["*"]` + `allow_credentials=True`;`config.py:28` 仍空字串。 |
| 🔄 持續 | R-BE-020 prod fail-fast | `config.py` 仍只有 `is_prod`,無啟動驗證。 |
| 🔄 持續 | R-PII-001 SSO log 印 email | `sso.py:120,136` 仍 `email=%s`。 |
| 🔄 持續 | R-LOG-006 version 端點 | 仍無 `/api/v1/version`。 |
| 🔄 持續 | AD-001 SDK Key 明文存 DB | `models/sdk_api_key.py:23` `key_values` 仍明文(已文件化取捨)。 |
| 🆕 新增 | AD-002 同 owner 併發送單 race | 申請單開通鏈路無序列化/唯一約束保護。 |
| 🆕 新增 | R-BE-012 process 端點洩漏內部錯誤 | `api_key_requests.py:306-308` 把原始例外字串回前端。 |
| 🆕 新增 | AD-003 usage_log fire-and-forget | `proxy.py:329` `create_task` 無 reference,可能漏記帳。 |
| 🆕 新增 | AD-004 SSE relay 非 OR 例外不收尾 | `proxy.py:1037` 只攔 `OpenRouterError`。 |
| 🆕 新增 | AD-005 prompt/images 全文落地 | `proxy.py:317` `request_content` 存使用者輸入原文。 |
| 🆕 新增 | AD-006 無 per-caller 配額 | SDK Key 維度無呼叫量/頻率上限。 |
| 🆕 新增 | AD-007 OR Key failover N+1 | `proxy.py:448-451` 重試迴圈內每圈重查全表。 |
| 🆕 新增 | AD-008 status server_default 不一致 | `models/api_key_request.py:33-35` 預設 `pending` 不在狀態機。 |

---

## 1. 總覽

| 項目 | 內容 |
| --- | --- |
| 掃描時間 | 2026-06-22 05:29 (UTC+8) |
| 涵蓋類別 | ENV / AI / FE / BE / DB / SEC / PII / LOG / GIT / TEST / DEP |
| 🔴 Critical | 1 |
| 🟠 High | 6 |
| 🟡 Medium | 3 |
| 🔵 Low | 3 |
| ⚪ Info | 0 |

**結論**:前次 4 項維運盲點(graceful shutdown、health 探 DB、雜湊阻塞、request_id)已全數修正,工程基線持續提升。本次新風險集中在 **v1.7–v1.10 新增的申請單自動開通鏈路**:`process` 端點把原始例外字串回前端(R-BE-012)、同 owner 併發送單缺乏序列化保護(AD-002)、以及 LLM 派發核心的記帳 `create_task` fire-and-forget 有漏寫風險(AD-003)。唯一 🔴 仍是前次未處理的 CORS 回退(R-BE-008)。前端(Next.js)經查無 localStorage 存 token、無 `dangerouslySetInnerHTML`、無 `any`、無分散 fetch、三態齊全;DB schema 金額用 `Numeric`、密碼 argon2、無 SQL 拼接、`find_by_uid` 全過濾軟刪、migration 線性無重寫,品質佳。

---

## 2. 專案摘要

- **目標**:DF-OpenRouter-Dispatch — 內部 LLM 派發閘道,統一管理 OpenRouter / 內部模型的 Key、配額、用量統計,並透過 SDK Key + DF-SSO 對接內部系統。
- **技術棧對照**:

  | 層 | 規範預期 | 實際 | 對照 |
  | --- | --- | --- | --- |
  | FE | React | Next.js 14 (App Router) + Redux Toolkit + RTK Query + Tailwind | ✅ |
  | BE | FastAPI | FastAPI + Pydantic v2 + 分層(api/services/repositories/clients) | ✅ |
  | DB | PostgreSQL + SQLAlchemy | asyncpg + `async_sessionmaker` + Alembic(0001→0015 線性) | ✅ |
  | Log | 集中式 | Seq(`seqlog`)+ console fallback + request_id | ✅ |

- **目錄結構**:後端分層清楚;前端標準 Next.js 結構,API 集中於 `lib/api/client.ts`。
- **Task 進度**:已至 v1.10(SSO 自動帶部門 + 稽核 log JSONB 修正,見 `docs/Tasks/v1.10/fixed.md`)。
- **完成度**:功能成熟,申請單自動開通(route→AI→provision)鏈路完整,具測試與 e2e smoke。

---

## 3. 詳細發現(依嚴重度)

### 🔴 [R-BE-008] CORS 萬用字元回退搭配 `allow_credentials=True`(持續)

- **檔案**:`backend/app/main.py:48`、`backend/app/core/config.py:28,87-88`
- **內容**:`allow_origins=settings.cors_origins_list or ["*"]` 且 `allow_credentials=True`;`CORS_ORIGINS` 預設空字串 → `cors_origins_list` 回空陣列 → 回退 `["*"]`。正式環境若漏設該變數,靜默變成「任意來源 + 攜帶 cookie」。
- **白話**:本服務以 httpOnly cookie 認證,萬用字元 + credentials 等於允許任何外部站台的 JS 帶使用者 cookie 對本 API 發已認證請求並讀回應,構成跨站資料外洩 / CSRF。
- **修正**:`main.py:48` 移除 `or ["*"]`,改 `allow_origins=settings.cors_origins_list`;並於 prod 啟動 fail-fast(見 R-BE-020)。本機開發在 `.env` 明確填 `CORS_ORIGINS=http://localhost:3000`。
- **首次發現**:2026-05-29

### 🟠 [AD-002] 同 owner 併發送單 → race condition 重複開通(新增)

- **檔案**:`backend/app/api/v1/api_key_requests.py:144-213`、`backend/app/services/api_key_request_router.py`(整個 `route`)、`backend/app/services/api_key_request_provision.py`
- **內容**:`route()` 靠 SELECT 判斷「既有專案 / 既有使用者 / 已存在相同 Key 去重」,但 `route → AI → provision → commit` 全程對 department / project / user **無鎖、無唯一約束保護的 upsert**。同 `owner_email`、同 `project_name`、同部門的兩個請求同時進入時,兩者都看到「無既有資料」→ 都走開通 → 建立兩套 Project / User / SDK Key,`system_cancel` 去重被繞過。
- **白話**:使用者手滑雙擊送出或前端 retry,系統就長出兩套重複專案 + 使用者 + 金鑰,且狀態機都認為「成功」。已發出的一次性憑證可能已被領走,事後難清理。送單是同步 POST,雙擊是最常見的真實情境。
- **修正**(擇一,建議第 1 項,改動最小):
  1. 對 `projects(department_uid, name)`、`users(email)` 加 DB 層唯一約束 / 部分唯一索引,第二筆 insert 在 `provision.py` flush 直接撞約束 → 落入 except → 降級人工。
  2. `api_key_requests.py:144` `route()` 前對 `owner_email` 做 `pg_advisory_xact_lock(hashtext(owner_email))` 序列化同 owner 送單。
  3. 前端送出按鈕送出後即 disable(R-FE-006),降低但不根除。
- **首次發現**:2026-06-22

### 🟠 [R-BE-012] `process` 端點把原始例外字串當 response detail 回前端(新增)

- **檔案**:`backend/app/api/v1/api_key_requests.py:304-308`,搭配 `backend/app/services/api_key_request_provision.py:146`(`error=str(exc)[:300]`)、`backend/app/core/exceptions.py:11-18`(`AppError` 首參即 `detail`)、`main.py:66-67`(原樣回傳)
- **內容**:人工開通失敗時 `raise AppError((pr.error ...) or "provision_failed", code=409)`;`pr.error` 是 `str(exc)[:300]` 的**原始例外字串**,可能含 SQLAlchemy 訊息、約束名、表名、欄位名,甚至 `IntegrityError` 的 `DETAIL: Key (email)=(...)` 把**他人 email(PII)** 回灌畫面。`AppError.detail` 經 `failure_response` 原樣寫入回應 `detail`。
- **白話**:admin 後台人工開通失敗時,畫面直接顯示資料庫底層錯誤,甚至第三方 email。對比 `create` 端點(`:179`)只把 `pr.error` 寫進內部欄位 `error_message`,風險低;`process` 這條直接進 HTTP 回應。雖為 admin-only,內部 schema 與第三方 PII 仍不應出現在錯誤回應。
- **修正**:`api_key_requests.py:306-308` 改回固定碼,細節只進 log:
  ```python
  except Exception as exc:
      await db.rollback()
      logger.exception("人工開通失敗 request_uid=%s", row.request_uid)
      raise AppError("provision_failed", code=409) from exc
  ```
  (`pr.error` 可續寫入 `row.error_message` 供內部查,但不進 response。)
- **首次發現**:2026-06-22

### 🟠 [AD-003] 用量記帳 `create_task` fire-and-forget,可能被 GC 靜默取消而漏寫(新增)

- **檔案**:`backend/app/services/proxy.py:328-331`(`schedule_usage_log` 的 `asyncio.create_task(_task())`)
- **內容**:`create_task` 的回傳無任何人持有 reference。CPython 文件明載 event loop 只持 task 的 weak reference,無強引用的 task 可能在完成前被 GC 回收而**靜默取消**(高併發 / GC 壓力下)。
- **白話**:對一個以「用量 / 計費統計」為核心價值的閘道,部分 `usage_logs` 會隨機漏寫且不報錯 — 帳對不起來。串流路徑(`proxy.py:1047`)同樣經此函式。
- **修正**:module-level `set` 持強引用,完成後移除:
  ```python
  _bg_tasks: set[asyncio.Task] = set()
  ...
  t = asyncio.create_task(_task())
  _bg_tasks.add(t)
  t.add_done_callback(_bg_tasks.discard)
  ```
- **首次發現**:2026-06-22

### 🟠 [R-BE-020] 缺 production 啟動 fail-fast 檢查(持續)

- **檔案**:`backend/app/core/config.py`(僅有 `is_prod`,無啟動驗證)
- **內容**:prod 特有安全前提未把關:`JWT_SECRET` 長度未驗證(R-SEC-001 要求 ≥ 32)、prod 下 `CORS_ORIGINS` 為空仍可啟動(配合 R-BE-008 即成 🔴)。
- **白話**:組態錯誤的服務能在 prod 正常起來,把安全問題推遲到被攻擊時才暴露。
- **修正**:於 `Settings` 加 model validator:`is_prod` 為真時斷言 `len(JWT_SECRET) >= 32` 且 `cors_origins_list` 非空,否則 raise。
- **首次發現**:2026-05-29

### 🟠 [R-PII-001] SSO 登入 log 印出明文 email(持續)

- **檔案**:`backend/app/services/sso.py:120`(首次建立成員)、`:136`(登入成功)
- **內容**:`logger.info("...email=%s", ..., email)` — email 屬 PII,且會推送至集中式 Seq。
- **白話**:PII 進入 log 系統留存於第三方檢索介面,違反最小化;Seq 權限或保存週期失控即構成個資外洩面。
- **修正**:遮罩後再記(只記網域或前綴),或改記 `user_uid` 取代 email。
- **首次發現**:2026-05-29

### 🟠 [AD-001] SDK API Key 以明文存 DB(持續,已文件化取捨)

- **檔案**:`backend/app/models/sdk_api_key.py:19-23`(`key_hash` argon2 + `key_values` 明文 `Text`)、reveal 於 `backend/app/services/sdk_key.py:45,53-59`
- **內容**:除 argon2 `key_hash` 外另存完整明文 `key_values`,後台可原樣還原與複製(`frontend/.../departments/page.tsx`)。註解載明為 v1.5「業務要求 DB 可直編,接受 DB dump 等同明文外洩」,並有 migration `0009` 從加密版回退。屬已簽核決策,非疏漏。
- **白話**:DB dump / 唯讀備份外洩即等同所有 SDK Key 外洩,可冒用呼叫派發閘道。對比 `internal_keys` / `openrouter_keys` 皆用加密 `key_ciphertext`,標準不一致。
- **修正(供決策參考)**:理想改為「建立時一次性顯示明文」(與 User Token reveal-once 一致);若硬須 DB 可直編,退而採對稱加密欄(比照 `0008`)。維持現狀則建議於 Design-Base 留正式簽核。
- **首次發現**:2026-05-29

---

### 🟡 [AD-004] SSE relay 只攔 `OpenRouterError`,非 OR 例外不補送收尾(新增)

- **檔案**:`backend/app/services/proxy.py:1037`
- **內容**:串流中途若發生**非** `OpenRouterError`(httpx `ReadError`、`asyncio.TimeoutError` 等),不會送 `error chunk + [DONE]`,直接穿過 `except` 進 `finally`。客戶端 SSE 收到無預警截斷、且等不到 `[DONE]`。記帳在 `finally`(`:1047`)仍會執行,故帳不漏;但若 `:1045 agen.aclose()` 自身拋例外則會跳過記帳。
- **白話**:特定失敗型態(逾時 / 連線中斷)下串流不優雅收尾,SSE 客戶端 hang。
- **修正**:`except` 增 `except Exception` 分支同樣補送 error chunk + `[DONE]`;`finally` 把 `agen.aclose()` 包 `try/except` 與記帳分離,確保記帳必執行(`CancelledError` 應在記帳後 re-raise)。
- **首次發現**:2026-06-22

### 🟡 [AD-005] prompt / images 全文落地 `usage_logs.request_content`(新增)

- **檔案**:`backend/app/services/proxy.py:92-112`(`_build_request_log`)、`:317`(`request_content=request_log`)
- **內容**:完整保留使用者 `text`(prompt 原文)與 `images`(URL / data URI)寫入 DB JSONB。`files` 已只記檔名(法務考量),但 text / images 無同等保護。
- **白話**:prompt 常含 PII / 營業機密,全文長期留存(疊加 AD-001 的明文 Key)放大外洩衝擊,屬合規(個資法)風險。註:此為寫 DB 非寫 logger(logger 面向乾淨)。可能為 dashboard 檢視的有意設計,故列 🟡 供評估。
- **修正**:評估保留必要性;至少對 images 比照 files 只記 metadata,或加欄位級加密 / 保留期限。
- **首次發現**:2026-06-22

### 🟡 [AD-006] SDK Key 維度無配額 / rate limit(新增)

- **檔案**:`backend/app/core/sdk_auth.py`(整支)、`backend/app/api/v1/model_chat.py`
- **內容**:`resolve_sdk_caller` 只做身分解析(key 有效 / 部門一致 / user 未撤銷 / project 有效),**無任何 per-SDK-Key 或 per-user 的呼叫量 / 頻率上限**。速率限制只在 proxy 層綁**下游 OpenRouter / Internal Key**(供應商側),非綁呼叫者。
- **白話**:任何一把合法(或被盜)SDK Key 可無上限打 LLM,單一租戶可吃光該部門所有 Key 額度、灌爆成本,其他人被 failover 拖累;`usage_logs` 只能事後看不能事前擋。
- **修正**:在 caller 維度(`sdk_api_key_uid` / department / user)加配額或 RPM 閘門,於進 proxy 前檢查。
- **首次發現**:2026-06-22

---

### 🔵 [R-LOG-006] 缺 `/api/v1/version` 端點(持續)

- **檔案**:`backend/app/api/v1/`(無 version route)
- **內容 / 白話**:無版本端點,滾動更新後不易確認線上 build。
- **修正**:新增 `GET /api/v1/version` 回 `{"version": "...", "app": settings.APP_NAME}`。
- **首次發現**:2026-05-29

### 🔵 [AD-007] OpenRouter Key failover 在重試迴圈內每圈重查全表(新增)

- **檔案**:`backend/app/services/proxy.py:448-451`、`942-945`(`pick_random_active` → `repositories/openrouter_key.py` `list_active_by_department`)
- **內容**:failover 迴圈每輪都重新查整張 active key 表(最多 `_MAX_RETRIES=5` 次)。internal 路徑(`proxy.py:645` 一帶)已是「迴圈外查一次、記憶體 shuffle」,兩條路徑作法不一致。
- **白話**:每次 failover 多打 DB,純浪費;Key 多 / 併發高時放大 DB 負載。功能正確、僅低效。
- **修正**:迴圈外查一次 active keys,記憶體內 shuffle 依序取,對齊 internal 路徑寫法。
- **首次發現**:2026-06-22

### 🔵 [AD-008] `api_key_requests.status` 的 `server_default` 與狀態機不一致(新增)

- **檔案**:`backend/app/models/api_key_request.py:33-35`
- **內容**:`server_default="pending"`,但 v1.9.1 狀態機(`manual_pending / agent_done / done / revoked / cancelled`)無 `pending`。service 層 INSERT 都明確賦值,故幾乎不會命中;但若有路徑漏設,會落入前端 `statusBadge()` 無對應的孤兒狀態。
- **修正**:改 `server_default="manual_pending"` 對齊初始態,或移除 server_default 強制 service 賦值。
- **首次發現**:2026-06-22

---

## 4. 修正優先序

**立刻(本次)**
- 🔴 R-BE-008 — 移除 `or ["*"]` 回退(一行),唯一 Critical。
- 🟠 R-BE-020 — 同步補 prod fail-fast,封住 R-BE-008 的「忘記設定」破口。
- 🟠 R-BE-012 — `process` 端點改回固定錯誤碼(避免內部 schema / 他人 PII 外洩,改動小)。

**本週**
- 🟠 AD-002 — 申請單併發送單:加 `projects/users` 唯一約束(治本、最小改動)。
- 🟠 AD-003 — usage_log `create_task` 持強引用,堵住記帳漏寫。
- 🟠 R-PII-001 — SSO log email 遮罩。
- 🟠 AD-001 — 決策:SDK Key 是否改 reveal-once / at-rest 加密(或正式簽核維持現狀)。

**有空**
- 🟡 AD-004 SSE 收尾、🟡 AD-005 prompt at-rest、🟡 AD-006 per-caller 配額。
- 🔵 R-LOG-006 version、🔵 AD-007 failover N+1、🔵 AD-008 status 預設值。

---

## 5. 已跳過類別(附原因)

| 類別 | 原因 |
| --- | --- |
| `R-ENV-001/003/004/006`、`R-GIT-001` | `.env` 已 gitignore、git 歷史無 `.env`、無敏感檔被追蹤、無機密寫死;`.env` 本地未提供無法比對 example 值。 |
| `R-DB-002`(created_by / updated_by) | **規範優先**:`Design-Base/30-database.md §1` 未要求,actor 追蹤由 `audit_logs` 負責。 |
| `R-BE-003`(Response 外殼) | **規範優先**:`90-task-spec.md` 外殼為 `{success, code, data, detail}`,`response.py` 相符;規則 `response_code` 被覆蓋。 |
| `R-BE-001`(back-channel `/api/auth`) | DF-SSO 中央寫死路徑的硬性需求,文件化例外。 |
| `R-FE-001/002/003/010/012`、`R-SEC-004` | 已驗證:無 localStorage 存 token、無 `dangerouslySetInnerHTML`、fetch 集中 `lib/api/client.ts`、無 `any`、無原生 `alert/confirm`、無 `eval/exec`。 |
| `R-SEC-002`(login rate limit) | 已具帳號層級鎖定(5 次失敗鎖 15 分),視為等效緩解。**但** SDK Key 維度無配額,另記 AD-006。 |
| `R-DB-003/004/005/006/009`、migration 重寫 | 密碼 argon2、無 SQL 拼接、金額 `Numeric`、軟刪除齊全、`find_by_uid` 全過濾 `is_deleted`、0001→0015 線性無重寫。 |
| `rate_limit` 單 process | 已文件化(檔頭註明 multi-worker 需 v1.3 Redis),屬已知待辦,不重複計列。 |

---

## 6. AD-xxx(規則外發現)

已列於第 3 章:**AD-001**(SDK Key 明文,🟠)、**AD-002**(併發送單 race,🟠)、**AD-003**(usage_log 漏寫,🟠)、**AD-004**(SSE 收尾,🟡)、**AD-005**(prompt at-rest,🟡)、**AD-006**(無 per-caller 配額,🟡)、**AD-007**(failover N+1,🔵)、**AD-008**(status 預設值,🔵)。

**已巡視但未形成正式發現的面向(低後果,僅記錄)**:
- **SDK Key 驗證 timing/prefix enumeration**(`sdk_auth.py:44-56`):prefix 命中與否的耗時差可枚舉有效 prefix,但 secret 仍 62^32 熵,實務爆破不可行 → 低後果,建議 candidates 為空時跑一次 dummy verify 即可。
- **claim-secrets 併發領取**(`api_key_requests.py:380-381`):無樂觀鎖,併發下同一人可領兩次明文;同申請人、影響有限。建議改條件式 UPDATE RETURNING 原子領取。
- **交易邊界**:`provision()` 全程只 flush、由端點 `begin_nested()` savepoint 包裹,失敗整段 rollback;commit 由端點統一負責 — 設計正確。寄信 `send_provision_email` 全失敗路徑回 `EmailResult(ok=False)` 不拋例外,best-effort 正確。
- **權限**:申請單 list 後端強制範圍(member 只看自己,忽略前端參數);get/cancel/claim 檢查本人或 admin;process/resend 強制 admin。proxy 白名單對不存在 / 停用 / 軟刪一律回同一 `model_forbidden(403)`,不洩漏模型是否存在。
- **logger 機密 / PII**:proxy 全鏈路 Key 只記 `*_key_uid`,不記 raw key / token / prompt;`email_graph` 只記收件網域。logger 面向乾淨(PII 問題在寫 DB,見 AD-005)。
- **重試收斂**:OpenRouter / Internal 兩路徑皆有 `_MAX_RETRIES` + `tried` 集合,單請求不會無限重試。

---

## 7. 規範自身問題(Design-Base 矛盾 / 缺漏)

1. **R-DB-002 與 `30-database.md §1` 衝突**:通用規則要求 `created_by/updated_by`,專案規範未列(本次依規範優先跳過)。建議擇一註明避免每次誤報。
2. **R-BE-003 字段名**:通用規則寫 `response_code`,實作與規範均為 `code`。建議規則措辭統一為「`code`(或 `response_code`)」。
3. **Design-Base 缺「機密 at-rest 加密」準則**:`internal_keys` / `openrouter_keys` 加密、`sdk_api_keys` 明文並存(AD-001)。建議於 `30-database.md` 或新增安全章節明定「哪類機密須加密、哪類可明文及其簽核要求」,讓取捨有據。
4. **缺「對外錯誤回應內容」準則**:R-BE-012 此次在 `process` 端點重現,建議於 Design-Base 明文「API 回應 `detail` 一律為穩定錯誤碼字串,原始例外只進 log」,作為各端點一致準則。

---

> 唯一 🔴(R-BE-008)與兩個高槓桿、低改動的新發現(R-BE-012 一段 try/except、AD-002 一條唯一約束、AD-003 一個 task set)可一併處理。需要我直接動手修這幾項嗎?
