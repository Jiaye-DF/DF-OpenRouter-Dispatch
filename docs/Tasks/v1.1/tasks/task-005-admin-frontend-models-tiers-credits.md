---
id: task-005
title: Admin 前端三頁 — models / model-tiers / openrouter-keys 餘額 + SyncButton
status: done
parallel: false
depends_on: [task-003]
affected_files:
  - frontend/src/app/(main)/admin/models/page.tsx
  - frontend/src/app/(main)/admin/model-tiers/page.tsx
  - frontend/src/app/(main)/admin/openrouter-keys/page.tsx
  - frontend/src/components/admin/SyncButton.tsx
  - frontend/src/components/layout/Sidebar.tsx
  - frontend/src/lib/api/endpoints.ts
  - frontend/src/types/api.ts
estimated_hours: 4
---

## 目標
建 `/admin/models`(列表 / tier 徽章 / `is_active` toggle / Drawer 編輯 tier / 搜尋 + filter)、`/admin/model-tiers`(CRUD:建立 Dialog / 編輯 Drawer / 刪除 Confirm 含 `tier_in_use` 訊息)、`/admin/openrouter-keys` 列表加餘額欄(進度條 + Free Tier 徽章 + >24h 警告色);抽出可重用 `SyncButton`(click 即 disabled 防雙擊、成功與 `sync_throttled` 同邏輯倒數、localStorage 持久化 `last_sync_ts`);Sidebar admin 分組加「模型管理」「模型分級」;補 endpoints 常數與 `Model`/`ModelTier`/`Credit` 型別。

## Acceptance
- [x] `npm run build`(frontend)成功,無型別錯誤
- [x] `grep -rn "models\|model-tiers" frontend/src/lib/api/endpoints.ts` 命中新端點常數;`types/api.ts` 含 `Model`/`ModelTier`/`Credit` 型別
- [x] `SyncButton` click 後立即 disabled;收 `sync_throttled` 依 `retry_after_seconds` 顯示倒數;重進頁面由 `localStorage.last_sync_ts` 重算 cooldown
- [x] `grep -n "模型管理\|模型分級" frontend/src/components/layout/Sidebar.tsx` 命中;openrouter-keys 頁餘額欄含進度條(>80% 警告)與 >24h 過時警告

## 必讀檔(Just-in-time)
- [`02-frontend/00-overview.md`](../../../Design-Base/02-frontend/00-overview.md) · [`02-frontend/01-routing-and-error.md`](../../../Design-Base/02-frontend/01-routing-and-error.md) · [`02-frontend/02-api-and-state.md`](../../../Design-Base/02-frontend/02-api-and-state.md) · [`02-frontend/03-env-and-auth.md`](../../../Design-Base/02-frontend/03-env-and-auth.md)
- [`02-frontend/05-components.md`](../../../Design-Base/02-frontend/05-components.md) · [`02-frontend/06-rwd.md`](../../../Design-Base/02-frontend/06-rwd.md) · [`02-frontend/04-datetime.md`](../../../Design-Base/02-frontend/04-datetime.md)
- [`02-frontend/90-project-frontend.md`](../../../Design-Base/02-frontend/90-project-frontend.md) · [`02-frontend/91-project-ui-ux.md`](../../../Design-Base/02-frontend/91-project-ui-ux.md)
