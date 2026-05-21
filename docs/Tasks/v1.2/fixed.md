# v1.2 收尾修正(fixed)

v1.2 主體與 Internal Keys 增量合併進 `main` 後,UI / 細節調整的修正項目集中於此。
與 [`tasks-v1.2.0.md`](./tasks-v1.2.0.md) 仍未完成的 DoD 項(整合測試、`20-backend.md § 3` 段落)分開追蹤。

## 修正項目總覽

| # | 項目 | 狀態 |
| --- | --- | --- |
| 01 | [用量紀錄篩選區重整](#fix-01用量紀錄篩選區重整) | 已完成 |
| 02 | [模型管理頁搜尋改 Combobox + 後端全量回傳](#fix-02模型管理頁搜尋改-combobox--後端全量回傳) | 已完成 |
| 03 | [篩選區改混合水平/垂直排列](#fix-03篩選區改混合水平垂直排列) | 已完成 |
| 04 | [新增本地模型表單精簡](#fix-04新增本地模型表單精簡) | 已完成 |
| 05 | [模型 / 分級頁面文字清晰化](#fix-05模型--分級頁面文字清晰化) | 已完成 |

---

## Fix 01 · 用量紀錄篩選區重整

### 問題

`/usage-logs` 篩選區以 5 欄 grid 擠在同一列,下拉選單與自由輸入框並用,操作體驗差:

- 部門 / 狀態用 `<select>` 下拉
- 模型用自由輸入框(易打錯、無提示)
- 起始 / 結束用 `datetime-local`,須手動輸入年月日時分
- 狀態顯示英文 `success` / `error`

### 調整

| 欄位 | 原本 | 改為 |
| --- | --- | --- |
| 部門 | `<select>` 下拉 | `FilterChip` tag nav(全部 + 各部門) |
| 狀態 | `<select>` 下拉 | `FilterChip` tag nav(全部 / 成功 / 失敗) |
| 模型 | 自由輸入框 | `Combobox` 可搜尋下拉(來源:active 模型清單) |
| 時間 | `datetime-local` ×2 | 快捷區間 chip(近 3 / 7 / 30 日)+ `type="date"` 起迄日期;預設最近 3 日 |

- 狀態文案一律中文:`成功` / `失敗`(篩選 chip 與表格徽章同步)
- 篩選改為即時套用(變更即查詢、自動回第 1 頁),移除「套用篩選」按鈕,保留「重設」
- 時間查詢:起始補 `T00:00:00`、結束補 `T23:59:59`,涵蓋整日
- 整體 layout 由單列 grid 改為依面向分列(部門 / 狀態 / 模型 / 按時間),對齊 [`11-ui-ux.md § 篩選與排序 chip`](../../Design-Base/11-ui-ux.md)

### 交付物

- 新增:`frontend/src/components/ui/Combobox.tsx`(可搜尋單選下拉,共用元件)
- 修改:`frontend/src/app/(main)/usage-logs/page.tsx`

---

## Fix 02 · 模型管理頁搜尋改 Combobox + 後端全量回傳

### 問題

- `/admin/models` 工具列「手動新增地端模型」按鈕用語,與其他頁面的「本地模型」不一致。
- 搜尋為自由輸入框,僅能對「當前載入頁(20 筆)」做 client-side filter — 跨頁的模型搜尋不到。
- 後端 `GET /api/v1/models` 採 server-side 分頁,前端無法一次掌握完整模型清單,Combobox 無法有效運作。

### 調整

#### 後端

- `GET /api/v1/models` 改為**一次回傳全部模型**(不分頁):移除 `page` / `size` / `modality` / `tier_key` query 參數,僅保留 `include_inactive`(admin)。
- `ModelRepository.list_all()` 同步精簡:去除 offset / limit 與 count,回傳 `list[Model]`。
- 回應仍維持 `Page[ModelRead]` 形狀(`total=len`、`page=1`、`size=len`),前端型別不變。
- 模型總數有限(OpenRouter 全量約數百筆),單次回傳流量可接受。

#### 前端

- 「手動新增地端模型」按鈕 → **新增本地模型**(Dialog 標題同步)。
- 搜尋框改用 `Combobox`:載入全部模型後,**僅以模型名稱**搜尋並選取單一模型定位。
- 分頁邏輯改由前端處理:`visible` 經可用性 / 分級 / 選取模型篩選後,前端切 20 筆/頁。

### 交付物

- 修改:`backend/app/api/v1/models.py`、`backend/app/repositories/model.py`
- 修改:`frontend/src/app/(main)/admin/models/page.tsx`
- 連帶:`frontend/src/app/(main)/usage-logs/page.tsx`(模型清單 fetch 移除冗餘分頁參數)

---

## Fix 03 · 篩選區改混合水平/垂直排列

### 問題

fix-01 / fix-02 將篩選區改為「依面向分列」後,每個面向各佔一整列:

- 用量紀錄:部門 / 狀態 / 模型 / 按時間 = 4 列
- 模型管理:搜尋 / 可用性 / 分級 = 3 列

列數過多佔據垂直版面,壓縮下方資料表格的可視範圍。

### 調整

原則:**短面向同列水平排列;長面向(chip 數量不定或元件較寬)獨立一列**。

#### 用量紀錄(`usage-logs`)4 列 → 3 列

| 列 | 內容 |
| --- | --- |
| 1 | 部門(chip 數量不定,獨立列) |
| 2 | 狀態 + 模型(水平同列) |
| 3 | 按時間(presets + 起迄日期 + 重設,較寬,獨立列) |

#### 模型管理(`admin/models`)3 列 → 2 列

| 列 | 內容 |
| --- | --- |
| 1 | 搜尋 Combobox(獨立列) |
| 2 | 可用性 + 分級(水平同列) |

- 同列的兩個面向以 `gap-x-8` 分隔,各自仍 `flex-wrap`,窄螢幕自然降列。

### 交付物

- 修改:`frontend/src/app/(main)/usage-logs/page.tsx`
- 修改:`frontend/src/app/(main)/admin/models/page.tsx`

---

## Fix 04 · 新增本地模型表單精簡

### 問題

`/admin/models` 的「新增本地模型」Dialog 表單過長,且夾雜大量說明文字。

### 調整

移除冗餘文字:

- 頂部藍色說明框(provider=internal 用途說明)
- Model Key 下方格式提示文字(placeholder 已示範格式)
- 底部速率限制警告(⚠ 速率限制屬 Server 層級⋯)

欄位改雙欄排列縮短高度:

| 列 | 內容 |
| --- | --- |
| 1 | Model Key（整列) |
| 2 | 名稱 + 分級(雙欄) |
| 3 | Context Length + Modality(雙欄) |
| 4 | 說明（整列) |

### 交付物

- 修改:`frontend/src/app/(main)/admin/models/page.tsx`

---

## Fix 05 · 模型 / 分級頁面文字清晰化

### 問題

模型相關頁面充斥縮寫與英文,使用者「看不懂」:

- 模型管理頁:卡片用 `ctx`、`Mtok`,表格 / 編輯 Dialog 用 `Context`、`$/Mtok`、`$/image`、`$/req`。
- 模型分級頁:`自動匹配 min/max(USD/Mtok)` 欄位語意不明,表頭因欄位過寬被擠成直書(`中\n文\n名\n稱`);使用者不理解「自動匹配」是什麼。

### 調整

#### 模型管理(`admin/models`)

縮寫一律改為完整中文標示:

| 原本 | 改為 |
| --- | --- |
| `ctx 256,000` | `上下文長度:256,000 tokens` |
| `text->text` | `模態:text → text` |
| `Prompt $X / Mtok` | `輸入價格:US$X / 每百萬 tokens` |
| `Completion $X / Mtok` | `輸出價格:US$X / 每百萬 tokens` |
| 表頭 `Context` / `Modality` / `Prompt $/Mtok` ⋯ | `上下文長度` / `模態` / `輸入價格(US$ / 每百萬 tokens)` ⋯ |
| Dialog `$/image` / `$/req` | `圖片價格(US$ / 每張)` / `請求價格(US$ / 每次)` |

- 卡片改為逐項標籤式呈現;無價格顯示「未提供」、無值顯示「未指定」。

#### 模型分級(`admin/model-tiers`)

- 新增 `PageHint` 說明「自動匹配」:同步模型時依輸入價格落點自動歸類分級。
- `自動匹配 min / max` 兩欄合併為單欄「**自動匹配價格區間(US$ / 每百萬 tokens)**」,顯示為 `0 ~ 1` / `5 以上` / `僅 0` / `不參與自動匹配`。
- 表頭加 `whitespace-nowrap`,修正被擠成直書的問題。
- 編輯 Dialog 欄位改名「價格區間下限 / 上限」,說明改寫清楚(下限含、上限不含)。

### 交付物

- 修改:`frontend/src/app/(main)/admin/models/page.tsx`
- 修改:`frontend/src/app/(main)/admin/model-tiers/page.tsx`
</content>
</invoke>
