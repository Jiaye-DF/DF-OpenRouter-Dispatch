# Task v1.0

## 版本資訊

- **前置依賴**：無（本專案由零建置，本版本為 MVP）。
- **本版本範圍**：後端骨架 + 本地登入系統 + 組織結構（部門／專案）+ OpenRouter Key 管理 + SDK 代理端點 + 用量紀錄與基礎後台儀錶板。本版本**不包含**多階段審批、進階配額策略、影片輸入（預留欄位）。
- **對齊的 Design-Base 章節**：
  - [00-overview.md § Monorepo 目錄結構](../../Design-Base/00-overview.md#monorepo-目錄結構)
  - [20-backend.md § 1 統一 Response 格式](../../Design-Base/20-backend.md#1-統一-response-格式)
  - [20-backend.md § 3 路由與 API 命名](../../Design-Base/20-backend.md#3-路由與-api-命名)
  - [20-backend.md § 8 Session 與 Transaction 規範](../../Design-Base/20-backend.md#8-session-與-transaction-規範)
  - [30-database.md § 1 必備欄位](../../Design-Base/30-database.md#1-必備欄位)
  - [50-openrouter.md](../../Design-Base/50-openrouter.md)（**本版本將異動 50-openrouter.md**，詳見文末「Design-Base 同步更新事項」）
  - [60-naming-env.md § 2 環境變數管理](../../Design-Base/60-naming-env.md#2-環境變數管理)
  - [70-auth.md](../../Design-Base/70-auth.md)（登入、Access + Refresh Token、admin 建立使用者）
  - [80-permission.md](../../Design-Base/80-permission.md)（**本版本將異動 80-permission.md § 1**，見文末）
  - [90-task-spec.md](../../Design-Base/90-task-spec.md)

## Definition of Done

- [ ] `backend/` 與 `frontend/` 子專案骨架建立並可 `docker compose up --build` 啟動
- [ ] `/api/docs` Swagger 可顯示本版本全部 API
- [ ] Flyway Migration V1 建立全部 Table 並通過啟動
- [ ] 初始 admin 由 Seed 依 `INITIAL_ADMIN_*` 建立並可登入
- [ ] 登入系統（§ 1）：login / refresh（rotation + 重用偵測）/ logout / me / 改密 / admin 建立使用者 / admin 重設密碼全部通過整合測試
- [ ] 組織結構（§ 2）：部門、專案 CRUD 完成；admin 可將使用者掛入部門
- [ ] OpenRouter Key 管理（§ 3）：CRUD + 加密儲存 + 啟停用完成；同一部門可有多把 Key（典型 3 把）
- [ ] SDK 代理端點（§ 4）：`POST /api/v1/model/openrouter/chat` 通過端對端測試（用 OpenRouter 低成本模型實打一次驗證）
- [ ] SDK Key 與 User Token 的建立 / 撤銷流程完成
- [ ] 用量紀錄（§ 5）：每次代理呼叫寫 `usage_logs`，含模型 / tokens / 耗時 / 成本 / 請求內容
- [ ] 儀錶板（§ 6）：部門 × 模型 × tokens / 金額 的彙總視圖完成（簡易版）
- [ ] `.env.example` 同步新增本版本所有變數；Coolify `docker-compose.yml` 同步
- [ ] 單元 + 整合測試覆蓋關鍵流程（refresh rotation、Token 解密、Key 選擇、usage 寫入）

---

## 功能 1：登入系統

完全依 [70-auth.md](../../Design-Base/70-auth.md) 實作。

### 1.1 Migration（Flyway）

```
migrations/
├── V1__init_auth.sql          # users + refresh_tokens
```

- `users` 表欄位：`pid`、`user_uid`、`account`、`username`、`password_hash`、`role`、`department_uid`（§ 2 建立後以 V2 ALTER 加入，見 § 2.2）、`failed_login_count`、`locked_until`、`password_changed_at`、必備欄位（`is_active` / `is_deleted` / `created_at` / `updated_at`）。
- `refresh_tokens` 表欄位依 [70-auth.md § 4.2](../../Design-Base/70-auth.md#42-refresh_tokens)。
- 建立 `set_updated_at()` function 與對應 trigger。
- Seed 初始 admin（以 `INITIAL_ADMIN_ACCOUNT` / `INITIAL_ADMIN_USERNAME` / `INITIAL_ADMIN_PASSWORD` 注入；密碼於 Seed 用 argon2id hash 寫入，**禁止**明文）。

### 1.2 端點

| Method | Path | 認證 | 說明 |
| --- | --- | --- | --- |
| POST | `/api/v1/auth/login` | 匿名 | 發 Access + Refresh |
| POST | `/api/v1/auth/refresh` | Refresh Cookie | Rotation + 重用偵測 |
| POST | `/api/v1/auth/logout` | Access / Refresh | 作廢 Refresh + 清 Cookie |
| GET  | `/api/v1/auth/me` | Access | 回 `Actor` |
| POST | `/api/v1/auth/password` | Access | 自行改密 |
| POST | `/api/v1/users` | Access + admin | admin 建立使用者 |
| GET  | `/api/v1/users` | Access + admin | 使用者列表（分頁 + 部門過濾） |
| GET  | `/api/v1/users/{user_uid}` | Access + admin | 查詢單一使用者 |
| PATCH | `/api/v1/users/{user_uid}` | Access + admin | 改 `username` / `role` / `department_uid` / `is_active` |
| POST | `/api/v1/users/{user_uid}/password/reset` | Access + admin | 重設密碼 |

### 1.3 交付檔案

- `backend/app/api/v1/auth.py`、`backend/app/api/v1/users.py`
- `backend/app/services/auth/`（login, refresh, password）
- `backend/app/services/user/`（create, list, update, reset_password）
- `backend/app/repositories/user.py`、`backend/app/repositories/refresh_token.py`
- `backend/app/schemas/auth.py`、`backend/app/schemas/user.py`
- `backend/app/core/security.py`（JWT 簽發 / 解碼、password hash）
- `backend/tests/api/test_auth.py`、`backend/tests/api/test_users.py`

---

## 功能 2：組織結構（部門、專案）

### 2.1 資料模型

- **部門（departments）**：頂層組織單位。典型範例：`資訊部`、`財務部`、`業務部`。
- **專案（projects）**：隸屬於部門；同一部門可有多個專案。
- **User ↔ 部門**：User 綁定於**一個**部門（本版本不做多部門）。
- **User ↔ 專案**：本版本 User 不直接綁專案；專案資訊由 SDK 呼叫時以 Token 中的 `project_code`（可選）附上，或由儀錶板查詢時以查詢參數指定。

> 「一個部門多個專案可共用同一把 Key」→ Key 掛**部門層**（§ 3），專案僅作稽核分類用途，不影響 Key 選擇。

### 2.2 Migration（V2）

```sql
CREATE TABLE departments (
    pid                 BIGSERIAL PRIMARY KEY,
    department_uid      UUID         NOT NULL UNIQUE,
    code                VARCHAR(32)  NOT NULL,              -- 部門代碼（例 T000）
    name                VARCHAR(128) NOT NULL,
    description         TEXT,
    is_active           BOOLEAN      NOT NULL DEFAULT TRUE,
    is_deleted          BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX uq_departments_code ON departments (lower(code)) WHERE is_deleted = FALSE;

CREATE TABLE projects (
    pid                 BIGSERIAL PRIMARY KEY,
    project_uid         UUID         NOT NULL UNIQUE,
    department_uid      UUID         NOT NULL REFERENCES departments(department_uid),
    code                VARCHAR(64)  NOT NULL,              -- 專案代碼（例 ORD-ANALYTICS）
    name                VARCHAR(128) NOT NULL,
    description         TEXT,
    is_active           BOOLEAN      NOT NULL DEFAULT TRUE,
    is_deleted          BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX uq_projects_dept_code ON projects (department_uid, lower(code)) WHERE is_deleted = FALSE;

-- users 擴充
ALTER TABLE users
    ADD COLUMN department_uid  UUID REFERENCES departments(department_uid),
    ADD COLUMN employee_id     VARCHAR(32),          -- 員工工號（§ 4 Token payload 使用）
    ADD COLUMN email           VARCHAR(255);          -- 公司 Mail（§ 4 Token payload 使用）
CREATE INDEX idx_users_department_uid ON users (department_uid) WHERE is_deleted = FALSE;
```

> 初始 admin Seed 所屬部門：於 V2 建立 `SYSTEM` 部門並把初始 admin 掛入。

### 2.3 端點

| Method | Path | 認證 | 說明 |
| --- | --- | --- | --- |
| GET  | `/api/v1/departments` | Access | 列表（分頁） |
| POST | `/api/v1/departments` | Access + admin | 建立 |
| GET  | `/api/v1/departments/{uid}` | Access | 查詢 |
| PATCH | `/api/v1/departments/{uid}` | Access + admin | 修改 |
| DELETE | `/api/v1/departments/{uid}` | Access + admin | 軟刪除（需無啟用的 Key / project / user） |
| GET  | `/api/v1/projects` | Access | 列表（可依 `department_uid` 過濾） |
| POST | `/api/v1/projects` | Access + admin | 建立 |
| GET  | `/api/v1/projects/{uid}` | Access | 查詢 |
| PATCH | `/api/v1/projects/{uid}` | Access + admin | 修改 |
| DELETE | `/api/v1/projects/{uid}` | Access + admin | 軟刪除 |

- 一般 `user` 角色**僅可讀取**自身部門下的 department / projects（service 層以 `actor.department_uid` 比對）。
- admin 可操作全部。

### 2.4 交付檔案

- `backend/app/api/v1/departments.py`、`backend/app/api/v1/projects.py`
- `backend/app/services/{department,project}/`、`backend/app/repositories/{department,project}.py`
- `backend/app/schemas/{department,project}.py`
- `backend/tests/api/test_departments.py`、`backend/tests/api/test_projects.py`

---

## 功能 3：OpenRouter Key 管理

### 3.1 資料模型

- **OpenRouter Key**：代表一把真實的 OpenRouter API Key（由 OpenRouter 官方核發）。
- 每把 Key **掛在某個部門**；該部門下所有專案皆可使用（無需額外授權）。
- 單一部門**典型 3 把**（多把的用意：平衡負載、Rate Limit 切換、成本歸戶）。
- Key 明文**必須**以 AES-256-GCM 加密存 DB；解密金鑰為 `ENCRYPTION_KEY`（32 bytes base64，注入環境變數）。
- Key 建立後僅於首次回應 Body 中回 prefix（末 4 碼），不再輸出明文。

### 3.2 Migration（V3）

```sql
CREATE TABLE openrouter_keys (
    pid                  BIGSERIAL PRIMARY KEY,
    openrouter_key_uid   UUID         NOT NULL UNIQUE,
    department_uid       UUID         NOT NULL REFERENCES departments(department_uid),
    name                 VARCHAR(128) NOT NULL,              -- 便於識別（例「OR-生產-主用」）
    key_ciphertext       BYTEA        NOT NULL,              -- AES-256-GCM nonce||cipher||tag
    key_prefix           VARCHAR(16)  NOT NULL,              -- Key 前 4 碼（例「sk-o」）
    key_last4            VARCHAR(8)   NOT NULL,              -- Key 末 4 碼
    is_active            BOOLEAN      NOT NULL DEFAULT TRUE,
    is_deleted           BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_openrouter_keys_dept ON openrouter_keys (department_uid) WHERE is_deleted = FALSE AND is_active = TRUE;
```

### 3.3 端點（全 admin）

| Method | Path | 說明 |
| --- | --- | --- |
| GET  | `/api/v1/openrouter-keys` | 列表（可依 `department_uid` 過濾，**不**回 ciphertext，僅 prefix + last4） |
| POST | `/api/v1/openrouter-keys` | 建立：body `{ department_uid, name, key }`，後端加密後存；Response 只回 last4 |
| GET  | `/api/v1/openrouter-keys/{uid}` | 查詢（不回明文） |
| PATCH | `/api/v1/openrouter-keys/{uid}` | 僅可改 `name` / `is_active`；**禁止**改 `key` |
| DELETE | `/api/v1/openrouter-keys/{uid}` | 軟刪除 |

### 3.4 Key 選擇策略（供 § 4 使用）

- 給定 `department_uid`，挑出 `is_active=TRUE AND is_deleted=FALSE` 的全部 Key。
- 本版本採 **random choice**（Python `random.choice`）以平均分散負載。
- **僅**在所有 Key 均 401（已失效）時才連續重試下一把；單次呼叫**最多**嘗試 N 把（N = 該部門 active key 數，上限 5）。
- 超過嘗試次數仍失敗 → 回 502 `openrouter_unavailable`，並於 Log 標記可疑 Key。

### 3.5 交付檔案

- `backend/app/api/v1/openrouter_keys.py`
- `backend/app/services/openrouter_key/`
- `backend/app/repositories/openrouter_key.py`
- `backend/app/core/crypto.py`（AES-256-GCM helper：`encrypt(plaintext) / decrypt(ciphertext)`）
- `backend/app/schemas/openrouter_key.py`
- `backend/tests/api/test_openrouter_keys.py`、`backend/tests/core/test_crypto.py`

---

## 功能 4：SDK 代理端點

### 4.1 認證機制

SDK 呼叫代理端點時 Header **必須**同時帶兩個值：

| Header | 作用 | 格式 |
| --- | --- | --- |
| `X-SDK-Key` | 識別呼叫方所屬部門，驗證 SDK 本身可用性 | 平台發行的明文字串（見 § 4.2） |
| `X-User-Token` | 識別呼叫方個別使用者（員工） | AES-256-GCM 加密後 base64url 字串 |

- **兩者缺一不可**；缺漏或解密失敗一律 401 `unauthorized`，**禁止**分別揭露哪一項失敗。
- `X-SDK-Key` 所屬部門**必須**與 `X-User-Token` 解密後的 `department_uid` **一致**；不一致視同偽造，401。

### 4.2 SDK Key

- 一個部門可核發多把 SDK Key，便於輪替與分裝。
- 存於 `sdk_api_keys` 表，DB 僅存 `argon2id` hash，明文僅於建立時回應一次。
- 呼叫端於 Header 以 `X-SDK-Key: <明文>` 送出。

**Migration（V4）：**

```sql
CREATE TABLE sdk_api_keys (
    pid                  BIGSERIAL PRIMARY KEY,
    sdk_api_key_uid      UUID         NOT NULL UNIQUE,
    department_uid       UUID         NOT NULL REFERENCES departments(department_uid),
    name                 VARCHAR(128) NOT NULL,
    key_hash             VARCHAR(255) NOT NULL,        -- argon2id hash
    key_prefix           VARCHAR(16)  NOT NULL,        -- 公開 prefix（例「ordsk_ab12」）
    is_active            BOOLEAN      NOT NULL DEFAULT TRUE,
    is_deleted           BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_sdk_api_keys_dept   ON sdk_api_keys (department_uid) WHERE is_deleted = FALSE;
CREATE INDEX idx_sdk_api_keys_prefix ON sdk_api_keys (key_prefix)     WHERE is_deleted = FALSE;
```

- SDK Key 明文格式：`ordsk_<12 字 hex>_<32 字 base62 secret>`；DB 以 prefix 作候選查詢、再以 argon2 比對 secret。

### 4.3 User Token（加密）

- Token payload（固定欄位，值取自 `users` + `departments`）：

```json
{
  "user_uid":       "<uuid>",
  "department_uid": "<uuid>",
  "department_code":"T000",
  "employee_id":    "00063",
  "email":          "user@df-recycle.com",
  "issued_at":      "2026-04-17T10:00:00Z"
}
```

- 加密：AES-256-GCM，金鑰 = `ENCRYPTION_KEY`，nonce 12 bytes 隨機，輸出為 `base64url(nonce || ciphertext || tag)`。
- 由 admin 於後台以 `POST /api/v1/users/{user_uid}/tokens` 產生並**一次性**顯示給 admin；admin 帶外交付使用者設定於 SDK 環境變數。
- 不落地 DB（因 payload 為固定值，可由 users 表重建）；但**必須**提供 `POST /api/v1/users/{user_uid}/tokens/revoke` 寫入 `user_tokens_revocations`（見 V5），驗證時比對黑名單。

**Migration（V5）：**

```sql
CREATE TABLE user_tokens_revocations (
    pid                               BIGSERIAL PRIMARY KEY,
    user_tokens_revocation_uid        UUID         NOT NULL UNIQUE,
    user_uid                          UUID         NOT NULL REFERENCES users(user_uid),
    revoked_issued_at                 TIMESTAMPTZ  NOT NULL,   -- 撤銷「此時間之前發的」全部 Token
    revoked_at                        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    reason                            VARCHAR(255),
    is_active                         BOOLEAN      NOT NULL DEFAULT TRUE,
    is_deleted                        BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at                        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at                        TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_user_tokens_revocations_user ON user_tokens_revocations (user_uid) WHERE is_deleted = FALSE;
```

- 驗證時：`token.issued_at >= user.latest_revocation.revoked_issued_at`（若有）；否則 401。

### 4.4 代理端點

| Method | Path | 說明 |
| --- | --- | --- |
| POST | `/api/v1/model/openrouter/chat` | 向 OpenRouter 發一次 chat completion 並同步等 Response |

**Request Body（簡化版，V1）：**

```json
{
  "model":   "anthropic/claude-3.5-sonnet",
  "text":    "幫我把這段整理成 bullet points：...",
  "images":  [
    "https://example.com/chart.png",
    "data:image/png;base64,iVBORw0..."
  ]
}
```

- `model`：必填，字串；**必須**在全域模型白名單內（可由環境變數 `ALLOWED_MODELS` 列舉；空代表不限）。
- `text`：選填，字串。
- `images`：選填，陣列，元素為 URL 或 `data:image/*;base64,*`。
- **預留** `videos`：V1 **不實作**；若送出回 400 `feature_not_supported`。

**後端改寫為 OpenRouter 官方 chat/completions 格式：**

```json
{
  "model": "anthropic/claude-3.5-sonnet",
  "messages": [
    { "role": "user", "content": [
      { "type": "text",      "text":     "..." },
      { "type": "image_url", "image_url":{ "url": "https://..." } }
    ]}
  ]
}
```

**Response**：回傳 OpenRouter 原始 `{ id, choices, usage, ... }`（去除任何含內部識別的欄位）；若失敗則回 `ApiResponse` 失敗格式（§ 錯誤處理對照）。

### 4.5 完整呼叫流程

```
SDK ─▶ POST /api/v1/model/openrouter/chat
       Headers: X-SDK-Key, X-User-Token
       Body:    { model, text, images }
         │
         ▼
   1. 解析 X-SDK-Key → 比對 sdk_api_keys → 得 department_uid (SDK)
   2. 解密 X-User-Token → 得 payload → 驗 revocation → 取 department_uid (User)
   3. 若 SDK.department_uid != User.department_uid → 401
   4. 驗 model 白名單；若超出 → 403 model_forbidden
   5. 改寫 Request Body 成 OpenRouter chat/completions 格式
   6. 挑一把該部門 active OpenRouter Key（§ 3.4）
   7. httpx 呼叫 OpenRouter；錯誤則依 § 3.4 嘗試下一把
   8. 回 200 Response
   9. 寫 usage_logs（含 model、tokens、cost、latency、request_content）
```

### 4.6 端點補充（SDK Key / User Token 管理）

| Method | Path | 認證 | 說明 |
| --- | --- | --- | --- |
| GET  | `/api/v1/sdk-keys` | admin | 列表（不回明文） |
| POST | `/api/v1/sdk-keys` | admin | 建立；Response 一次性回明文 |
| PATCH | `/api/v1/sdk-keys/{uid}` | admin | 改 `name` / `is_active` |
| DELETE | `/api/v1/sdk-keys/{uid}` | admin | 軟刪除 |
| POST | `/api/v1/users/{user_uid}/tokens` | admin | 產生 User Token；Response 一次性回加密字串 |
| POST | `/api/v1/users/{user_uid}/tokens/revoke` | admin | 撤銷該 user 於此時間之前所有 Token |

### 4.7 交付檔案

- `backend/app/api/v1/model_openrouter.py`（代理端點）
- `backend/app/api/v1/sdk_keys.py`、`backend/app/api/v1/user_tokens.py`
- `backend/app/services/proxy/`（orchestration、改寫、key selection、重試）
- `backend/app/clients/openrouter/`（httpx wrapper、OpenRouterClient）
- `backend/app/core/sdk_auth.py`（X-SDK-Key / X-User-Token 解析與驗證 Dependency）
- `backend/app/schemas/model.py`、`backend/app/schemas/sdk_key.py`、`backend/app/schemas/user_token.py`
- `backend/tests/api/test_model_openrouter.py`（含「SDK Key 與 Token 部門不一致」「解密失敗」「所有 Key 都失效」等案例）

---

## 功能 5：用量紀錄（Usage Log）

### 5.1 Migration（V6）

```sql
CREATE TABLE usage_logs (
    pid                       BIGSERIAL PRIMARY KEY,
    usage_log_uid             UUID         NOT NULL UNIQUE,
    user_uid                  UUID         REFERENCES users(user_uid),
    department_uid            UUID         NOT NULL REFERENCES departments(department_uid),
    openrouter_key_uid        UUID         REFERENCES openrouter_keys(openrouter_key_uid),
    model                     VARCHAR(128) NOT NULL,
    prompt_tokens             INT          NOT NULL DEFAULT 0,
    completion_tokens         INT          NOT NULL DEFAULT 0,
    total_tokens              INT          NOT NULL DEFAULT 0,
    cost_usd                  NUMERIC(12,6) NOT NULL DEFAULT 0,
    latency_ms                INT          NOT NULL DEFAULT 0,
    status                    VARCHAR(16)  NOT NULL,        -- 'success' | 'error'
    error_code                VARCHAR(64),
    request_content           JSONB,                        -- 原始 request body（text、images URL）
    response_summary          JSONB,                        -- 裁切後 response（首段文字 + usage）
    openrouter_generation_id  VARCHAR(64),
    is_active                 BOOLEAN      NOT NULL DEFAULT TRUE,
    is_deleted                BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at                TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at                TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_usage_logs_dept_time  ON usage_logs (department_uid, created_at DESC);
CREATE INDEX idx_usage_logs_user_time  ON usage_logs (user_uid, created_at DESC);
CREATE INDEX idx_usage_logs_model_time ON usage_logs (model, created_at DESC);
```

### 5.2 寫入規則

- **每次**代理呼叫（含失敗）**必須**寫一筆；即使驗證失敗（SDK Key / Token 無效），也**應**寫一筆 `status='error'` 記錄（`user_uid`、`department_uid` 可能為 NULL）。
- `request_content` 儲存**原始** request body（`model` + `text` + `images` URL 或 base64 指標，**不**儲存 base64 本體以免暴增資料量；base64 影像以 sha256 指紋代替）。
- `response_summary` 儲存 response 首段文字（≤ 500 字）+ `usage`；完整 response **不**落地。
- 寫入**必須**於 response 回給 Client **之後**執行（透過 FastAPI `BackgroundTasks` 或 `asyncio.create_task`），避免拖慢呼叫。

### 5.3 查詢端點

| Method | Path | 認證 | 說明 |
| --- | --- | --- | --- |
| GET | `/api/v1/usage-logs` | Access | 列表（admin 看全部；user 僅看自身部門）；filters: `department_uid` / `user_uid` / `model` / `from` / `to` / `status` |
| GET | `/api/v1/usage-logs/{uid}` | Access | 單筆；同上可見性規則 |

### 5.4 交付檔案

- `backend/app/api/v1/usage_logs.py`
- `backend/app/services/usage/`、`backend/app/repositories/usage_log.py`
- `backend/app/schemas/usage_log.py`
- `backend/tests/api/test_usage_logs.py`

---

## 功能 6：後台監控與儀錶板（簡易）

### 6.1 彙總端點

| Method | Path | 認證 | 說明 |
| --- | --- | --- | --- |
| GET | `/api/v1/stats/overview` | Access | 總覽：時間範圍內的總請求數、總 tokens、總金額 |
| GET | `/api/v1/stats/by-department` | Access | 依部門彙總（admin 全部；user 僅自部門） |
| GET | `/api/v1/stats/by-model` | Access | 依模型彙總（交叉部門可選） |
| GET | `/api/v1/stats/timeseries` | Access | 時序：每日 / 每小時 的 tokens & 成本 |

Query params：`from`、`to`（`TIMESTAMPTZ`）、`department_uid`、`granularity`（`hour` / `day`）。

### 6.2 前端頁面

- `/dashboard` 首頁：
  - 3 張 KPI 卡：總請求、總 tokens、總金額（本月）
  - 長條圖：部門 × 總 tokens（Top N）
  - 堆疊柱：模型 × 總 tokens
  - 折線圖：日用量時序
- 使用 `recharts` 或 `chart.js`；**不得**引入重量級商業儀錶板庫。

### 6.3 交付檔案

- `backend/app/api/v1/stats.py`、`backend/app/services/stats/`
- `frontend/src/app/(main)/dashboard/page.tsx`
- `frontend/src/components/feature/stats/*.tsx`

---

## 錯誤處理對照表

| 情境 | HTTP | `detail` |
| --- | --- | --- |
| 未登入 / Access 無效 | 401 | `unauthorized` |
| Refresh 重用偵測 | 401 | `refresh_reuse_detected` |
| 帳密錯誤 | 401 | `invalid_credentials` |
| 帳號鎖定 | 423 | `account_locked` |
| 權限不足（非 admin） | 403 | `forbidden` |
| User 存取他部門資源 | 403 | `forbidden` |
| SDK Key 無效 / Token 解密失敗 / 部門不一致 | 401 | `unauthorized`（**統一**回應） |
| User Token 已撤銷 | 401 | `unauthorized` |
| 模型不在白名單 | 403 | `model_forbidden` |
| 模型不存在（OpenRouter 回 404） | 404 | `model_not_found` |
| 本版本不支援影片輸入 | 400 | `feature_not_supported` |
| 欄位驗證失敗 | 400 | `invalid_input` |
| 部門 / 專案代碼重複 | 409 | `code_conflict` |
| OpenRouter Rate Limit | 429 | `rate_limited` |
| 所有 OpenRouter Key 皆失效 | 502 | `openrouter_unavailable` |
| 未預期錯誤 | 500 | `操作失敗` |

---

## 環境變數新增（本版本）

同步於 `.env.example`、[40-deployment.md § 4](../../Design-Base/40-deployment.md#4-docker-composeyml-範本)、[60-naming-env.md § 2.1](../../Design-Base/60-naming-env.md#21-本專案環境變數分區)：

```dotenv
# --- OpenRouter ---
OPENROUTER_API_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_API_TIMEOUT=60

# --- Model whitelist ---
ALLOWED_MODELS=                 # 以逗號分隔；空代表不限

# --- SDK / Encryption ---
ENCRYPTION_KEY=                 # 32 bytes base64（AES-256-GCM）
```

---

## 交付物清單

**後端：** `backend/app/{api/v1,services,clients/openrouter,repositories,schemas,core,models}/*`、`backend/tests/*`、`backend/Dockerfile`、`backend/pyproject.toml`。

**前端：** `frontend/src/app/{(auth)/login,(main)/{dashboard,departments,projects,users,openrouter-keys,sdk-keys,usage-logs}}/page.tsx`、`frontend/src/lib/api/*`、`frontend/src/store/*`、`frontend/Dockerfile`、`frontend/package.json`。

**Migration：** `migrations/V1__init_auth.sql`、`V2__organization.sql`、`V3__openrouter_keys.sql`、`V4__sdk_api_keys.sql`、`V5__user_tokens_revocations.sql`、`V6__usage_logs.sql`。

**環境：** `.env.example`、`docker-compose.yml`、`docker-compose.dev.yml`。

---

## Design-Base 同步更新事項

本 Task 導入的新設計與 Design-Base 現狀不一致；**建立此 Task 前**（或作為 Task 第一個子任務）**必須**先更新下列章節，保持規範為單一真相來源：

1. **[50-openrouter.md § 3 本地金鑰](../../Design-Base/50-openrouter.md#3-本地金鑰local-api-key)** → 以本 Task § 4.1–4.3 的 **SDK Key + 加密 User Token** 取代 `ord_*` 設計。
2. **[50-openrouter.md § 5 代理端點規範](../../Design-Base/50-openrouter.md#5-代理端點規範)** → 路徑由 `/api/v1/proxy/<openrouter-path>` 改為 `/api/v1/model/openrouter/<action>`；Request 採簡化 schema（§ 4.4）而非 OpenAI 相容 passthrough。
3. **[80-permission.md § 1 主體類型](../../Design-Base/80-permission.md#1-主體類型)** → 代理端主體由「本地金鑰 `ord_*`」改為「SDK Key + User Token 雙因子」，說明部門一致性檢查。
4. **[30-database.md](../../Design-Base/30-database.md)** 無直接衝突，但 § 6 歷史遺留補救流程**應在實作前重讀**（本專案無歷史 V，但規範要求維持）。

---

## 前置檢查（依 [90-task-spec.md § 3](../../Design-Base/90-task-spec.md#3-前置檢查ai-產-task-前必做)）

- [x] 閱讀全部 Design-Base 檔案
- [x] 對齊章節已明列具體錨點
- [x] 與 Design-Base 衝突：已於「Design-Base 同步更新事項」列出，**必須**先更新
- [x] `.env.example` 新增變數已列出
- [x] Migration V1–V6 已規劃
- [x] OpenRouter 整合對齊 [50-openrouter.md](../../Design-Base/50-openrouter.md)（含本 Task 要修訂的章節）

---

## 自我檢核清單（依 [90-task-spec.md § 6](../../Design-Base/90-task-spec.md#6-檢核清單)）

- [x] 文件結構：版本資訊 / DoD / 功能設計 / 交付物清單 齊備
- [x] 前置檢查已完成
- [x] Response Schema 以 Pydantic 明確定義（實作階段產出）
- [x] API 路徑符合 `/api/v1/*` + kebab-case 複數；代理路徑採 `/api/v1/model/openrouter/*`
- [x] 敏感欄位過濾表：OpenRouter Key 明文 / User Token 明文 / SDK Key 明文 均僅於建立時一次性回應
- [x] 錯誤處理對照表已附
- [x] 代理端說明 `usage_logs` 寫入；管理端異動（建使用者 / 重設密碼 / Key CRUD）寫稽核 Log（對齊 [80-permission.md § 9](../../Design-Base/80-permission.md#9-稽核-log)）
- [x] 未觸犯 [90-task-spec.md § 5](../../Design-Base/90-task-spec.md#5-禁止事項) 禁止事項
