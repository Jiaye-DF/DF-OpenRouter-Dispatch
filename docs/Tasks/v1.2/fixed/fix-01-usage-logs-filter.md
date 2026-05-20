# Fix 01 · 用量紀錄篩選區重整

## 問題

`/usage-logs` 篩選區以 5 欄 grid 擠在同一列,下拉選單與自由輸入框並用,操作體驗差:

- 部門 / 狀態用 `<select>` 下拉
- 模型用自由輸入框(易打錯、無提示)
- 起始 / 結束用 `datetime-local`,須手動輸入年月日時分
- 狀態顯示英文 `success` / `error`

## 調整

| 欄位 | 原本 | 改為 |
| --- | --- | --- |
| 部門 | `<select>` 下拉 | `FilterChip` tag nav(全部 + 各部門) |
| 狀態 | `<select>` 下拉 | `FilterChip` tag nav(全部 / 成功 / 失敗) |
| 模型 | 自由輸入框 | `Combobox` 可搜尋下拉(來源:active 模型清單) |
| 時間 | `datetime-local` ×2 | 快捷區間 chip(近 3 / 7 / 30 日)+ `type="date"` 起迄日期;預設最近 3 日 |

- 狀態文案一律中文:`成功` / `失敗`(篩選 chip 與表格徽章同步)
- 篩選改為即時套用(變更即查詢、自動回第 1 頁),移除「套用篩選」按鈕,保留「重設」
- 時間查詢:起始補 `T00:00:00`、結束補 `T23:59:59`,涵蓋整日
- 整體 layout 由單列 grid 改為依面向分列(部門 / 狀態 / 模型 / 按時間),對齊 [`11-ui-ux.md § 篩選與排序 chip`](../../../Design-Base/11-ui-ux.md)

## 交付物

- 新增:`frontend/src/components/ui/Combobox.tsx`(可搜尋單選下拉,共用元件)
- 修改:`frontend/src/app/(main)/usage-logs/page.tsx`
