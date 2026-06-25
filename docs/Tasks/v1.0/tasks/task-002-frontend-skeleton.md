---
id: task-002
title: 前端骨架(Next.js scaffold + API client + auth store + layout + 登入頁)
status: done
parallel: true
depends_on: []
affected_files:
  - frontend/package.json
  - frontend/Dockerfile
  - frontend/src/app/layout.tsx
  - frontend/src/app/(auth)/login/page.tsx
  - frontend/src/lib/api/client.ts
  - frontend/src/lib/api/endpoints.ts
  - frontend/src/store/auth.ts
  - frontend/src/components/layout/Sidebar.tsx
  - frontend/src/components/layout/AppShell.tsx
estimated_hours: 4
---

## 目標

建立 Next.js 前端骨架:App Router 目錄、`ApiResponse` 解殼的 fetch client(自動帶 cookie、401 轉登入)、auth store(`me` 狀態 / RouteGuard)、主版面(Sidebar + AppShell)與登入頁。與後端解耦,純前端可獨立 `npm run build`。

## Acceptance

- [x] `cd frontend && npm run build` 通過(TypeScript 編譯無 error)
- [x] `lib/api/client.ts` 統一解 `{success,code,data,detail}` 殼;非 200 / `success:false` 拋型別化 error
- [x] 未登入存取 `(main)` 路由 → 前端 RouteGuard 導向 `/login`(`grep -n RouteGuard frontend/src` 有守衛)
- [x] 登入頁送 `POST /api/v1/auth/login` 後寫入 auth store 並導向 `/dashboard`

## 必讀檔(Just-in-time)

- [`02-frontend/00-overview.md`](../../../Design-Base/02-frontend/00-overview.md) · [`01-routing-and-error.md`](../../../Design-Base/02-frontend/01-routing-and-error.md)
- [`02-frontend/02-api-and-state.md`](../../../Design-Base/02-frontend/02-api-and-state.md) · [`03-env-and-auth.md`](../../../Design-Base/02-frontend/03-env-and-auth.md)
- [`02-frontend/90-project-frontend.md`](../../../Design-Base/02-frontend/90-project-frontend.md)
