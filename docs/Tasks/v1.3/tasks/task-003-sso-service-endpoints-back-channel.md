---
id: task-003
title: SSO 登入流程、callback、back-channel logout 端點與 session 共用重構
status: done
parallel: false
depends_on: [task-001, task-002]
affected_files:
  - backend/app/services/sso.py
  - backend/app/api/v1/auth.py
  - backend/app/api/back_channel.py
  - backend/app/repositories/user.py
  - backend/app/services/auth.py
estimated_hours: 4
---

## 目標
實作 SSO 登入主流程(login 重導向 + callback 換 token 建 session)、back-channel logout(HMAC 驗章後撤銷該人所有 session),並抽出帳密與 SSO 共用的 session cookie helper。

## Acceptance
- [x] `app/services/auth.py` 抽出共用「建立 session cookie」邏輯供帳密與 SSO 兩路共用
- [x] `app/repositories/user.py` 加 `get_by_sso_user_id` 與 `get_by_email_admin`
- [x] `app/api/v1/auth.py` 加 `GET /sso/login`(302 至 authorize URL)與 `GET /sso/callback`(換 token + 取 userinfo + 建 Access+Refresh session + 302 至 `FRONTEND_URL`)
- [x] callback 以 email 找本地 admin:找到回填 `users.sso_user_id`;找不到回 401 `unauthorized`(不自動建 user)
- [x] `app/api/back_channel.py` 加 `POST /api/auth/back-channel-logout`:HMAC 驗章失敗回 401 `unauthorized`,通過後撤銷該 sso_user_id 對應使用者所有 Refresh / Access
- [x] SSO 上游 timeout / 換 token 失敗回 502 `sso_unavailable`

## 必讀檔(Just-in-time)
- [`90-third-party-service/08-df-sso.md`](../../../Design-Base/90-third-party-service/08-df-sso.md) · [`03-backend/02-auth.md`](../../../Design-Base/03-backend/02-auth.md) · [`03-backend/91-project-auth.md`](../../../Design-Base/03-backend/91-project-auth.md) · [`03-backend/01-routing.md`](../../../Design-Base/03-backend/01-routing.md) · [`03-backend/05-exceptions-and-logging.md`](../../../Design-Base/03-backend/05-exceptions-and-logging.md)
