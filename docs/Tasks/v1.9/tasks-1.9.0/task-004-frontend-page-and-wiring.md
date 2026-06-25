---
id: task-004
title: 前端申請頁、Sidebar/RouteGuard 入白名單、endpoint 與型別
status: done
parallel: false
depends_on: [task-003]
affected_files:
  - frontend/src/app/(main)/api-key-requests/page.tsx
  - frontend/src/components/layout/Sidebar.tsx
  - frontend/src/components/layout/RouteGuard.tsx
  - frontend/src/lib/api/endpoints.ts
  - frontend/src/types/api.ts
estimated_hours: 4
---

## 目標
建立 `/api-key-requests` 頁面(上方 6 欄申請表單 + 下方歷程列表分頁),並完成 member 可進入所需的三處一致設定(sidebar 不設 adminOnly、RouteGuard 白名單、後端 UserDep)前端側兩處,加上 endpoint 與型別。

## Acceptance
- [x] 新頁 `app/(main)/api-key-requests/page.tsx`:6 欄全必填表單,`project_url` 與 `owner_email` 前端即時格式提示;送出成功 toast + reload 列表,失敗 `showDialog(error, err.localizedDetail)`。
- [x] 列表 admin/member 共用同頁、前端不判 role 切換查詢(範圍由後端決定);顯示「待審核」status badge、申請時間,分頁「共 N 筆 · 第 X / Y 頁」。
- [x] `Sidebar.tsx` 新增 nav item「API Key 申請表單」,**不設 `adminOnly`**;`RouteGuard.tsx` 的 `MEMBER_ALLOWED_PREFIXES` 加入 `"/api-key-requests"`。
- [x] `lib/api/endpoints.ts` 新增 `apiKeyRequests`;`types/api.ts` 新增 `ApiKeyRequest` / `ApiKeyRequestCreate`。

## 必讀檔(Just-in-time)
- [`02-frontend/00-overview.md`](../../../Design-Base/02-frontend/00-overview.md) · 前端總覽
- [`02-frontend/01-routing-and-error.md`](../../../Design-Base/02-frontend/01-routing-and-error.md) · 路由守衛 / 錯誤呈現
- [`02-frontend/02-api-and-state.md`](../../../Design-Base/02-frontend/02-api-and-state.md) · apiClient / endpoints / 型別
- [`02-frontend/05-components.md`](../../../Design-Base/02-frontend/05-components.md) · PageTitle / Card / Table / 表單元件
- [`02-frontend/91-project-ui-ux.md`](../../../Design-Base/02-frontend/91-project-ui-ux.md) · badge / 分頁 / toast 慣例
