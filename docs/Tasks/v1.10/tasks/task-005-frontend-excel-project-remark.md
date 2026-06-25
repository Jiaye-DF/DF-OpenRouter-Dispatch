---
id: task-005
title: 前端 Excel 匯出「專案」sheet 新增「備註」欄(=專案描述)
status: done
parallel: false
depends_on: [task-004]
affected_files:
  - frontend/src/types/api.ts
  - frontend/src/lib/export/excel.ts
---

## 目標
Excel 匯出「專案」sheet 在專案名稱後新增「備註」欄(內容為專案描述),並修正受影響的 USD 格式欄索引。

## Acceptance
- [x] `types/api.ts`:`StatsByProject` 加 `project_description`。
- [x] `lib/export/excel.ts`:「專案」sheet 表頭加「備註」(置於專案名稱後)。
- [x] USD 格式欄索引改為 5(欄位順移後對齊)。
- [x] 前端 `tsc --noEmit` 無錯。

## 必讀檔(Just-in-time)
- [`02-frontend/02-api-and-state.md`](../../../Design-Base/02-frontend/02-api-and-state.md) · 型別與匯出資料對應
- [`02-frontend/91-project-ui-ux.md`](../../../Design-Base/02-frontend/91-project-ui-ux.md) · Excel 匯出欄位慣例
- [`00-overview/04-api-docs.md`](../../../Design-Base/00-overview/04-api-docs.md) · `StatsByProject` 型別新欄位
