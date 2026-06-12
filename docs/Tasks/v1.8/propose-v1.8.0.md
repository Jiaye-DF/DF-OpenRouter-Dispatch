[//]: # (此檔為 v1.8 任務提案,實作前先由使用者確認範圍與設計取捨。)

# Propose v1.8.0 · 檔案上傳（PDF 等）支援

> 此為 **proposal**(規劃草案),確認後即轉為正式 `tasks-v1.8.0.md`。
>
> 對應母本:[v1.7 串流（SSE）回應支援](../v1.7/propose-v1.7.0.md)。

## 1. 目標

讓代理端的 chat 請求可隨訊息**附上檔案**(主要為 PDF),交由模型閱讀後回答。對齊 OpenRouter 的 `file` content part,於既有 `/model/chat` 與 `/model/chat/stream` 兩端點皆支援,**不**新增端點。

核心是把既有「文字 / 圖片」多模態輸入再擴一種:`files: [{ filename, file_data }]`,後端組裝為 OpenAI-compatible 的 `{"type":"file","file":{...}}` content block 後透傳 OpenRouter,由 OpenRouter 負責解析(模型原生支援檔案則直接傳入,否則 OpenRouter 解析後再送模型)。

**這是輸入方向(SDK → 模型)的功能**,與 v1.7 的串流(輸出方向)正交;兩者可組合使用。

## 2. 動機

- 既有輸入僅 `text` / `images`,使用者無法直接讓模型讀 PDF / 文件。
- OpenRouter 原生支援以 `file` content part 帶 PDF(URL 或 base64 data URL),後端只需擴充組裝層,不需自行做檔案解析。
- 與 `images` 的處理高度對稱,改動面小、風險低。

## 3. 範圍

### In Scope

**後端**:

- `ChatRequest` 新增 `files: list[ChatFile] | None`;`ChatFile = { filename: str, file_data: str }`。
- [`proxy.py`](../../../backend/app/services/proxy.py) `_rewrite_request()` 擴充:對每個 file append `{"type":"file","file":{"filename":..., "file_data":...}}` 至 user 訊息 content。
- `run_chat()` / `run_chat_stream()` 簽名加 `files`,透傳給組裝與記帳。
- 端點 [`model_chat.py`](../../../backend/app/api/v1/model_chat.py) 兩處(非串流 + 串流)把 `body.files` 轉 dict 後傳入 service。

**隱私 / 法務(本版關鍵取捨,見 § 9)**:

- `usage_logs.request_content` 對 files **只記錄 `filename`,不記 `file_data`(檔案內容)**;`_build_request_log()` 據此實作。

**文件**:

- 更新 [`docs/INTEGRATION.md`](../../INTEGRATION.md):§5 欄位表新增 `files`、新增 §5.3 檔案上傳範例與隱私說明、§10 儲存說明補檔案例外(對外 API 鏈路異動,須連帶更新)。
- 本檔(propose)→ 確認後產出 `docs/Tasks/v1.8/tasks-v1.8.0.md`。

### Out of Scope

- **PDF 解析引擎 / plugins 選擇**:OpenRouter 支援 `plugins`(`file-parser` 之 `native` / `mistral-ocr` / `cloudflare-ai`)指定引擎與計費。本版**不**開放給 SDK 選擇,沿用 OpenRouter 預設(優先模型原生 → 否則 cloudflare-ai fallback)。如有掃描檔 OCR 需求再於後續版本評估。
- **檔案大小 / MIME 驗證、病毒掃描**:本版不在後端做檔案層級驗證;`file_data` 由 OpenRouter 解讀,格式錯誤由 OpenRouter 回對應錯誤。
- **檔案落地儲存 / S3**:屬另一條獨立路線(image-storage roadmap);本版檔案內容**僅於該次請求轉送**,不寫入任何儲存。
- **影片(`videos`)**:維持不支援,送出即 `400 feature_not_supported`。
- **前端 UI**:chat 由 SDK 直呼,管理後台不呼叫;本版無前端改動。
- **DB schema / migration**:不新增欄位(僅檔名塞進既有 `request_content` JSONB);不需 migration。

## 4. 流程概要

```
SDK ──▶ POST /api/v1/model/chat( /stream )   Headers: X-SDK-Key, X-User-Token
                                             Body:    { model, text, images, files, tools }
  │
  │   1. 驗 SDK Key + User Token(沿用 SdkCallerDep)
  │   2. videos 非空 → 400 feature_not_supported
  │   3. 白名單檢查
  │   4. _rewrite_request:text / images / files 合併為單一 user 訊息 content
  │        files → {"type":"file","file":{"filename","file_data"}}
  │   5. _build_request_log:files 只留 filename(不留 file_data)
  │   6. 透傳 OpenRouter /chat/completions(由 OR 解析檔案)
  ▼
SDK ◀── 純文字回應(非串流) / SSE {id,content}(串流)
  └─ 背景寫 usage_logs(request_content.files = [filename, ...])
```

## 5. 設計重點

### 5.1 `files` 為何用結構化物件而非 `list[str]`

`images` 是 `list[str]`(URL / data URI 即可)。但 OpenRouter 的 `file` content part **要求 `filename`**(用於副檔名判斷與解析),故 file 無法只給一個字串,必須 `{ filename, file_data }` 成對。`file_data` 同 `images` 可填 base64 data URL 或遠端 URL。

### 5.2 用量紀錄只存檔名(法務考量)

- 與 `images` 不同:圖片內容(含 base64 data URI)會留存於 `request_content` 供後台稽核預覽;**檔案不留存內容**,只留 `filename`。
- 理由:使用者上傳的文件可能含個資 / 機敏 / 受著作權保護內容,長期留存於系統有法律風險。只留檔名即可滿足「哪個請求帶了哪些檔案」的稽核需求,而不持有檔案本體。
- 實作落點單一:`_build_request_log()`;`_rewrite_request()`(送 OpenRouter 的 payload)仍帶完整 `file_data`,兩者刻意分離。

### 5.3 兩端點一致

非串流 `/model/chat` 與串流 `/model/chat/stream` 皆走同一組 `_rewrite_request` / `_build_request_log`,故 `files` 在兩端點行為一致(含「只存檔名」)。

## 6. 錯誤處理對照

| 情境 | 回應 |
| --- | --- |
| `filename` / `file_data` 缺漏或空字串 | `422`(Pydantic 驗證,`ChatFile` 欄位必填) |
| `videos` 非空 | `400 feature_not_supported`(不變) |
| `file_data` 格式 / 內容無法解析 | 由 OpenRouter 回對應錯誤(本平台不另驗證) |
| 模型不支援檔案輸入 | OpenRouter 自動解析後送模型(native 不可用時 fallback) |

## 7. 用量紀錄（usage_logs）

- `request_content.files`:`[filename, ...]`(僅檔名);無 `file_data`。
- 其餘欄位(token / cost / latency / status / used_tools)沿用既有邏輯,不因 files 改變。
- 不新增欄位;`files` 為 `request_content` JSONB 內的可選鍵(有檔案才出現,與 `tools` 一致)。

## 8. 設定與相容

- 不新增環境變數、不改 DB schema、不需 migration。
- 既有不帶 `files` 的請求行為完全不變;`files` 為純新增的可選欄位,向後相容。
- 對齊的 Design-Base 章節:
  - [50-openrouter.md § 4 呼叫流程 / § 6 回應精簡 / § 10 用量紀錄](../../Design-Base/50-openrouter.md)
  - [80-permission.md § 5 代理端存取規則](../../Design-Base/80-permission.md)

## 9. 設計取捨 / 決議

> **決議(2026-06-12,使用者確認)**:
> - (1) **用量紀錄只存 `filename`、不存 `file_data`**(法務考量:避免留存使用者上傳之文件內容)。為本版最關鍵取捨,落點 `_build_request_log()`。
> - (2) PDF 解析引擎 / `plugins` 選擇**本版不開放**,沿用 OpenRouter 預設。
> - (3) `files` 採結構化 `{ filename, file_data }`(因 OpenRouter `file` part 必帶 filename)。
> - (4) 非串流與串流端點**一併支援**。
> - (5) 對外 API 鏈路異動,`docs/INTEGRATION.md` 本版一併更新。

1. **是否開放 SDK 指定解析引擎(mistral-ocr 等)?** 本版建議否(預設即可,掃描檔 OCR 需求再評估)。
2. **是否需在後端限制檔案大小 / 數量?** 本版未做;若擔心濫用,可後續加上單請求檔案數 / 大小上限與對應 400。
