---
id: task-003
title: 儀表板 4 張長條圖版面由 2×2 改 1×4
status: done
parallel: true
depends_on: []
affected_files:
  - frontend/src/app/(main)/dashboard/page.tsx
---

## 目標
將儀表板 4 張長條圖(部門 / 模型 / 專案 / 使用者成本)由 2×2 grid 改為每列一張、整排往下堆的 1×4 版面,圖表內容不變。

## Acceptance
- [x] 移除兩個 `lg:grid-cols-2` grid 容器。
- [x] 4 張長條圖直接置於 `flex flex-col gap-6`,每列一張。
- [x] 圖表資料與內容不變(僅版面調整)。
- [x] 前端 `tsc --noEmit` 無錯。

## 必讀檔(Just-in-time)
- [`02-frontend/06-rwd.md`](../../../Design-Base/02-frontend/06-rwd.md) · grid → flex 單欄堆疊版面
- [`02-frontend/05-components.md`](../../../Design-Base/02-frontend/05-components.md) · 圖表容器配置
- [`02-frontend/91-project-ui-ux.md`](../../../Design-Base/02-frontend/91-project-ui-ux.md) · 儀表板版面慣例
