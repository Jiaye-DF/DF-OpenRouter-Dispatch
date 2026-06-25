---
id: task-004
title: seed 回填 admin email 與登入頁帳密／SSO 並存
status: done
parallel: false
depends_on: [task-003]
affected_files:
  - backend/app/seed.py
  - frontend/src/app/(auth)/login/page.tsx
  - frontend/src/lib/api/endpoints.ts
estimated_hours: 2
---

## 目標
讓 seed 以 `INITIAL_ADMIN_EMAIL` 回填現有 admin 的 email(供 SSO email 對應),並在登入頁帳密表單上方加 DF-SSO 登入按鈕、前端 endpoints 補上 SSO 兩個端點。

## Acceptance
- [x] `app/seed.py` 啟動時以 `INITIAL_ADMIN_EMAIL` 回填現有 admin 的 email
- [x] `frontend/src/app/(auth)/login/page.tsx` 在帳密表單上方加「使用 DF-SSO 登入」按鈕,點擊呼叫後端 `/sso/login` 啟動 OIDC 流程
- [x] `frontend/src/lib/api/endpoints.ts` 加 SSO login / callback 兩個 endpoint
- [x] 帳密登入流程維持原樣,兩種登入方式並存可用

## 必讀檔(Just-in-time)
- [`02-frontend/03-env-and-auth.md`](../../../Design-Base/02-frontend/03-env-and-auth.md) · [`02-frontend/02-api-and-state.md`](../../../Design-Base/02-frontend/02-api-and-state.md) · [`02-frontend/01-routing-and-error.md`](../../../Design-Base/02-frontend/01-routing-and-error.md) · [`03-backend/91-project-auth.md`](../../../Design-Base/03-backend/91-project-auth.md)
