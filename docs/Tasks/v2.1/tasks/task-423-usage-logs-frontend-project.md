---
id: task-423
title: 前端 用量記錄 專案欄 + 專案 Combobox 篩選 + 明細專案欄 + RouteGuard/Sidebar 放行
status: done
parallel: false
depends_on: [task-421, task-422]
affected_files:
  - frontend/src/app/(main)/usage-logs/page.tsx
  - frontend/src/app/(main)/usage-logs/[uid]/page.tsx
  - frontend/src/components/layout/RouteGuard.tsx
  - frontend/src/components/layout/Sidebar.tsx
  - frontend/src/types/api.ts
estimated_hours: 3
---

## 目標

用量記錄前端串接 task-421 的部門下放與專案欄:列表加「專案」欄 + 可搜尋的專案 Combobox 篩選、明細加「專案」欄位,並放行一般使用者進入 `/usage-logs`(對齊 propose §C.3)。

## 範圍與要點

- **可見性**:`RouteGuard.tsx` 的 `MEMBER_ALLOWED_PREFIXES` 加 `/usage-logs`;`Sidebar.tsx` 用量記錄入口由 `adminOnly:true` 改為對所有登入者顯示。
- **型別**:`types/api.ts` 的 usage-log 列表/明細型別補 `project_uid: string | null`、`project_code: string | null`、`project_name: string | null`;列表查詢參數型別補 `project_uid?`。
- **列表頁** `usage-logs/page.tsx`:
  - 新增「**專案**」欄(顯示 `project_code`;副標 `project_name`;NULL → 「—」)。
  - 篩選列新增**專案** `Combobox`(`components/ui/Combobox.tsx`,可輸入搜尋),選定帶 `project_uid` 查詢;選項來源 `GET /api/v1/projects`(`API_ENDPOINTS.projects`,非-admin 已鎖部門),沿用 `DashboardFilters` 抓專案清單的既有模式。
  - 非-admin 檢視隱藏「部門」等 admin-only 篩選(UX;後端仍鎖部門把關)。
- **明細頁** `usage-logs/[uid]/page.tsx`:基本資訊區新增「專案」欄位(`project_code` + `project_name`);非-admin 檢視**不**渲染 `AiAnalysisSection`(維持 admin-only,以 `role === "admin"` 條件渲染)。

## Acceptance

- [ ] `cd frontend && npm run lint && npx tsc --noEmit` 零錯誤零 warning
- [ ] `grep -n "/usage-logs" frontend/src/components/layout/RouteGuard.tsx` 命中(已加入 MEMBER_ALLOWED_PREFIXES)
- [ ] `grep -n "Combobox" frontend/src/app/(main)/usage-logs/page.tsx` 命中(專案篩選)
- [ ] `grep -nE "project_code|project_name" frontend/src/types/api.ts` 命中(型別已補專案欄)
- [ ] 手測(記於 PR):一般使用者可進 `/usage-logs`,列表僅見自身部門紀錄且有「專案」欄;專案 Combobox 可搜尋選定並過濾;明細頁見「專案」欄位且非-admin 不顯示 AI 分析區塊
- [ ] `cd frontend && npm run build` 成功

## 必讀檔(Just-in-time)

- `docs/Design-Base/02-frontend/00-overview.md`
- `docs/Design-Base/02-frontend/02-api-and-state.md`
- `docs/Design-Base/02-frontend/03-env-and-auth.md`
- `docs/Design-Base/02-frontend/05-components.md`
- `docs/Design-Base/02-frontend/06-rwd.md`
- `docs/Design-Base/02-frontend/90-project-frontend.md`
- `docs/Design-Base/02-frontend/91-project-ui-ux.md`
- `docs/Design-Base/03-backend/92-project-permission.md`
