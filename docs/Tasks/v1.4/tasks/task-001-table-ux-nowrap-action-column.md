---
id: task-001
title: 表格 whitespace-nowrap + 7 管理頁操作欄移至每列最前
status: done
parallel: true
depends_on: []
affected_files:
  - frontend/src/components/ui/table.tsx
  - frontend/src/app/(main)/users/page.tsx
  - frontend/src/app/(main)/sdk-keys/page.tsx
  - frontend/src/app/(main)/departments/page.tsx
  - frontend/src/app/(main)/projects/page.tsx
  - frontend/src/app/(main)/internal-keys/page.tsx
  - frontend/src/app/(main)/openrouter-keys/page.tsx
  - frontend/src/app/(main)/model-tiers/page.tsx
estimated_hours: 3
---

## 目標
表格欄位長文字不換行改由外層水平捲動,並將 7 個管理頁的操作欄從最後一欄移到第一欄,縮短點擊動線。

## Acceptance
- [x] `components/ui/table.tsx` 的 `TH` / `TD` 加上 `whitespace-nowrap`,長文字不換行
- [x] 表格外層具水平捲動容器,內容過寬時可橫向捲動而非擠壓換行
- [x] 7 個管理頁(`users` / `sdk-keys` / `departments` / `projects` / `internal-keys` / `openrouter-keys` / `model-tiers`)操作欄皆為每列第一欄
- [x] 7 頁表頭與資料列欄位順序一致,無欄位錯位

## 必讀檔(Just-in-time)
- [`02-frontend/05-components.md`](../../../Design-Base/02-frontend/05-components.md) · [`02-frontend/06-rwd.md`](../../../Design-Base/02-frontend/06-rwd.md) · [`02-frontend/91-project-ui-ux.md`](../../../Design-Base/02-frontend/91-project-ui-ux.md)
