# Propose v1.3.0 · DF-SSO 單一登入整合

> 此為**追溯補寫的 proposal**(原版本實作落地時未撰寫 spec,本檔依 git 歷史與既有程式碼回填,方便後續維護);實際實作以 commits `5923d89` + `4c3cd15` 為準。
>
> 對應母本:[v1.2 已落地的 Internal Keys 與 Endpoint 收斂](../v1.2/propose-v1.2.0.md)。

## 1. 目標

把平台與公司既有的 **DF-SSO 中央認證**串接起來,讓 admin 不必各自管理帳密;同時不破壞既有「帳號密碼登入」流程,兩者並存。

具體三件事:

1. **加入 SSO 登入閘道**:`/api/auth/sso/login` 與 `/api/auth/sso/callback`,以 Email 對應到本地 admin 後沿用既有 Access + Refresh session 機制。
2. **接收 SSO back-channel logout**:中央登出時透過 HMAC 簽章通知本平台,本地 session 同步失效。
3. **登入頁 UI 並存**:既有帳號密碼表單與 DF-SSO 按鈕並列,使用者依自身狀況擇一。

## 2. 動機

- 公司內部已有 DF-SSO 為中央認證來源,**每位管理員不應再記憶第二組密碼**。
- 中央登出時若本地仍持有有效 session,會出現「在 SSO 登出但平台還在線」的安全漏洞 → 需 **back-channel logout**。
- 但平台還有「初始化超管」與「離線除錯」場景,**完全廢除帳密登入會自鎖** → 兩者並存。

## 3. 範圍

### In Scope

**Schema**(migration `0004_users_sso_user_id.py`):
- `users` 新增 `sso_user_id VARCHAR(128) NULL`
- 對應 partial index `idx_users_sso_user_id WHERE is_deleted = FALSE` 供 back-channel 反查

**後端**:
- 新增 `app/clients/sso.py`(DF-SSO HTTP client,token / userinfo)
- 新增 `app/services/sso.py`(登入流程主體 + back-channel verifier)
- 新增 `app/schemas/sso.py`(請求 / 回應 / back-channel payload)
- 新增 `app/api/v1/auth.py` SSO 子端點:`GET /sso/login` 重導向、`GET /sso/callback` 換 token+建立 session
- 新增 `app/api/back_channel.py`:`POST /api/auth/back-channel-logout` 端點(HMAC 驗章後撤銷該使用者所有 Refresh / Access)
- `app/repositories/user.py` 加 `get_by_sso_user_id` / `get_by_email_admin`
- `app/services/auth.py` refactor:抽出共用「建立 session cookie」邏輯供 SSO 與帳密兩條路共用
- `app/core/config.py` 加 SSO 相關 env 區塊:`SSO_URL` / `SSO_APP_ID` / `SSO_APP_SECRET` / `BACKEND_URL` / `FRONTEND_URL` / `SSO_TIMEOUT_SECONDS`
- `app/seed.py`:啟動初始化支援以 `INITIAL_ADMIN_EMAIL` 回填現有 admin 的 email(讓 SSO 能找到對應使用者)

**前端**:
- `frontend/src/app/(auth)/login/page.tsx`:在帳密表單上方加「使用 DF-SSO 登入」按鈕,點擊呼叫後端 `/sso/login` 端點開始 OIDC 流程
- `frontend/src/lib/api/endpoints.ts` 加 SSO 兩個 endpoint

**部署**:
- `.env.example` 加 SSO 整段(含註解)
- `docker-compose-prod.yml` backend `environment` 段加 SSO 對應變數(由 `4c3cd15` 補上)
- `SSO_TIMEOUT_SECONDS` 以字面值 `8` 注入,避免空字串解析錯誤

**文件**:
- `docs/Design-Base/70-auth.md` 補 SSO 整合章節(流程圖、env 列表、back-channel 安全性)
- `docs/Design-Base/40-deployment.md` 補 compose 範本

### Out of Scope

- 使用者自助綁定 SSO(本版只允許 admin 經 email 自動對應)
- 多 IdP 切換 / 動態 IdP 設定
- 外部使用者(非公司員工)的 SSO
- 既有 SDK 使用者(role=user)走 SSO 登入(這群人本來就不登入後台)
- Refresh Token 結構變更
- 帳密登入流程的任何改動

## 4. 流程概要

```
使用者 → 登入頁 → 點 DF-SSO 按鈕
        │
        └─→ GET /api/auth/sso/login → 302 redirect to DF-SSO authorize URL
            │
            └─→ DF-SSO 登入 → 302 callback to /api/auth/sso/callback?code=...
                │
                ├─ 換 access_token(client_credentials + code)
                ├─ 取 userinfo (email, name, sso_user_id)
                ├─ 以 email 找本地 admin user
                │  ├─ 找到 → 用 sso_user_id 回填 users.sso_user_id
                │  └─ 找不到 → 401 unauthorized(本版不自動建 user)
                ├─ 建立 Access + Refresh session(沿用帳密登入的同套 cookie)
                └─ 302 redirect to FRONTEND_URL(進首頁)

DF-SSO logout → POST /api/auth/back-channel-logout(HMAC 簽章)
              → verify → 找 sso_user_id 對應 local user → 撤銷該人所有 Refresh + Access
```

## 5. 已知後續(留待後續版本處理)

- **v1.4 增量**:`9c8ae63` 補上「SSO 登入後顯示對應使用者姓名」(`sso_display_name` cookie 機制),屬於 UX 增強而非 v1.3 本身遺漏
- 後續若要支援自助綁定:需新增「帳密登入後手動綁 SSO」流程,本版不做
