---
id: task-001
title: Sidebar 移除「存取金鑰」section,組織順序維持部門→專案→使用者
status: done
parallel: true
depends_on: []
affected_files:
  - src/components/layout/Sidebar.tsx
estimated_hours: 1
---

## 目標
SDK Key 管理合進部門頁後,移除側邊欄「存取金鑰」整段 section,並清掉已不再使用的 icon import。

## Acceptance
- [x] 移除「存取金鑰」section 整段(底下僅 SDK Keys 一項,已失去意義)
- [x] 一併移除已不再使用的 `KeyRound` / `Server` icon import,無 unused import lint 警告
- [x] 「組織」section 順序維持為:部門 → 專案 → 使用者
- [x] 加註解標註 v1.6 變更原因(舊書籤直打 `/sdk-keys` 仍可進入)

## 必讀檔(Just-in-time)
- [`02-frontend/05-components.md`](../../../Design-Base/02-frontend/05-components.md) · [`02-frontend/01-routing-and-error.md`](../../../Design-Base/02-frontend/01-routing-and-error.md) · [`02-frontend/91-project-ui-ux.md`](../../../Design-Base/02-frontend/91-project-ui-ux.md)
