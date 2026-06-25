---
id: task-002
title: DF-SSO HTTP client、schemas 與 config env 區塊
status: done
parallel: true
depends_on: []
affected_files:
  - backend/app/clients/sso.py
  - backend/app/schemas/sso.py
  - backend/app/core/config.py
estimated_hours: 3
---

## 目標
建立 DF-SSO 串接的基礎建設:HTTP client(換 token / 取 userinfo)、請求/回應/back-channel payload schemas,以及 config 的 SSO env 區塊。

## Acceptance
- [x] `app/clients/sso.py` 提供換 access_token 與取 userinfo 兩個方法,上游 timeout / 失敗時可被上層轉成 502 `sso_unavailable`
- [x] `app/schemas/sso.py` 定義登入請求 / 回應 / back-channel payload(含 HMAC 簽章欄位)
- [x] `app/core/config.py` 加 `SSO_URL` / `SSO_APP_ID` / `SSO_APP_SECRET` / `BACKEND_URL` / `FRONTEND_URL` / `SSO_TIMEOUT_SECONDS` 六個設定
- [x] `SSO_APP_SECRET` 等機密以 env 載入,不寫死於程式碼

## 必讀檔(Just-in-time)
- [`90-third-party-service/08-df-sso.md`](../../../Design-Base/90-third-party-service/08-df-sso.md) · [`90-third-party-service/01-client-design.md`](../../../Design-Base/90-third-party-service/01-client-design.md) · [`03-backend/04-config.md`](../../../Design-Base/03-backend/04-config.md) · [`00-overview/02-secrets.md`](../../../Design-Base/00-overview/02-secrets.md)
