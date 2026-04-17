# 50 · OpenRouter 整合

本文件定義後端作為 OpenRouter API 代理層的整合規範：API Key 管理、路由策略、錯誤處理、重試、串流、用量與稽核。

> OpenRouter 官方文件：https://openrouter.ai/docs

## 1. 代理原則

- **後端為唯一出口**：所有對 OpenRouter 的呼叫**必須**經由 `backend/app/clients/openrouter/`，**禁止**前端或其他服務直連。
- **API Key 僅存後端**：OpenRouter 的 API Key 透過環境變數 `OPENROUTER_API_KEY` 注入，或加密後寫入 DB。**禁止**在 Response、Log、前端程式碼中出現。
- **使用者不持有 OpenRouter Key**：本平台對使用者發放的是**本地金鑰**（詳見 § 3），由本平台在後端換發 OpenRouter 呼叫；使用者**永遠無法**取得 OpenRouter 原生 Key。

## 2. Client 結構

```
backend/app/clients/openrouter/
├── __init__.py
├── client.py          # OpenRouterClient（httpx.AsyncClient 封裝）
├── schemas.py         # OpenRouter Request / Response Pydantic 模型
└── errors.py          # OpenRouterError 家族
```

**Client 職責：**

- 包裝 HTTP 呼叫（chat completions、models list、generation metadata 查詢）。
- 注入 `Authorization: Bearer ${OPENROUTER_API_KEY}` 與必要 Header（例如 `HTTP-Referer`、`X-Title`）。
- 統一處理逾時、重試、錯誤分類。
- **禁止**在 Client 層決定業務規則（配額、白名單、模型改寫），這屬於 service 層的職責。

**依賴注入：**

```python
# backend/app/core/deps.py
async def get_openrouter_client() -> OpenRouterClient: ...
```

所有 service **必須**透過 `Depends(get_openrouter_client)` 取得 Client，**禁止**自行 `httpx.AsyncClient()`。

## 3. 本地金鑰（Local API Key）

- 本平台對使用者發放自有金鑰（格式建議 `ord_<prefix>_<random>`，例：`ord_live_Ab3...`）。
- 金鑰於建立時回傳一次明文，其後 DB 僅保留 **hash** 與 **prefix**；**禁止**以明文寫入 DB 或 Log。
- 每把金鑰綁定：
  - 擁有者（`user_uid`）
  - 可用模型白名單（`allowed_models`，空值代表無限制、但仍受平台全域設定限制）
  - 配額（每日 / 每月請求數、Token 數、金額上限）
  - 啟用狀態（`is_active`）
- 呼叫代理端點時以 `Authorization: Bearer ord_...` 帶入，後端比對 hash 後執行。

## 4. 呼叫流程

```
Client (使用者應用 / 管理 UI)
  │  Authorization: Bearer ord_...
  ▼
[backend] /api/v1/proxy/chat/completions
  │  1. 驗證本地金鑰 hash → user + 配額上下文
  │  2. 檢查模型白名單
  │  3. 檢查配額（日 / 月 / 金額）
  │  4. 改寫 Request（剝除敏感欄位、補 metadata）
  │  5. 呼叫 OpenRouterClient
  ├───────────────────▶ OpenRouter /api/v1/chat/completions
  │                     （Authorization: Bearer OPENROUTER_API_KEY）
  │  6. 接收 Response / stream chunk
  │  7. 擷取 usage（tokens、cost）並寫入 usage_logs
  │  8. 串回 Client（維持 Response 結構；串流為 SSE）
  ▼
Client
```

## 5. 代理端點規範

- 路徑**必須**使用 `/api/v1/proxy/<openrouter-path>`，對應 OpenRouter 的官方 path（去掉 `/api/v1`）。
  - 例：OpenRouter `POST /api/v1/chat/completions` → 本平台 `POST /api/v1/proxy/chat/completions`
- Request 欄位**應**盡量與 OpenRouter 相容，以利既有 SDK（OpenAI Python、LangChain 等）切換 baseURL 後直接使用。
- 非代理端點（管理 UI 用）使用 `/api/v1/<resource>`，遵循 [20-backend.md § 3](./20-backend.md#3-路由與-api-命名)。

## 6. 請求改寫與欄位過濾

後端**必須**在送往 OpenRouter 前改寫 Request：

| 處理 | 說明 |
| --- | --- |
| 移除 `user` 欄位原值 | 改為本平台 `user_uid`（避免將 Client 端使用者識別直接傳給 OpenRouter） |
| 注入 `metadata` | 加入 `{"ord_user_uid": ..., "ord_api_key_uid": ...}` 以便回溯 |
| 剔除不允許欄位 | 由設定檔定義 `disallowed_fields`（預設含 `route`、未授權的 `provider`） |
| 模型別名展開 | 平台可定義短別名（例 `default-fast`）對應到 OpenRouter 實際模型字串 |

Response 回傳給 Client 前：

| 處理 | 說明 |
| --- | --- |
| 保留 OpenRouter 原始 `id`、`choices`、`usage` | 保持 SDK 相容 |
| 移除內部 metadata | 不回傳後端注入的 `ord_*` 欄位 |
| **禁止**回傳任何包含 API Key 的欄位 | 即使 OpenRouter 未回傳，代碼層仍需防禦性過濾 |

## 7. 串流（Streaming）

- 支援 `stream=true`，後端以 **SSE**（`text/event-stream`）回傳，Content-Type 與 chunk 格式**必須**與 OpenRouter 相同（`data: {...}\n\n` + `data: [DONE]\n\n`）。
- 串流中途若 OpenRouter 中斷，後端**必須**送出 `event: error` chunk 後關閉連線，**禁止**靜默截斷。
- 串流端點**不**套用統一 `ApiResponse` 包裝（見 [20-backend.md § 1](./20-backend.md#1-統一-response-格式)）；但**啟動前**的錯誤（驗證、配額、白名單）**必須**以 HTTP 4xx + `ApiResponse` 回絕，**不**開啟串流。
- Client 斷線時後端**必須**取消上游 httpx stream（`response.aclose()`），避免額外 Token 計費。

## 8. 重試策略

| 情境 | 重試 | 策略 |
| --- | --- | --- |
| HTTP 5xx（非 502/504 具體指令） | ✅ | 指數退避，最多 2 次 |
| HTTP 429（rate limit） | ✅ | 依 `Retry-After` header，最多 1 次；超過仍失敗則回 429 給 Client |
| HTTP 4xx（除 429） | ❌ | 直接回傳 |
| 連線錯誤 / timeout | ✅ | 指數退避，最多 2 次 |
| Streaming 開始後 | ❌ | 開始後**禁止**重試（已有 chunk 送達 Client） |

## 9. 錯誤對應

| OpenRouter 行為 | 後端回應 HTTP | `detail` |
| --- | --- | --- |
| 400（欄位錯誤） | 400 | `invalid_request` |
| 401（API Key 無效） | 502 | `openrouter_unavailable`（不得洩漏「Key 失效」予 Client） |
| 402（餘額不足） | 502 | `openrouter_unavailable`；**必須**立即告警管理員 |
| 403（模型不可用） | 403 | `model_forbidden` |
| 404（模型不存在） | 404 | `model_not_found` |
| 429 | 429 | `rate_limited` |
| 5xx / timeout | 502 | `openrouter_unavailable` |
| 本平台配額不足 | 429 | `quota_exceeded` |
| 本平台白名單拒絕 | 403 | `model_forbidden` |

OpenRouter 原始錯誤**必須**完整寫入後端 Log（含 `X-Request-Id`），但**禁止**回傳前端。

## 10. 用量紀錄（Usage Log）

- 每次呼叫完成（含錯誤）**必須**寫入 `usage_logs` 表，欄位至少：
  - `usage_log_uid`（UUIDv7）
  - `api_key_uid`、`user_uid`
  - `model`、`provider`（若 OpenRouter 回傳）
  - `openrouter_generation_id`（如有）
  - `prompt_tokens`、`completion_tokens`、`total_tokens`
  - `cost`（USD，取自 OpenRouter `usage` 或事後查詢 `/generation`）
  - `latency_ms`
  - `status`（`success` / `error`）、`error_code`
  - `created_at`
- 串流呼叫的 Token 統計**必須**在串流結束後查詢 OpenRouter `/api/v1/generation?id=...` 補齊（OpenRouter 串流本身不夾帶最終 usage）。
- 此表屬高頻寫入，**應**加上 `(user_uid, created_at)` 與 `(api_key_uid, created_at)` 複合索引以利日報彙總。

## 11. 設定與健康檢查

- `OPENROUTER_API_BASE_URL` 預設 `https://openrouter.ai/api/v1`，**可**於 `.env` 覆寫以導向測試 / 私有 Gateway。
- `OPENROUTER_API_TIMEOUT` 預設 60（秒）；串流使用獨立 `OPENROUTER_STREAM_TIMEOUT`（預設 300 秒）。
- 後端**應**提供 `/api/v1/health/openrouter` 端點（僅限 admin），實呼低成本模型驗證金鑰與通路。

## 12. 禁止事項

- **禁止**將 OpenRouter API Key 以任何形式下發至前端或 Response。
- **禁止**在 Log 中完整列印本地金鑰明文、OpenRouter 原始錯誤的敏感欄位（若含）。
- **禁止**繞過 `OpenRouterClient` 直接 `httpx` 呼叫 OpenRouter。
- **禁止**在代理端點使用與管理 API 相同的本地金鑰（管理 UI 用登入 Cookie，代理用 `ord_*` 金鑰，兩者**必須**分離）。
