---
id: task-012
title: 前端管理頁 + 儀錶板(部門 / 專案 / 使用者 / Keys / SDK Keys / 用量 / dashboard)
status: done
parallel: false
depends_on: [task-002, task-004, task-005, task-006, task-011]
affected_files:
  - frontend/src/app/(main)/dashboard/page.tsx
  - frontend/src/app/(main)/departments/page.tsx
  - frontend/src/app/(main)/projects/page.tsx
  - frontend/src/app/(main)/users/page.tsx
  - frontend/src/app/(main)/openrouter-keys/page.tsx
  - frontend/src/app/(main)/sdk-keys/page.tsx
  - frontend/src/app/(main)/usage-logs/page.tsx
  - frontend/src/components/feature/stats/
  - frontend/src/lib/api/endpoints.ts
estimated_hours: 4
---

## 目標

依 propose § 6.2 串接前端各管理頁與儀錶板:部門 / 專案 / 使用者 / OpenRouter Keys / SDK Keys / 用量紀錄列表頁(CRUD Drawer/Dialog + 一次性明文顯示),以及 dashboard 3 張 KPI 卡 + 部門/模型長條圖 + 日用量折線(`recharts`,禁重量級儀錶板庫)。`parallel:false`:相依骨架(002)與各後端端點(004/005/006/011)。

## Acceptance

- [x] `cd frontend && npm run build` 通過(TypeScript 編譯無 error)
- [x] dashboard 三張 KPI 卡 + 部門 × tokens / 模型 × tokens / 日時序圖皆渲染(實際 API 接通)
- [x] OpenRouter Key / SDK Key / User Token 建立後一次性顯示明文,列表頁不再顯示明文
- [x] 各列表頁依角色限縮可見資源(user 僅自部門),圖表不含內部識別欄位

## 必讀檔(Just-in-time)

- [`02-frontend/01-routing-and-error.md`](../../../Design-Base/02-frontend/01-routing-and-error.md) · [`02-api-and-state.md`](../../../Design-Base/02-frontend/02-api-and-state.md)
- [`02-frontend/05-components.md`](../../../Design-Base/02-frontend/05-components.md) · [`91-project-ui-ux.md`](../../../Design-Base/02-frontend/91-project-ui-ux.md)
- [`02-frontend/06-rwd.md`](../../../Design-Base/02-frontend/06-rwd.md)
