# Fix 05 · 模型 / 分級頁面文字清晰化

## 問題

模型相關頁面充斥縮寫與英文,使用者「看不懂」:

- 模型管理頁:卡片用 `ctx`、`Mtok`,表格 / 編輯 Dialog 用 `Context`、`$/Mtok`、`$/image`、`$/req`。
- 模型分級頁:`自動匹配 min/max(USD/Mtok)` 欄位語意不明,表頭因欄位過寬被擠成直書(`中\n文\n名\n稱`);使用者不理解「自動匹配」是什麼。

## 調整

### 模型管理(`admin/models`)

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

### 模型分級(`admin/model-tiers`)

- 新增 `PageHint` 說明「自動匹配」:同步模型時依輸入價格落點自動歸類分級。
- `自動匹配 min / max` 兩欄合併為單欄「**自動匹配價格區間(US$ / 每百萬 tokens)**」,顯示為 `0 ~ 1` / `5 以上` / `僅 0` / `不參與自動匹配`。
- 表頭加 `whitespace-nowrap`,修正被擠成直書的問題。
- 編輯 Dialog 欄位改名「價格區間下限 / 上限」,說明改寫清楚(下限含、上限不含)。

## 交付物

- 修改:`frontend/src/app/(main)/admin/models/page.tsx`
- 修改:`frontend/src/app/(main)/admin/model-tiers/page.tsx`
