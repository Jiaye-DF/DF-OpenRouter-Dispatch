# 專案掃描報告 — Issue-Scan-Project-260529150850

> 本報告僅涵蓋**本地開發**範圍(程式碼 + 本地服務組態),不涵蓋部署規範。
> 首次掃描,無前次報告可比對(故省略「與前次差異」章節)。

---

## 1. 總覽

| 項目 | 內容 |
| --- | --- |
| 掃描時間 | 2026-05-29 15:08 (UTC+8) |
| 涵蓋類別 | ENV / AI / FE / BE / DB / SEC / PII / LOG / GIT / TEST / DEP |
| 🔴 Critical | 1 |
| 🟠 High | 5 |
| 🟡 Medium | 2 |
| 🔵 Low | 1 |
| ⚪ Info | 0 |

**結論**:整體工程品質佳。Auth 流程(帳號鎖定、refresh token reuse 偵測、密碼變更失效)、統一 Response、Repository 軟刪除、Numeric 金額、集中式 API client、argon2 雜湊、Seq 集中 log 等皆到位。主要風險集中在**單一 🔴(CORS 萬用字元 + credentials 的預設回退)**,以及維運盲點(graceful shutdown、prod fail-fast)與 PII log。無機密寫死、無 `eval/exec`、無 localStorage 存 token、前端無 `any`。

> **註(2026-05-29)**:prod 目前確實由 Coolify 注入 `CORS_ORIGINS`,故 fallback 暫不會觸發;但 `or ["*"]` 屬 insecure default(漏設即靜默退成最不安全狀態),應 fail-loud 而非 fallback,故維持 🔴 — 此風險不因「目前剛好有設」而消失。

---

## 2. 專案摘要

- **目標**:DF-OpenRouter-Dispatch — 內部 LLM 派發閘道,統一管理 OpenRouter / 內部模型的 Key、配額、用量統計,並透過 SDK Key + DF-SSO 對接內部系統。
- **技術棧對照**:

  | 層 | 規範預期 | 實際 | 對照 |
  | --- | --- | --- | --- |
  | FE | React | Next.js 14 (App Router) + Redux Toolkit + RTK Query + Tailwind | ✅(`NEXT_PUBLIC_*` 前綴) |
  | BE | FastAPI | FastAPI + Pydantic v2 + 分層(api/services/repositories/clients) | ✅ |
  | DB | PostgreSQL + SQLAlchemy | asyncpg + `async_sessionmaker` 連線池 + Alembic | ✅ |
  | Log | 集中式 | Seq(`seqlog`)+ console fallback | ✅ |

- **目錄結構**:`backend/app/{api,services,repositories,clients,core,models,schemas}` 分層清楚;`frontend/src/{app,components,lib,store}` 標準 Next.js 結構。
- **Task 進度**:已至 v1.6(儀表板日期區間篩選 + `usage_logs.created_at` 索引)。
- **完成度**:功能成熟,測試涵蓋 core(crypto/password/security)與 services(rate_limit),具 e2e smoke 腳本。

---

## 3. 詳細發現(依嚴重度)

### 🔴 [R-BE-008] CORS 萬用字元回退搭配 `allow_credentials=True`

- **檔案**:`backend/app/main.py:40-46`、`backend/app/core/config.py:28,73-74`
- **內容**:`allow_origins=settings.cors_origins_list or ["*"]` 且 `allow_credentials=True`。`CORS_ORIGINS` 預設為空字串(`config.py:28`),`cors_origins_list` 回傳空陣列 → 回退為 `["*"]`。`docker-compose-prod.yml:34` 以 `${CORS_ORIGINS}` 注入,**若正式環境忘記設定該變數,會靜默變成「任意來源 + 攜帶 cookie」**。
- **白話**:本服務以 httpOnly cookie 認證。萬用字元 + credentials 等於允許任何外部網站的 JS 帶著使用者 cookie 對本 API 發出已認證請求並讀取回應,構成跨站資料外洩 / CSRF 風險。
- **修正**:
  1. `main.py:42` 移除 `or ["*"]` 回退;改為 `allow_origins=settings.cors_origins_list`(空則不開放跨域)。
  2. 於 prod 啟動時 fail-fast:`CORS_ORIGINS` 為空即 raise(見 R-BE-020)。
  3. 本機開發如需跨域,於 `.env` 明確填 `CORS_ORIGINS=http://localhost:3000`,而非靠程式回退。
- **首次發現**:2026-05-29

### 🟠 [R-LOG-004] `lifespan` 關閉時未 `await engine.dispose()`

- **檔案**:`backend/app/main.py:18-26`、`backend/app/core/database.py:13-19`
- **內容**:`lifespan` 的 `yield` 之後僅呼叫 `flush_logging()`,未釋放 DB 連線池。
- **白話**:服務關閉 / 重啟時連線池未優雅關閉,可能殘留連線或在容器滾動更新時讓 PostgreSQL 端累積待回收連線。
- **修正**:`main.py:26` 於 `flush_logging()` 前後加入 `await engine.dispose()`(從 `app.core.database` import `engine`)。
- **首次發現**:2026-05-29

### 🟠 [R-BE-018] argon2 雜湊在 async 路徑裸呼叫(阻塞 event loop)

- **檔案**:`backend/app/core/security.py:16-26`,呼叫點 `backend/app/services/auth.py:84`(`verify_password`)、`auth.py:198`(`hash_password`)
- **內容**:規則 R-BE-018 針對 bcrypt,argon2 同屬 CPU 密集雜湊(預設約 40–100ms),於 async login / reset password 路徑中直接呼叫會阻塞事件迴圈。
- **白話**:`UVICORN_WORKERS=1`(預設)下,登入尖峰會讓單一 worker 在雜湊計算時無法處理其他請求,造成可感知延遲。
- **修正**:`auth.py:84` 改 `if not await asyncio.to_thread(verify_password, password, user.password_hash):`;`auth.py:198` 改 `user.password_hash = await asyncio.to_thread(hash_password, new_password)`。
- **首次發現**:2026-05-29

### 🟠 [R-BE-020] 缺 production 啟動 fail-fast 檢查

- **檔案**:`backend/app/core/config.py`(僅有 `is_prod` property,無 `_fail_fast_in_prod`)
- **內容**:必填欄位(`DATABASE_URL` / `JWT_SECRET` / `ENCRYPTION_KEY` / `INITIAL_ADMIN_*`)缺漏雖會在啟動時報錯,但**正式環境特有的安全前提未把關**:`JWT_SECRET` 長度未驗證(R-SEC-001 要求 ≥ 32)、prod 下 `CORS_ORIGINS` 為空仍可啟動(配合 R-BE-008 即成 🔴)。
- **白話**:組態錯誤的服務能在 prod 正常起來,把安全問題推遲到被攻擊時才暴露。
- **修正**:於 `Settings` 加 model validator(或 `_fail_fast_in_prod`):`is_prod` 為真時,斷言 `len(JWT_SECRET) >= 32` 且 `cors_origins_list` 非空,否則 raise。
- **首次發現**:2026-05-29

### 🟠 [R-PII-001] SSO 登入成功 log 印出明文 email

- **檔案**:`backend/app/services/sso.py:78`
- **內容**:`logger.info("SSO 登入成功 account=%s email=%s", user.account, email)` — email 屬 PII,且此 log 會推送至集中式 Seq。
- **白話**:PII 進入 log 系統後留存於第三方檢索介面,違反最小化原則;若 Seq 權限或保存週期失控即構成個資外洩面。
- **修正**:遮罩後再記錄,例:只記網域或前綴 `email=ab***@df-recycle.com.tw`;或改記 `user_uid` 取代 email。`account` 同樣建議評估是否為 PII。
- **首次發現**:2026-05-29

### 🟠 [AD-001] SDK API Key 以明文存 DB

- **檔案**:`backend/app/models/sdk_api_key.py:23-27`(`key_values: Text`)
- **內容**:`key_values` 存完整 key 明文,程式碼註解明載為 v1.5「業務要求 DB 可直編填值,接受 DB dump 等同明文外洩的風險取捨」。此為**已文件化的風險接受**,非疏漏。
- **白話**:仍屬實質風險 — DB dump / 唯讀備份外洩即等同所有 SDK Key 外洩,可被冒用呼叫派發閘道。專案已具 `ENCRYPTION_KEY` 與加密機制(`internal_keys.key_ciphertext` 即用 `LargeBinary` 加密)。
- **修正(供決策參考,非強制)**:若可接受,將 `key_values` 改走與 `internal_keys` 相同的對稱加密(at-rest 加密),後台讀取時解密顯示 — 既滿足「後台可直編 / 顯示明文」需求,又避免 DB dump 直接外洩。若維持現狀,建議於 `docs/Design-Base` 或 v1.5 fixed 留下正式簽核紀錄。
- **首次發現**:2026-05-29

### 🟡 [R-LOG-001] `/api/v1/health` 未檢查 DB 連線

- **檔案**:`backend/app/api/v1/health.py:9-11`
- **內容**:`health()` 固定回 `{"status": "ok"}`,未實際探測 DB。規則要求回 `{db}` 連線狀態。
- **白話**:health check 永遠綠燈,DB 斷線時 LB / 容器健康檢查仍判定服務健康,失去探活意義。
- **修正**:注入 `DbDep`,執行 `await db.execute(text("SELECT 1"))`,回 `{"status": "ok", "db": "ok"}`;失敗則回 503 + `{"db": "down"}`。
- **首次發現**:2026-05-29

### 🟡 [R-LOG-005] Log 缺結構化關聯欄位(request_id)

- **檔案**:`backend/app/core/logging.py:62-65`
- **內容**:Seq 已設定全域 `Application` / `Environment`,但無 `request_id`(或 trace id)可串接單一請求的多筆 log;console 格式 `_CONSOLE_FORMAT` 亦無。
- **白話**:正式環境排查時無法依單一請求把分散的 log 串起來,故障定位成本高。
- **修正**:加一個 middleware 產生 / 透傳 `X-Request-ID`,以 `contextvars` + log filter 注入每筆 record(Seq 走 `support_extra_properties`)。
- **首次發現**:2026-05-29

### 🔵 [R-LOG-006] 缺 `/api/v1/version` 端點

- **檔案**:`backend/app/api/v1/`(無 version route)
- **內容**:無回傳版本資訊的端點,部署後無法快速確認線上版本。
- **白話**:滾動更新後不易驗證實際跑的是哪個 build。
- **修正**:新增 `GET /api/v1/version` 回 `{"version": "1.6.0", "app": settings.APP_NAME}`。
- **首次發現**:2026-05-29

---

## 4. 修正優先序

**立刻(本次)**
- 🔴 R-BE-008 — 移除 `or ["*"]` 回退(一行),這是唯一 Critical。
- 🟠 R-BE-020 — 同步補 prod fail-fast,封住 R-BE-008 的「忘記設定」破口。

**本週**
- 🟠 R-LOG-004 — `engine.dispose()`(一行)。
- 🟠 R-BE-018 — login / reset 雜湊改 `asyncio.to_thread`。
- 🟠 R-PII-001 — SSO log email 遮罩。
- 🟠 AD-001 — 決策:SDK Key 是否改 at-rest 加密(或正式簽核維持現狀)。

**有空**
- 🟡 R-LOG-001 health DB 探測、🟡 R-LOG-005 request_id、🔵 R-LOG-006 version 端點。

---

## 5. 已跳過類別(附原因)

| 類別 | 原因 |
| --- | --- |
| `R-ENV-004`(env 與 example key 不一致) | `.env` 已 gitignore 且本地未提供,無法比對;`.env.example` 鍵齊全。 |
| `R-DB-002`(created_by / updated_by) | **規範優先**:`docs/Design-Base/30-database.md §1` 僅要求 `<entity>_uid` / `is_active` / `is_deleted` / `created_at` / `updated_at`,均已具備;actor 追蹤由 `audit_logs` 表負責。規則的 `created_by/updated_by` 與專案規範衝突 → 跳過。 |
| `R-BE-003`(Response 外殼) | **規範優先**:`Design-Base/90-task-spec.md` 定義外殼為 `{success, code, data, detail}`,`response.py` 完全相符;規則的 `response_code` 字段名被專案規範覆蓋。 |
| `R-BE-001`(`/api/auth` back-channel) | `back_channel.py` 掛在 `/api/auth`(非 `/api/v1`),程式註解載明為 DF-SSO 中央寫死路徑的硬性需求,屬文件化例外。 |
| `R-FE-001/002/012`、`R-SEC-004` | 已驗證無 localStorage 存 token、無 `dangerouslySetInnerHTML`、無原生 `alert/confirm`、無 `eval/exec`。 |
| `R-ENV-001/003/006`、`R-GIT-001` | 無機密寫死、`.env` 已 gitignore 且 git 歷史無 `.env`、無敏感檔被追蹤。 |
| `R-SEC-002`(login rate limit) | 已具帳號層級鎖定(`auth.py:22-23,85-90`:5 次失敗鎖 15 分),視為等效緩解。 |

---

## 6. AD-xxx(規則外發現)

- **AD-001**(已列於第 3 章,🟠):SDK API Key 明文存 DB — 已文件化的風險取捨,仍建議評估 at-rest 加密。

**已巡視但無額外發現的面向**:
- **邏輯邊界**:auth refresh token reuse 偵測(`auth.py:134-140` family 撤銷)、密碼變更使舊 access 失效(`deps.py:53`)— 設計嚴謹。
- **效能(N+1 / 阻塞 / re-render)**:proxy 的 `for key_row in shuffled`(`proxy.py:434`)為 Key 輪詢非 DB N+1;前端集中 RTK Query 無元件層裸 `fetch`。唯一阻塞點為 argon2(已記 R-BE-018)。
- **商業邏輯(transaction / 狀態機 / race)**:`auth.py` login / refresh 以單一 session commit;refresh 採 rotate + reuse 偵測狀態機,正確。
- **啟動**:必填 env 缺漏會 fail(但缺 prod 專屬把關,已記 R-BE-020)。
- **維運盲點**:graceful shutdown 缺 `engine.dispose()`(R-LOG-004)、health 未探 DB(R-LOG-001)、無 version 端點(R-LOG-006)。

---

## 7. 規範自身問題(Design-Base 矛盾 / 缺漏)

1. **R-DB-002 與 `30-database.md §1` 衝突**:通用規則要求 `created_by/updated_by`,專案規範未列。建議在 scan-project 規則或 Design-Base 擇一註明,避免每次掃描誤報(本次已依「規範優先」跳過)。
2. **R-BE-003 字段名不一致**:通用規則寫 `response_code`,專案實作與規範均為 `code`。建議統一規則措辭為「`code`(或 `response_code`)」以免誤判。
3. **Design-Base 缺「機密 at-rest 加密」準則**:`internal_keys` 加密、`sdk_api_keys` 明文兩種做法並存(AD-001),建議於 `30-database.md` 或新增安全章節明定「哪類機密須加密、哪類可明文及其簽核要求」,讓取捨有據可循。

---

> 需要我直接動手修 🔴 R-BE-008(移除 `["*"]` 回退)嗎?可一併把 🟠 R-BE-020(prod fail-fast)補上,兩者一起才算真正堵住這個破口。
