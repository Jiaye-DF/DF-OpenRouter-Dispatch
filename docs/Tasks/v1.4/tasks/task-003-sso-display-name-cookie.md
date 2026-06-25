---
id: task-003
title: SSO 顯示名稱 cookie 驅動 Actor.username
status: done
parallel: true
depends_on: []
affected_files:
  - backend/app/core/deps.py
  - backend/app/services/sso.py
  - docs/Design-Base/90-third-party-service/08-df-sso.md
estimated_hours: 3
---

## 目標
SSO 登入後 `Actor.username` 顯示 SSO 本人姓名而非本地 `users.username`,透過新增的 `sso_display_name` cookie 驅動,DB 不變動。

## Acceptance
- [x] `require_user` 依 `sso_display_name` cookie 決定 `Actor.username`(SSO 登入顯示本人姓名;帳密登入顯示本地 username)
- [x] SSO callback 寫入 `sso_display_name` cookie;refresh 延展;logout 與帳密 login 清除該 cookie
- [x] DB `users.username` 不變動,無 schema migration
- [x] `90-third-party-service/08-df-sso.md` 補上 `sso_display_name` cookie 規格

## 必讀檔(Just-in-time)
- [`90-third-party-service/08-df-sso.md`](../../../Design-Base/90-third-party-service/08-df-sso.md)
- [`03-backend/02-auth.md`](../../../Design-Base/03-backend/02-auth.md) · [`03-backend/01-routing.md`](../../../Design-Base/03-backend/01-routing.md)
