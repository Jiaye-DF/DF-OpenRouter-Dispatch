# 70 · 認證（本地登入 · Access + Refresh Token）

本文件定義本平台管理端的認證設計：採 **本地登入**，涵蓋**登入、登出、修改密碼、管理員建立使用者 / 重設密碼**流程；Token 採 **Access Token + Refresh Token 雙 Token + Rotation** 機制。

> **本平台為 admin 後台管理系統**，**禁止**任何自助流程（註冊 / 忘記密碼 / Email 驗證）。所有帳號生命週期由 admin 於後台操作。

> 代理端（`/api/v1/model/openrouter/*`）**不**套用本文件，改以 **SDK Key + 加密 User Token** 雙因子認證，詳見 [50-openrouter.md § 3](./50-openrouter.md#3-本地認證sdk-key--user-token-雙因子) 與 [80-permission.md § 1](./80-permission.md#1-主體類型)。

## 1. 核心原則

- **admin-only 帳號治理**：**無**自助註冊、**無**忘記密碼、**無**公開 `/register` 端點；使用者由 admin 於後台建立並發放首次密碼。
- **最小欄位**：`account`（登入帳號）+ `username`（顯示名稱）+ `password`。**不**使用 Email、**不**做 Email 驗證、**不**寄任何信。
- **雙 Token**：
  - **Access Token**：短期（預設 15 分鐘）、JWT、用於 API 驗證。
  - **Refresh Token**：長期（預設 7 天）、隨機 opaque 字串、僅存於 DB（hash），**僅**用於換發新 Access + Refresh。
- **Rotation**：每次 `/refresh` 一次性換新，舊 Refresh Token **立即作廢**，新 Refresh Token 繼承同一 `family_uid`。
- **重用偵測（Reuse Detection）**：若偵測到已作廢的 Refresh Token 被再次使用，**必須**視為遭竊並**立即作廢整個 family**（強制該 Session 所有裝置重登）。
- **雙 Cookie 分 Path**：Access Cookie 掛 `/`，Refresh Cookie 僅掛 `/api/v1/auth`，**禁止**使 Refresh Token 隨一般 API 請求外洩。
- **密碼一律 hash**：argon2id 或 bcrypt（cost ≥ 12）；**禁止**明文存放或寫 Log。

## 2. 欄位語義

| 欄位 | 用途 | 要求 |
| --- | --- | --- |
| `account` | 登入用帳號（唯一識別） | 4–64 字元、`[a-zA-Z0-9._-]`、唯一、**登入輸入用** |
| `username` | 顯示名稱（畫面呈現用） | 1–128 字元、可含中文、**可重複** |
| `password` | 密碼 | 10–128 字元，包含大小寫英數符中**至少三類** |

## 3. 環境變數

於 `.env.example` 登記（對齊 [60-naming-env.md § 2.1](./60-naming-env.md#21-本專案環境變數分區)）：

```dotenv
# --- Auth / Security ---
JWT_SECRET=
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRES_MINUTES=15
REFRESH_TOKEN_EXPIRES_DAYS=7
ACCESS_COOKIE_NAME=access_token
REFRESH_COOKIE_NAME=refresh_token
ENCRYPTION_KEY=
CORS_ORIGINS=

# --- Auth / Admin Bootstrap ---
INITIAL_ADMIN_ACCOUNT=
INITIAL_ADMIN_USERNAME=
INITIAL_ADMIN_PASSWORD=
```

- `JWT_SECRET`、`INITIAL_ADMIN_PASSWORD` **禁止**出現於前端、Log、Commit。
- `INITIAL_ADMIN_*` 三變數由 Migration Seed 建立第一位 admin，之後的使用者**必須**透過 admin 後台建立。

## 4. 資料表

### 4.1 `users`

對齊 [30-database.md § 1](./30-database.md#1-必備欄位)：

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| `account` | `VARCHAR(64) NOT NULL` | 登入帳號，唯一 |
| `username` | `VARCHAR(128) NOT NULL` | 顯示名稱，可重複 |
| `password_hash` | `VARCHAR(255) NOT NULL` | argon2id / bcrypt |
| `role` | `VARCHAR(16) NOT NULL` | `'admin'` \| `'user'`（見 [80-permission.md § 2](./80-permission.md#2-角色定義)） |
| `failed_login_count` | `INT NOT NULL DEFAULT 0` | 連續失敗次數 |
| `locked_until` | `TIMESTAMPTZ` | 鎖定至該時間；`NULL` 代表未鎖 |
| `password_changed_at` | `TIMESTAMPTZ NOT NULL DEFAULT NOW()` | 密碼變更時間（下次更新時刷新） |

```sql
CREATE UNIQUE INDEX uq_users_account ON users (lower(account)) WHERE is_deleted = FALSE;
```

### 4.2 `refresh_tokens`

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| `refresh_token_uid` | `UUID NOT NULL UNIQUE` | 對外識別（同時作為 Cookie 內的公開部分） |
| `user_uid` | `UUID NOT NULL` | 外鍵 → `users(user_uid)` |
| `family_uid` | `UUID NOT NULL` | Rotation 鏈共用 ID，供重用偵測時一併作廢 |
| `token_hash` | `VARCHAR(255) NOT NULL` | Refresh Token secret 部分的 sha256 hex |
| `issued_at` | `TIMESTAMPTZ NOT NULL DEFAULT NOW()` | |
| `expires_at` | `TIMESTAMPTZ NOT NULL` | |
| `revoked_at` | `TIMESTAMPTZ` | 非 NULL 代表已作廢 |
| `replaced_by_uid` | `UUID` | 被 rotation 換掉時指向新的 token；用於重用偵測 |
| `user_agent` | `VARCHAR(512)` | 核發時的 UA |
| `ip` | `INET` | 核發時的 IP |

```sql
CREATE INDEX idx_refresh_tokens_user_uid ON refresh_tokens (user_uid) WHERE is_deleted = FALSE;
CREATE INDEX idx_refresh_tokens_family   ON refresh_tokens (family_uid) WHERE is_deleted = FALSE;
```

## 5. 後端端點

集中於 `backend/app/api/v1/auth/` 與 `backend/app/api/v1/users/`：

| Method | Path | 認證 | 功能 |
| --- | --- | --- | --- |
| POST | `/api/v1/auth/login` | 匿名 | 登入，發 Access + Refresh |
| POST | `/api/v1/auth/refresh` | Refresh Cookie | 以 Refresh 換新 Access + Refresh（rotation） |
| POST | `/api/v1/auth/logout` | Access or Refresh | 作廢當前 Refresh 並清 Cookie |
| GET  | `/api/v1/auth/me` | Access | 回傳 `Actor` |
| POST | `/api/v1/auth/password` | Access | 自行變更密碼（需舊密碼） |
| POST | `/api/v1/users` | Access + admin | admin 建立使用者（帶首次密碼） |
| POST | `/api/v1/users/{user_uid}/password/reset` | Access + admin | admin 重設他人密碼 |

**禁用端點：** 公開的 `/register`、`/password/forgot`、`/password/reset`（非 admin 版）、`/email/*` **一律不實作**；若誤打這些路徑，FastAPI 預設回 404。

## 6. 管理員建立使用者

```
POST /api/v1/users   { account, username, password, role }
        │
        ▼
   後端（需 Access + admin）：
     1. require_admin
     2. 格式驗證：
          - account: 4–64 字元、符合 [a-zA-Z0-9._-]
          - username: 1–128 字元
          - password: 強度規則（§ 11）
          - role: 'admin' | 'user'
     3. 檢查 account 唯一性（lower(account) 比對）
          已存在 → 400 account_taken
     4. 建立 users（password_hash、role）
     5. 寫稽核 Log（action="create_user"，target=new_user_uid）
     6. 200 { success, data: { user_uid, account, username, role } }
        - 首次密碼**僅一次性**於 Response 中回傳給 admin
        - admin 以**帶外**管道（口頭 / 即時通訊）轉交該使用者
        - **禁止**透過 Email / 系統通知送出明文密碼
```

**規則：**

- 建立使用者**為** admin 專屬功能，**禁止**對一般使用者開放。
- `account_taken` 直接回 400 是可接受的（admin 後台場景，無帳號列舉風險）。
- 使用者首次登入**應**被引導至「修改密碼」頁（可透過 `must_change_password` 欄位實作，屬後續增強，非本章必備）。

## 7. 登入流程

```
POST /api/v1/auth/login
   { account, password }
        │
        ▼
   後端：
     1. users.find_by_account(lower(account))
     2. 檢查 locked_until → 尚在鎖定期間 → 423 account_locked
     3. 比對 password_hash
        失敗 → failed_login_count += 1；達 5 次 → locked_until = now + 15 min
              → 401 invalid_credentials
     4. 成功 → failed_login_count=0、locked_until=NULL
     5. 發 Access Token（JWT）+ Refresh Token（opaque 字串）
          - 建立 refresh_tokens：family_uid = new uuid
     6. Set-Cookie access_token / refresh_token（見 § 13）
        │
        ▼
   200 { success, data: Actor, detail: "success" }
```

### Access Token 結構（JWT）

```json
{
  "sub": "<user_uid>",
  "jti": "<uuid>",
  "type": "access",
  "exp": 1712345678
}
```

### Refresh Token 結構（Cookie 值格式）

`<refresh_token_uid>.<secret>`

- `refresh_token_uid`：公開 UUID，用於 DB 查找。
- `secret`：32 bytes URL-safe base64 隨機字串；DB 只存 `sha256(secret)`。
- 以 `.` 分隔；比對時先以 UID 查 row，再以 hash 比對 secret（**必須** `hmac.compare_digest`）。

## 8. Refresh 流程（Rotation + 重用偵測）

```
POST /api/v1/auth/refresh   （Cookie: refresh_token=<uid>.<secret>）
        │
        ▼
   後端：
     1. 解析 Cookie → (uid, secret)
     2. DB 查 refresh_tokens where refresh_token_uid=uid
          未找到 → 401 unauthorized
     3. 比對 token_hash 與 sha256(secret)（constant-time）
          不符 → 401 unauthorized
     4. 檢查 expires_at / revoked_at / replaced_by_uid
          ├ 已過期 → 401 unauthorized
          ├ revoked_at IS NOT NULL：
          │   └ 若 replaced_by_uid IS NOT NULL（已被 rotation 用掉，又再次出現）
          │      → **重用偵測**：revoke 整個 family_uid 的全部 tokens
          │      → 401 refresh_reuse_detected
          └ 合法 → 進入 rotation
     5. Rotation（單一 DB transaction）：
          - 產生 new_refresh_token_uid + new_secret
          - 建立新 row（family_uid = 原 family_uid）
          - 舊 row: revoked_at=NOW()、replaced_by_uid=new_uid
     6. 發新 Access Token（JWT，新 jti）
     7. Set-Cookie 覆寫 access_token / refresh_token
        │
        ▼
   200 { success, detail: "success" }
```

**規則：**

- Refresh 操作**必須**包在單一 DB transaction；rotation 舊 row 更新與新 row 建立**必須**原子完成。
- 重用偵測觸發時**必須** log 嚴重事件（含 IP、UA、family_uid），並將整個 `family_uid` 下的 refresh tokens 全部 `revoked_at=NOW()`（含尚未過期的）。
- `/refresh` 端點**必須**允許未帶 Access Token 呼叫（Access 已過期）；**只**驗證 Refresh Token。
- Frontend 於收到 401 時**應**自動呼叫 `/refresh` 一次後重試原請求；`/refresh` 也回 401 時才導向 `/login`。

## 9. 登出流程

```
POST /api/v1/auth/logout   （Cookie: refresh_token=<uid>.<secret>）
        │
        ▼
   後端：
     1. 若帶 Refresh：以 uid 查 row，revoked_at=NOW()（即使不符也 best-effort，**不**回報原因）
     2. Set-Cookie access_token=; Max-Age=0
        Set-Cookie refresh_token=; Max-Age=0; Path=/api/v1/auth
        │
        ▼
   200 { success, detail: "success" }
```

**選配：「登出所有裝置」** — 提供 `POST /api/v1/auth/logout-all`，將當前 user 全部未過期 refresh tokens `revoked_at=NOW()`。

## 10. 修改密碼 / 管理員重設密碼

### 10.1 自行修改（已登入）

```
POST /api/v1/auth/password   { old_password, new_password }
        │
        ▼
   後端（需 Access）：
     1. 比對 old_password → 不符 → 400 invalid_credentials
     2. 驗證 new_password 強度（§ 11）；與舊 hash 相同 → 400 password_reused
     3. Transaction：
          - users.password_hash = hash(new_password)
          - users.password_changed_at = NOW()
          - 作廢該使用者全部 refresh_tokens（含當前 Session）
     4. 200；前端**必須**引導使用者重新登入
```

### 10.2 管理員重設他人密碼

```
POST /api/v1/users/{user_uid}/password/reset   { new_password }
        │
        ▼
   後端（需 Access + admin）：
     1. require_admin
     2. 驗證 new_password 強度（§ 11）
     3. Transaction：
          - users[user_uid].password_hash = hash(new_password)
          - users.password_changed_at = NOW()
          - users.failed_login_count = 0；locked_until = NULL
          - 作廢該 user 全部 refresh_tokens
          - 寫稽核 Log（action="admin_reset_password"，target=user_uid）
     4. 200 { success }；告知 admin 將新密碼以**帶外**管道交付使用者
```

**規則：**

- admin 重設密碼**禁止**透過 Email 或系統訊息回傳新密碼（無此管道，且安全考量）；新密碼應由 admin 於**頁面彈窗一次性顯示**並由 admin 口頭 / 即時通訊告知使用者。
- 若未來新增使用者首次登入強制改密欄位（`must_change_password`），admin 重設後**應**一併設為 `true`。

## 11. 密碼規則

- 最短 10 字元；最長 128 字元。
- 必須包含下列四類中的**至少三類**：小寫字母、大寫字母、數字、符號。
- 新密碼**不得**與最近一組舊密碼相同（比對 hash）。
- 密碼 hash 演算法**必須** `argon2id`（推薦）或 `bcrypt`（cost ≥ 12）。

## 12. 驗證流程（每次受保護請求）

```
Request ─▶ Cookie: access_token=<JWT>
              │
              ▼
       require_user Dependency
              │  1. 解碼 + 驗簽（HS256 + JWT_SECRET）
              │  2. 檢查 exp → 過期回 401（前端應接 /refresh）
              │  3. 檢查 type=="access"（防 refresh token 被當 access 用）
              │  4. 從 DB 讀 user（role 以 DB 為準）
              │  5. 若 user.password_changed_at > access.iat → 回 401（密碼已被改，舊 Access 失效）
              │  6. 組 Actor 注入 handler
              ▼
           Handler
```

- **禁止**於 Access JWT Claim 中固化 role。
- Access Token 不進失效清單（太短壽）；強制下線以作廢 Refresh Token + 提升 `password_changed_at` 達成。

## 13. Cookie 規範

| 項目 | Access Cookie | Refresh Cookie |
| --- | --- | --- |
| 名稱 | `ACCESS_COOKIE_NAME`（預設 `access_token`） | `REFRESH_COOKIE_NAME`（預設 `refresh_token`） |
| 內容 | Access JWT | `<uid>.<secret>` |
| `HttpOnly` | 強制開啟 | 強制開啟 |
| `Secure` | `prod` / `staging` 強制；`dev` 可關 | 同左 |
| `SameSite` | `Lax` | **`Strict`** |
| `Path` | `/` | `/api/v1/auth` |
| `Max-Age` | `ACCESS_TOKEN_EXPIRES_MINUTES * 60` | `REFRESH_TOKEN_EXPIRES_DAYS * 86400` |

- Refresh Cookie 的 **`Path` 限制為 `/api/v1/auth`**，確保只會隨 `/refresh` 與 `/logout` 上行。
- Logout 清除 Refresh Cookie 時**必須**指定相同 Path，否則瀏覽器不會清掉。

## 14. 前端頁面

| 頁面 | 可見性 | 說明 |
| --- | --- | --- |
| `/login` | 匿名 | 本地登入表單（`account` + `password`）；錯誤固定 `帳號或密碼錯誤` |
| `/settings/password` | 已登入 | 變更自身密碼（需舊密碼） |
| `/admin/users` | admin | 使用者列表 / 建立 / 停用 / 重設密碼 |

- **禁止**存在 `/register`、`/forgot-password`、`/reset-password` 等公開頁面；即使有人手動造訪也應 404。
- 前端**禁止**保存或讀取 Cookie 內容（HttpOnly 即可）。
- 任何 API 回 401 時，前端**應**先嘗試 `POST /api/v1/auth/refresh` 一次，失敗再導 `/login`。
- 避免「瞬間雙重 refresh」：前端**應**以單一 in-flight Promise 去重。

## 15. 錯誤處理對照

| 情境 | HTTP | `detail` |
| --- | --- | --- |
| 無 Access / Access 無效 / 過期 | 401 | `unauthorized` |
| Refresh 無效 / 過期 | 401 | `unauthorized` |
| Refresh **重用偵測** | 401 | `refresh_reuse_detected`（Log 嚴重事件） |
| 帳密錯誤 | 401 | `invalid_credentials` |
| 帳號被鎖定 | 423 | `account_locked` |
| 建立 / 重設：欄位格式不合 | 400 | `invalid_input`（明列欄位） |
| 建立 / 重設：密碼強度不足 | 400 | `weak_password` |
| 建立使用者：account 已存在 | 400 | `account_taken` |
| 修改密碼：舊密碼錯誤 | 400 | `invalid_credentials` |
| 修改密碼：與舊密碼相同 | 400 | `password_reused` |
| 管理員操作：target 不存在 | 404 | `not_found` |
| 管理員操作：非 admin | 403 | `forbidden` |
| 打到 `/register` / `/forgot-password` 等未定義路徑 | 404 | `not_found` |

## 16. Rate Limit

**必須**對下列端點套用 rate limit（Redis slide window 或等效實作）：

| 端點 | 維度 | 限制 |
| --- | --- | --- |
| `POST /auth/login` | `account` + IP | 10 次 / 5 分鐘（搭配帳號鎖定） |
| `POST /auth/refresh` | `refresh_token_uid` | 60 次 / 分鐘（防爆衝） |
| `POST /auth/password` | user_uid | 10 次 / 小時 |
| `POST /users` | admin user_uid | 60 次 / 小時 |
| `POST /users/{user_uid}/password/reset` | admin user_uid | 30 次 / 小時 |

## 17. FastAPI 實作約束

- Token 簽發 / 解碼 / hash 計算集中於 `backend/app/core/security.py`，**禁止**在各 service 重複實作。
- Refresh Token rotation 邏輯封裝於 `backend/app/services/auth/refresh.py`，**必須**包在 DB transaction。
- `require_user` / `require_admin` Dependency 封裝於 `backend/app/core/deps.py`；受保護 router **必須**透過 Dependency 注入。
- Token 明文（Access JWT、Refresh secret）與密碼明文**禁止**寫入 Log；如需記錄只保留前後 4 字元。
- 所有涉及 `users` / `refresh_tokens` 的寫入流程**必須**在 Dependency / Service 層顯式 `await db.commit()`（對齊 [20-backend.md § 8](./20-backend.md#8-session-與-transaction-規範)）。
