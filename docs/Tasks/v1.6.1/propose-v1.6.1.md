[//]: # (此檔為 v1.6.1 任務提案,記錄 Chat 代理 tools 透傳的範圍與設計取捨。)

# Propose v1.6.1 · Chat 代理支援透傳 tools 參數(server 端工具)

> 此為 **proposal**(規劃草案),確認後即轉為正式 `tasks-v1.6.1.md`。
>
> 對應母本:[v1.6 部門+SDK Key 管理整合](../v1.6/propose-v1.6.0.md)。本版為 v1.6 之上的 patch 增量。

## 1. 目標

讓 SDK 使用者在呼叫 `POST /api/v1/model/chat` 時,能附帶 `tools` 參數,以啟用 OpenRouter **server 端內建工具**(最典型為 web search:`{"type": "openrouter:web_search"}`)。

不做:**會回 `tool_calls` 的 function calling**(見 § Out of Scope)。

## 2. 動機

- OpenRouter 的 web search 等內建工具只需在 `/chat/completions` 帶上 `tools`,即可由 OpenRouter 在伺服器端執行、把結果餵回模型,最終回應仍是純文字 —— 與本平台現有「純文字輸出」介面天然相容。
- 現有 `ChatRequest` 只收 `model` / `text` / `images` / `videos`,且 `_rewrite_request` 是「從頭重組 payload」而非 pass-through,因此 `tools` 就算送來也會被默默丟棄,使用者無法使用 web search。
- 只要開一條「受控透傳」即可滿足需求,改動面小、風險低。

## 3. 範圍

### In Scope

**後端**:

- `backend/app/schemas/model.py`:`ChatRequest` 新增 `tools: list[dict[str, Any]] | None = None` 欄位(格式同 OpenAI tools 規格,原樣透傳)。
- `backend/app/services/proxy.py`:
  - `_rewrite_request` / `_build_request_log` 接收 `tools`,有值才放進 payload / request log。
  - `run_chat` 新增 `tools` 參數並往下傳;OpenRouter 與 internal 兩條路徑共用同一 payload,故兩者皆會收到 `tools`(下游 client 本就 `json=payload` 透傳)。
- `backend/app/api/v1/model_chat.py`:`_chat_handler` 透傳 `body.tools`。
- **docstring / 註解補強**:本次一併為 `model_chat.py`、`proxy.py` 串接鏈路上的每個 function 補上 docstring 與參數說明(繁中、Google-style Args/Returns/Raises)。

**回應行為**:維持回傳純文字(`_extract_content` 不變)。`openrouter:web_search` 為 server 端工具,回應仍是 `message.content` 文字,完全相容。

**文件**:

- `docs/INTEGRATION.md`:§5 Request Body 欄位表新增 `tools` 列;新增 §5.2「啟用工具(web search)」範例與注意事項。
- `docs/Tasks/v1.6.1/propose-v1.6.1.md`(本檔)+ `tasks-v1.6.1.md`。

### Out of Scope

- **Function calling(會回 `tool_calls`)**:需改 `_extract_content` 與 `run_chat` 回傳結構(不再是純 `str`),本版不做;有需求再開新版本。
- **`tools` 格式驗證**:刻意不在本平台驗證,原樣透傳,格式錯由 OpenRouter 回對應錯誤(走既有錯誤處理)。
- **internal provider 擋下 `openrouter:` 前綴工具**:本版不加保護;地端模型若不認該工具會自行報錯。視實際使用情況再決定是否加。
- **DB schema / migration**:無變更。

## 4. 設計取捨

- **受控透傳 vs 全 pass-through**:維持「從頭重組 payload」的既有設計,只額外放行 `tools` 一個欄位,不開放 temperature / response_format 等其餘 OpenAI 欄位,保持對外介面收斂。
- **兩條路徑共用 payload**:`tools` 對 internal 也會送出,屬可接受的副作用;不為此拆分 payload 建構邏輯。
- **不擋格式**:平台只做轉發,驗證責任交給 OpenRouter,降低維護面(工具型別會隨 OpenRouter 演進)。

## 5. 既有資料相容

- 不動 DB、不動既有 API 形狀;未帶 `tools` 的舊呼叫行為完全不變。
