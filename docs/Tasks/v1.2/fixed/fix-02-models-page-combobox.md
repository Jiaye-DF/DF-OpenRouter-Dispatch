# Fix 02 · 模型管理頁搜尋改 Combobox + 後端全量回傳

## 問題

- `/admin/models` 工具列「手動新增地端模型」按鈕用語,與其他頁面的「本地模型」不一致。
- 搜尋為自由輸入框,僅能對「當前載入頁(20 筆)」做 client-side filter — 跨頁的模型搜尋不到。
- 後端 `GET /api/v1/models` 採 server-side 分頁,前端無法一次掌握完整模型清單,Combobox 無法有效運作。

## 調整

### 後端

- `GET /api/v1/models` 改為**一次回傳全部模型**(不分頁):移除 `page` / `size` / `modality` / `tier_key` query 參數,僅保留 `include_inactive`(admin)。
- `ModelRepository.list_all()` 同步精簡:去除 offset / limit 與 count,回傳 `list[Model]`。
- 回應仍維持 `Page[ModelRead]` 形狀(`total=len`、`page=1`、`size=len`),前端型別不變。
- 模型總數有限(OpenRouter 全量約數百筆),單次回傳流量可接受。

### 前端

- 「手動新增地端模型」按鈕 → **新增本地模型**(Dialog 標題同步)。
- 搜尋框改用 `Combobox`:載入全部模型後,**僅以模型名稱**搜尋並選取單一模型定位。
- 分頁邏輯改由前端處理:`visible` 經可用性 / 分級 / 選取模型篩選後,前端切 20 筆/頁。

## 交付物

- 修改:`backend/app/api/v1/models.py`、`backend/app/repositories/model.py`
- 修改:`frontend/src/app/(main)/admin/models/page.tsx`
- 連帶:`frontend/src/app/(main)/usage-logs/page.tsx`(模型清單 fetch 移除冗餘分頁參數)
