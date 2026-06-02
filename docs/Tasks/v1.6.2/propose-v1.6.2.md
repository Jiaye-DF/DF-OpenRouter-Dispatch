[//]: # (此檔為 v1.6.2 任務提案,記錄用量紀錄 tools 標記與 Input/Output 詳情頁的範圍與設計取捨。)

# Propose v1.6.2 · 用量紀錄 tools 標記 + 單筆 Input/Output 詳情頁

> 此為 **proposal**(規劃草案),確認後即轉為正式 `tasks-v1.6.2.md`。
>
> 對應母本:[v1.6.1 Chat 代理支援透傳 tools 參數](../v1.6.1/propose-v1.6.1.md)。

## 1. 目標

承 v1.6.1 開放 `tools`(可能觸發較重計費),在**用量紀錄**頁加上對應的觀測能力:

1. 列表加「是否使用工具」欄與篩選(bool)。
2. 點任一筆 → 詳情頁顯示使用者實際傳入內容(Input,含圖片)與模型完整回覆(Output)。
3. Input 的 base64 圖片在前端轉檔顯示;詳情內容體積大,改開獨立頁面而非 modal。

## 2. 動機

- `tools`(如 web search)由 OpenRouter server 端執行並**額外計費**,admin 需能快速辨識「哪些呼叫用了工具」以利成本歸因。
- 既有用量紀錄只到「token / 花費 / 狀態」層級,無法回看單筆實際 Input/Output;稽核與排查需要看到具體傳入內容。
- `request_content` 內含 base64 圖片,體積極大,不適合塞進列表或彈窗。

## 3. 範圍

### In Scope

**後端**:

- Migration `0011_usage_log_used_tools`:`usage_logs` 加 `used_tools BOOLEAN NOT NULL DEFAULT FALSE`(server_default false → 舊紀錄自動回填 false)+ **partial index** `idx_usage_logs_used_tools_time ON (created_at DESC) WHERE used_tools=TRUE AND is_deleted=FALSE`(只索引稀少的 TRUE 子集)。
- `usage_log` model 加 `used_tools` 欄。
- `proxy.schedule_usage_log`:由請求快照 `request_log.tools` 推導 `used_tools` 寫入(只改一處,不在 6 個呼叫點各傳參)。
- `proxy._summarize_response`:改存**完整** `output_text`(原僅截斷 500 字的 `first_text`);只對之後新紀錄生效。
- Schema 拆分:`UsageLogListItem`(列表,加 `used_tools`,**移除** request_content/response_summary)/ `UsageLogDetail`(詳情,含完整內容)。
- 列表端點加 `used_tools` query 篩選;repository `_apply_filters` / `list` 對應加參數。

**前端**:

- `types/api.ts`:`UsageLog` 加 `used_tools`;新增 `UsageLogDetail` / `UsageRequestContent` / `UsageResponseSummary`。
- 用量紀錄列表頁:加「工具」欄(Badge)、「是否用工具」篩選 chip、每列可點進詳情頁。
- 新詳情頁 `usage-logs/[uid]/page.tsx`:Metadata + Input(text / tools JSON / images)+ Output;base64 圖片前端 `URL.createObjectURL` 轉 blob 顯示 + 開新分頁/下載,卸載時 `revokeObjectURL`。

**文件**:admin-guide「管理頁速查」補述;Design-Base 50 §6 補 `output_text`/`used_tools`;本 propose + tasks。

### Out of Scope

- **per-caller 速率限制 / 預算配額**(現有限流僅 per-Provider-Key;caller 級配額仍為既有 Out of Scope 的「預算管理」)。
- **舊紀錄 Output 回填**(本版本前無完整回覆可補,詳情頁以 fallback + 標註處理)。
- **request_content 改 S3**(沿用現行 base64 存 JSONB,見圖片儲存路線圖,短期不動)。

## 4. 設計取捨

- **used_tools 用持久化欄位 + partial index**(而非即時由 JSONB 推導):布林低基數一般不值得索引,但 TRUE 是稀少且計費敏感的子集,partial index 成本極低且支撐「只看用工具 + 時間範圍」查詢。
- **列表/詳情 schema 拆分**:順手修正既有問題 — 原列表端點回傳含 base64 的 request_content,每頁多筆造成巨大 payload 浪費;改為列表精簡、詳情按需。
- **base64 前端轉檔**:純前端 blob,不落地、不需新端點與權限管理,最快且足夠。

## 5. 既有資料相容

- `used_tools` server_default false → 舊紀錄自動為 false,無需資料遷移。
- 舊紀錄 `response_summary` 只有 `first_text` → 詳情頁 fallback 顯示並標註「僅前 500 字」。
- SDK 對外呼叫行為**不變**;本版本純為後台觀測能力。
