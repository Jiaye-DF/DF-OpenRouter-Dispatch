# Tasks v1.6.1

## 版本資訊

- 前置依賴:v1.6.0(部門+SDK Key 管理整合)
- 本版本範圍:Chat 代理 `POST /api/v1/model/chat` 支援透傳 `tools` 參數,啟用 OpenRouter server 端內建工具(如 web search);串接鏈路 docstring 補強
- 對齊的 Design-Base 章節:
  - [50-openrouter.md](../../../Design-Base/50-openrouter.md)
- 母本 propose:[`propose-v1.6.1.md`](./propose-v1.6.1.md)(包含設計推導與決議過程)

> 本 Tasks 為**實作契約**;設計理由與替代方案請參考母本 propose。內容若與 propose 衝突,以本檔為準。

## Definition of Done

### 後端

- [N/A] 本版本不動 DB schema、不新增 migration。

#### Schema

- [x] `backend/app/schemas/model.py`:
  - `ChatRequest` 新增 `tools: list[dict[str, Any]] | None = None`(格式同 OpenAI tools 規格,原樣透傳)
  - 補 `ChatRequest` class docstring 與 `tools` 欄位內聯註解(標明僅支援 server 端工具、function calling 未開放)

#### Proxy(service 層)

- [x] `backend/app/services/proxy.py`:
  - `_rewrite_request` 接收 `tools`,有值才放進 payload(`payload["tools"]`)
  - `_build_request_log` 接收 `tools`,有值才寫進 request log
  - `run_chat` 新增 `tools` 參數,往下傳給 `_rewrite_request` / `_build_request_log`
  - OpenRouter / internal 兩條路徑共用同一 payload,皆會收到 `tools`(下游 client 本就 `json=payload` 透傳)
  - `_extract_content` 維持回純文字不變(web_search 回應仍是 `message.content` 文字)
  - 為本檔串接鏈路上每個 function 補 docstring 與參數說明(Google-style Args/Returns/Raises)

#### API 端點

- [x] `backend/app/api/v1/model_chat.py`:
  - `_chat_handler` 透傳 `body.tools` 給 `run_chat`
  - `_chat_handler` / `chat` / `chat_deprecated` 補 docstring 與參數說明

### 前端

- [x] `frontend/src/app/(main)/user-guide/page.tsx`(後台內建「使用者使用說明」頁):
  - Request Body 欄位表新增 `tools` 列(標註僅 server 端工具、function calling 未開放)
  - 新增「啟用 web search 的 Request 範例」`TOOLS_EXAMPLE` 與說明 3 點(回應仍純文字 / 透傳不驗證 / 會額外計費)
  - `npm run type-check` 通過

### 文件

- [x] `docs/INTEGRATION.md`:
  - §5 Request Body 欄位表新增 `tools` 列(標註僅 server 端工具、function calling 未開放)
  - 新增 §5.2「啟用工具(web search)」:JSON 範例 + 3 點注意事項(透傳不驗證 / 會額外計費 / tool_calls 未開放)
- [x] `docs/Design-Base/50-openrouter.md`:§5 代理端點規範 + §6 請求改寫表格 各補 tools 透傳說明
- [x] `docs/Tasks/v1.6.1/propose-v1.6.1.md`:任務提案
- [x] `docs/Tasks/v1.6.1/tasks-v1.6.1.md`(本檔):實作契約

### 驗證

- [x] `python -m py_compile`(model.py / proxy.py / model_chat.py)通過
- [x] 手動驗證(待使用者執行):
  - 帶 `tools: [{"type": "openrouter:web_search"}]` 呼叫 `/api/v1/model/chat`,模型回覆結合搜尋結果、回應為純文字
  - 未帶 `tools` 的舊呼叫行為不變
  - Swagger `/api/docs` 的 `ChatRequest` 已出現 `tools` 欄位

## 備註

- **Function calling(回 `tool_calls`)未開放**:如未來要支援,需改 `_extract_content` 與 `run_chat` 回傳結構,另開版本處理(見 propose § Out of Scope)。
