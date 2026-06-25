# Tasks v1.3.0 · DF-SSO 單一登入整合

> 狀態:已完成(全數 done)。
>
> 母本 propose:[`propose-v1.3.0.md`](./propose-v1.3.0.md)(追溯補寫;實際實作以 commits `5923d89` + `4c3cd15` 為準)。
> 本 Tasks 為**實作契約**;設計理由請參考母本 propose。內容若衝突,以本檔為準。

## 版本資訊

- 前置依賴:v1.2.0(多 provider 代理、Internal Keys、Endpoint 收斂)。
- 本版本範圍:把平台與公司 **DF-SSO 中央認證**串接,admin 經 Email 自動對應後沿用既有 session;接收 back-channel logout;登入頁帳密 / SSO 並存。
- 對齊的 Design-Base 章節:
  - [`90-third-party-service/08-df-sso.md`](../../Design-Base/90-third-party-service/08-df-sso.md)(SSO 整合流程、env、back-channel 安全性)
  - [`03-backend/02-auth.md`](../../Design-Base/03-backend/02-auth.md)(Access + Refresh session 共用)
  - [`06-Coolify-CD/01-compose.md`](../../Design-Base/06-Coolify-CD/01-compose.md) · [`04-env-and-secrets.md`](../../Design-Base/06-Coolify-CD/04-env-and-secrets.md)

## Definition of Done

### Migration
- [x] `0004_users_sso_user_id.py`:`users` 加 `sso_user_id VARCHAR(128) NULL` + partial index `idx_users_sso_user_id WHERE is_deleted = FALSE`(供 back-channel 反查)

### Backend
- [x] `app/clients/sso.py`:DF-SSO HTTP client(token / userinfo)
- [x] `app/services/sso.py`:登入流程主體 + back-channel verifier
- [x] `app/schemas/sso.py`:請求 / 回應 / back-channel payload
- [x] `app/api/v1/auth.py` 加 SSO 子端點:`GET /sso/login`(302 至 authorize URL)、`GET /sso/callback`(換 token + 取 userinfo + 建 session + 302 至 `FRONTEND_URL`)
- [x] `app/api/back_channel.py`:`POST /api/auth/back-channel-logout`(HMAC 驗章後撤銷該使用者所有 Refresh / Access)
- [x] `app/repositories/user.py` 加 `get_by_sso_user_id` / `get_by_email_admin`
- [x] `app/services/auth.py` refactor:抽共用「建立 session cookie」邏輯供 SSO 與帳密兩路共用
- [x] `app/core/config.py` 加 SSO env 區塊:`SSO_URL` / `SSO_APP_ID` / `SSO_APP_SECRET` / `BACKEND_URL` / `FRONTEND_URL` / `SSO_TIMEOUT_SECONDS`
- [x] `app/seed.py`:啟動以 `INITIAL_ADMIN_EMAIL` 回填現有 admin 的 email(供 SSO 對應)
- [x] callback 以 email 找本地 admin:找到→回填 `users.sso_user_id`;找不到→401 `unauthorized`(本版不自動建 user)

### Frontend
- [x] `frontend/src/app/(auth)/login/page.tsx`:帳密表單上方加「使用 DF-SSO 登入」按鈕,點擊呼叫後端 `/sso/login` 啟動 OIDC 流程
- [x] `frontend/src/lib/api/endpoints.ts` 加 SSO 兩個 endpoint

### 部署
- [x] `.env.example` 加 SSO 整段(含註解)
- [x] `docker-compose-prod.yml` backend `environment` 加 SSO 對應變數(`4c3cd15`)
- [x] `SSO_TIMEOUT_SECONDS` 以字面值 `8` 注入,避免空字串解析錯誤

### Design-Base 文件同步
- [x] [`90-third-party-service/08-df-sso.md`](../../Design-Base/90-third-party-service/08-df-sso.md) 補 SSO 整合章節(流程圖、env 列表、back-channel 安全性)
- [x] [`06-Coolify-CD/01-compose.md`](../../Design-Base/06-Coolify-CD/01-compose.md) 補 compose 範本

## 流程概要

```
登入頁 → DF-SSO 按鈕 → GET /api/auth/sso/login → 302 authorize URL
  → DF-SSO 登入 → 302 /api/auth/sso/callback?code=...
    → 換 access_token → 取 userinfo(email, name, sso_user_id)
    → 以 email 找本地 admin(找到回填 sso_user_id;找不到 401)
    → 建 Access + Refresh session(沿用帳密同套 cookie)→ 302 FRONTEND_URL
DF-SSO logout → POST /api/auth/back-channel-logout(HMAC)→ verify → 撤銷該人所有 session
```

## 錯誤處理對照表

| 情境 | HTTP | `detail` |
|---|---|---|
| callback 以 email 找不到本地 admin | 401 | `unauthorized` |
| back-channel HMAC 驗章失敗 | 401 | `unauthorized` |
| SSO 上游 timeout / 換 token 失敗 | 502 | `sso_unavailable` |

## Out of Scope(本版不做)

- 使用者自助綁定 SSO(本版僅 admin 經 email 自動對應)
- 多 IdP 切換 / 動態 IdP 設定;外部(非員工)SSO
- role=user 走 SSO 登入後台;Refresh Token 結構變更;帳密登入流程任何改動

## 交付物清單

| 動作 | 路徑 |
|---|---|
| 新增 | `migrations/0004_users_sso_user_id.py` |
| 新增 | `backend/app/clients/sso.py`、`backend/app/services/sso.py`、`backend/app/schemas/sso.py`、`backend/app/api/back_channel.py` |
| 修改 | `backend/app/api/v1/auth.py`(SSO 子端點)、`backend/app/repositories/user.py`、`backend/app/services/auth.py`(抽 session helper)、`backend/app/core/config.py`、`backend/app/seed.py` |
| 修改 | `frontend/src/app/(auth)/login/page.tsx`、`frontend/src/lib/api/endpoints.ts` |
| 修改 | `.env.example`、`docker-compose-prod.yml` |
