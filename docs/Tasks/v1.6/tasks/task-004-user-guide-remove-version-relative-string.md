---
id: task-004
title: User Guide 錯誤碼表移除「(v1.5+ 必填)」版本相對字串
status: done
parallel: true
depends_on: []
affected_files:
  - src/app/(main)/user-guide/page.tsx
estimated_hours: 1
---

## 目標
清理後台導引動線雜訊:錯誤碼表 `project_code_required` 描述移除「(v1.5+ 必填)」版本相對字串,讓文件描述「現在是怎樣」。

## Acceptance
- [x] 錯誤碼表 `project_code_required` 描述移除「(v1.5+ 必填)」字串
- [x] 描述語意維持完整可讀(移除後不留多餘括號 / 空白)
- [x] 僅動 user-guide 頁,`docs/INTEGRATION.md` 的版本相對字串維持不動(對外讀者仍需要)
- [x] `npm run type-check` 通過

## 必讀檔(Just-in-time)
- [`02-frontend/05-components.md`](../../../Design-Base/02-frontend/05-components.md) · [`02-frontend/91-project-ui-ux.md`](../../../Design-Base/02-frontend/91-project-ui-ux.md)
