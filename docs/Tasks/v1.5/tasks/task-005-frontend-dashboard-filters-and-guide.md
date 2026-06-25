---
id: task-005
title: 前端儀表板三維篩選 + 依專案/依使用者圖表 + 使用說明頁更新
status: done
parallel: false
depends_on: [task-003, task-004]
affected_files:
  - frontend/src/types/api.ts
  - frontend/src/lib/api/endpoints.ts
  - frontend/src/lib/api/error-map.ts
  - frontend/src/components/feature/stats/ByProjectBar.tsx
  - frontend/src/components/feature/stats/ByUserBar.tsx
  - frontend/src/components/feature/stats/DashboardFilters.tsx
  - frontend/src/app/(main)/dashboard/page.tsx
  - frontend/src/app/(main)/user-guide/page.tsx
estimated_hours: 4
---

## 目標
前端串接三維統計 API：新增 types/endpoints/error-map、依專案與依使用者圖表元件、三層篩選器，並重寫 dashboard 頁；同步更新使用說明頁加入 X-Project-Code。

## Acceptance
- [x] `types/api.ts` 新增 `StatsByProject` / `StatsByUser` / `UserDropdownItem`；`UsageLog` 加 `project_uid: string | null`；`StatsByDepartment` 加 `department_code`
- [x] `lib/api/endpoints.ts` 加 `usersDropdown` / `statsByProject` / `statsByUser`；`lib/api/error-map.ts` 加 `project_code_required` / `project_invalid` 中文化
- [x] 新增 `ByProjectBar.tsx` / `ByUserBar.tsx`（抄 DeptTokensBar 改 dataKey/title）與 `DashboardFilters.tsx`（3 個 select、admin 可任選、non-admin 部門固定 badge、切部門重設並重拉 project/user 下拉）
- [x] `app/(main)/dashboard/page.tsx` 重寫：filters state `{department_uid, project_uid, user_uid}`，6 個 stats 呼叫都帶 filters，layout 加入 ByProjectBar / ByUserBar 行
- [x] `app/(main)/user-guide/page.tsx`：憑證 grid 改 3-column 加 X-Project-Code 卡片、HTTP/curl/Python 範例加 header、ERRORS 陣列加兩條新錯誤碼
- [x] `npm run build` 通過（TypeScript 無 error）

## 必讀檔(Just-in-time)
- [`02-frontend/02-api-and-state.md`](../../../Design-Base/02-frontend/02-api-and-state.md) · [`02-frontend/05-components.md`](../../../Design-Base/02-frontend/05-components.md) · [`02-frontend/01-routing-and-error.md`](../../../Design-Base/02-frontend/01-routing-and-error.md) · [`02-frontend/06-rwd.md`](../../../Design-Base/02-frontend/06-rwd.md) · [`02-frontend/91-project-ui-ux.md`](../../../Design-Base/02-frontend/91-project-ui-ux.md) · [`02-frontend/04-datetime.md`](../../../Design-Base/02-frontend/04-datetime.md)
