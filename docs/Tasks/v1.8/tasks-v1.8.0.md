# Tasks v1.8.0

## 版本資訊

- 前置依賴:v1.2 多 provider 代理(`/model/chat`、usage_logs)、v1.7 串流端點(`/model/chat/stream`)已完成。
- 本版本範圍:chat 請求新增 **檔案上傳(PDF 等)** 支援。新增 `files: [{ filename, file_data }]` 欄位,後端組裝為 OpenRouter `file` content part 透傳;**用量紀錄僅保留檔名,不留存檔案內容(法務考量)**。非串流與串流端點皆支援。
- 對齊的 Design-Base 章節:
  - [50-openrouter.md § 4 呼叫流程](../../Design-Base/50-openrouter.md)
  - [50-openrouter.md § 6 回應精簡](../../Design-Base/50-openrouter.md)
  - [50-openrouter.md § 10 用量紀錄](../../Design-Base/50-openrouter.md)
  - [80-permission.md § 5 代理端存取規則](../../Design-Base/80-permission.md)
  - [90-task-spec.md § 4 / § 5](../../Design-Base/90-task-spec.md)
- 母本 propose:[`propose-v1.8.0.md`](./propose-v1.8.0.md)(包含設計推導與決議過程)

> 本 Tasks 為**實作契約**;設計理由與替代方案請參考母本 propose。內容若與 propose 衝突,以本檔為準。

## Definition of Done

### 後端

- [x] `ChatRequest` 新增 `files: list[ChatFile] | None`;`ChatFile = { filename(必填), file_data(必填) }`(`schemas/model.py`)。
- [x] `/model/chat` 與 `/model/chat/stream` 皆可帶 `files`:每個檔案組裝為 `{"type":"file","file":{"filename","file_data"}}` 併入 user 訊息 content,透傳 OpenRouter。
- [x] `file_data` 支援 base64 data URL(`data:application/pdf;base64,...`)與可公開存取的遠端 URL。
- [x] **用量紀錄只記 `filename`、不記 `file_data`**:`request_content.files = [filename, ...]`(`_build_request_log()`)。
- [x] 不帶 `files` 的既有請求行為完全不變(向後相容)。
- [x] Swagger 於 `/api/docs` 反映 `files` 欄位(由 Pydantic schema 自動產生)。
- [x] SDK 對外文件 / `docs/INTEGRATION.md` 新增 `files` 欄位、範例與隱私說明。
- [x] 單元 / 整合測試:`files` 組裝為正確 content part、`request_content` 僅含檔名、`ChatFile` 缺欄回 422、串流端點亦帶 files。(專案目前無測試框架,待補)

### 前端

- [x] 無(chat 由 SDK 直呼,管理後台不呼叫;本版本無前端改動)。

## 功能設計

### A. Schema `ChatFile` / `ChatRequest.files`

- 位置:[`schemas/model.py`](../../../backend/app/schemas/model.py)。
- `ChatFile`:`filename`(`min_length=1, max_length=255`)、`file_data`(`min_length=1`);兩者必填,缺漏由 Pydantic 回 422。
- `ChatRequest.files: list[ChatFile] | None = None`,語意同既有 `images`(可選的多模態輸入)。

### B. 組裝 `_rewrite_request()`

- 位置:[`services/proxy.py`](../../../backend/app/services/proxy.py)。
- 簽名加 `files: list[dict[str, str]] | None = None`。
- 在 images 之後,對每個 file append:
  ```python
  {"type": "file", "file": {"filename": f["filename"], "file_data": f["file_data"]}}
  ```
- text / images / files 皆空時仍補空白 text block(維持既有「messages 不為空」保證)。

### C. 記帳 `_build_request_log()`

- 位置:[`services/proxy.py`](../../../backend/app/services/proxy.py)。
- 簽名加 `files`;**只取檔名**:
  ```python
  if files:
      log["files"] = [f["filename"] for f in files]
  ```
- **不**寫入 `file_data`。與 `tools` 一致:有值才出現於 `request_content`。

### D. Service 透傳 `run_chat()` / `run_chat_stream()`

- 兩者簽名加 `files`,分別傳給 `_rewrite_request(...)` 與 `_build_request_log(...)`;其餘流程(白名單 / failover / 記帳)不變。

### E. 端點 `model_chat.py`

- 位置:[`api/v1/model_chat.py`](../../../backend/app/api/v1/model_chat.py)。
- `_chat_handler`(非串流 + deprecated alias 共用)與 `chat_stream` 兩處,把 `body.files` 轉為 dict 後傳入 service:
  ```python
  files=[f.model_dump() for f in body.files] if body.files else None
  ```

## 隱私 / 敏感欄位處理表

| 資料 | 送 OpenRouter（`_rewrite_request`） | 用量紀錄（`_build_request_log`） |
| --- | --- | --- |
| `files[].filename` | ✅ 帶入 | ✅ 保留 |
| `files[].file_data`(檔案內容) | ✅ 帶入(該次請求) | ❌ **不留存** |
| `images`(含 base64) | ✅ 帶入 | ✅ 保留(供稽核預覽,與檔案不同) |

## 錯誤處理對照表

| 情境 | 時機 | HTTP / 行為 | detail |
| --- | --- | --- | --- |
| `filename` / `file_data` 缺漏或空 | 驗證 | 422 | Pydantic validation |
| `videos` 非空 | pre-call | 400 + ApiResponse | `feature_not_supported` |
| `file_data` 無法解析 | 下游 | 由 OpenRouter 回對應錯誤 | (透傳) |

## 用量與稽核

- `request_content.files` 僅含檔名陣列(有檔案才出現);無 `file_data`。
- token / cost / latency / status / used_tools 沿用既有邏輯,不因 files 改變。
- 無管理端異動操作,無稽核 Log 變更。

## 交付物清單

- 後端檔案:
  - 修改 [`backend/app/schemas/model.py`](../../../backend/app/schemas/model.py)(加 `ChatFile`、`ChatRequest.files`)
  - 修改 [`backend/app/services/proxy.py`](../../../backend/app/services/proxy.py)(`_rewrite_request` / `_build_request_log` / `run_chat` / `run_chat_stream` 加 `files`)
  - 修改 [`backend/app/api/v1/model_chat.py`](../../../backend/app/api/v1/model_chat.py)(兩端點傳 `files`)
- 前端檔案:無(消費端為 SDK)。
- Migration:無(不改 DB schema)。
- 環境變數:無新增。
- 文件:更新 [`docs/INTEGRATION.md`](../../INTEGRATION.md)(§5 欄位表、§5.3 範例、§10 儲存說明)。

## 測試重點

- 組裝:帶 `files` 的請求,送 OpenRouter 的 content 含正確 `{"type":"file","file":{...}}`,且 filename / file_data 對應。
- 記帳:`request_content.files` 只有檔名、**不含** `file_data`;不帶 files 時 `request_content` 無 `files` 鍵。
- 驗證:`ChatFile` 缺 `filename` 或 `file_data` → 422。
- 串流:`/model/chat/stream` 帶 files 行為與非串流一致(含只存檔名)。
