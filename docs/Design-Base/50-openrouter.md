# 50 · 模型代理整合（Model Provider）

本文件定義後端作為**模型代理層**的整合規範。v1.2 起支援多 provider：

- **OpenRouter**（外網）：以多把 Key 組成 pool,撞速率限制時 failover 到下一把。
- **Internal**（企業內地端 OpenAI-compatible server,vLLM / Ollama / TGI / LiteLLM 等）：單一 endpoint,撞速率限制時排隊等待。

兩 provider 共用同一套白名單（`models.is_active`）、SDK Key + User Token 雙因子認證、用量稽核、tier 分級；**差異只在 client 實作與速率控管行為**（詳 § 4 與 § 12）。

> OpenRouter 官方文件：https://openrouter.ai/docs

## 1. 代理原則

- **後端為唯一出口**：所有對 OpenRouter 的呼叫**必須**經由 `backend/app/clients/openrouter/`，**禁止**前端或其他服務直連。
- **OpenRouter Key 僅存後端**：OpenRouter 原生 API Key 以 **AES-256-GCM** 加密後存於 `openrouter_keys.key_ciphertext`，解密金鑰為 `ENCRYPTION_KEY`。**禁止**在 Response、Log、前端程式碼中出現明文。
- **使用者不持有 OpenRouter Key**：本平台對使用者發放的是 **SDK Key + 加密 User Token** 雙因子憑證（見 § 3），由後端換發 OpenRouter 呼叫；使用者**永遠無法**取得 OpenRouter 原生 Key。

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
- 注入 `Authorization: Bearer <解密後 OpenRouter Key>` 與必要 Header（例如 `HTTP-Referer`、`X-Title`）。
- 統一處理逾時、重試、錯誤分類。
- **禁止**在 Client 層決定業務規則（部門別、白名單、模型改寫、Key 選擇），這屬於 service 層的職責。

**依賴注入：**

```python
# backend/app/core/deps.py
async def get_openrouter_client() -> OpenRouterClient: ...
```

所有 service **必須**透過 `Depends(get_openrouter_client)` 取得 Client，**禁止**自行 `httpx.AsyncClient()`。

## 3. 本地認證（SDK Key + User Token 雙因子）

本平台代理端採 **SDK Key + User Token 雙因子** 認證，取代過去的 `ord_*` 單一金鑰設計。兩者缺一不可，且**部門必須一致**。

### 3.1 SDK Key

- 以「部門」為單位核發，代表呼叫來源的部門識別與 SDK 本身可用性。
- 一個部門可有多把 SDK Key，便於輪替與分裝（例如不同機器 / 不同環境）。
- 明文格式建議 `ordsk_<12 字 hex>_<32 字 base62 secret>`，例 `ordsk_ab12cd34ef56_<secret>`。
- DB 僅存 `argon2id` hash + 公開 prefix（`ordsk_<12 字 hex>`）；明文**僅於建立時一次性回應**。
- 呼叫端以 Header `X-SDK-Key: <明文>` 送出；後端以 prefix 候選 + argon2 比對 secret。

### 3.2 User Token（加密）

- 以個別「使用者（員工）」為單位核發。
- Payload 固定欄位（值取自 `users` + `departments`）：

  ```json
  {
    "user_uid":        "<uuid>",
    "department_uid":  "<uuid>",
    "department_code": "T000",
    "employee_id":     "00063",
    "email":           "user@df-recycle.com",
    "issued_at":       "2026-04-17T10:00:00Z"
  }
  ```

- 加密採 **AES-256-GCM**；金鑰 = `ENCRYPTION_KEY`（32 bytes base64，`.env` 注入），nonce 12 bytes 隨機。
- 輸出格式：`base64url(nonce || ciphertext || tag)`。
- 由 admin 於後台 `POST /api/v1/users/{user_uid}/tokens` 產生並**一次性**顯示；admin 以帶外管道（口頭 / 即時通訊）交付使用者設定於 SDK 環境變數。
- Token **不**落地 DB（payload 可由 `users` 重建），但**必須**提供撤銷端點寫入 `user_tokens_revocations`；驗證時以 `token.issued_at >= user.latest_revocation.revoked_issued_at` 比對。

### 3.3 OpenRouter Key（後端持有）

- OpenRouter 原生 API Key 綁定在一個「部門」下（見資料表 `openrouter_keys`）。
- 同一部門**典型 3 把**（負載平衡、Rate Limit 輪替、成本歸戶）。
- 明文以 **AES-256-GCM** 加密存於 `openrouter_keys.key_ciphertext`（`nonce||ciphertext||tag`）。
- 建立後**禁止**再取得明文；僅回傳 `key_prefix` / `key_last4` 作識別。
- Key 選擇策略：給定 `department_uid`，從 `is_active=TRUE AND is_deleted=FALSE` 中 **random choice**；401 時重試下一把，單次呼叫最多嘗試 N 把（N = 該部門 active key 數，上限 5）。

## 4. 呼叫流程

```
SDK（使用者應用）
  │  Headers:  X-SDK-Key, X-User-Token
  │  Body:     { model, text, images }
  ▼
[backend] POST /api/v1/model/chat                    (canonical,v1.2)
          POST /api/v1/model/openrouter/chat         (deprecated alias,行為相同)
  │  1. 解析 X-SDK-Key → argon2 比對 sdk_api_keys → 得 department_uid (SDK)
  │  2. 解密 X-User-Token → payload → 驗 revocation → 取 department_uid (User)
  │  3. 若 SDK.department_uid != User.department_uid → 401 unauthorized
  │  4. 驗 model 白名單（DB `models.is_active`）；未通過則 403 model_forbidden
  │  5. 依 model.provider 分流:
  │       openrouter:依 department_uid 隨機選一把 active Key,過 rate limiter
  │                  (per-Key),撞限額切下一把(failover),全撞牆 → 429 rate_limited
  │       internal:  過 rate limiter(per-Provider 全域),撞限額排隊;超過
  │                  RATE_WAIT_TIMEOUT → 429 internal_busy
  │  6. 改寫 Request → POST 對應 provider /chat/completions
  │  7. 取得 Response;OR 失敗(401)切下一把 Key;internal 5xx → 502 internal_unavailable
  │  8. 回 Client 後以 BackgroundTasks 寫 usage_logs(internal 的 openrouter_key_uid=NULL)
  ▼
SDK
```

## 5. 代理端點規範

- v1.2 起代理 canonical path 為 **`POST /api/v1/model/chat`**;所有 provider 共用,後端依 `model_key` 對應的 `models.provider` 自動分流。
- 舊路徑 `POST /api/v1/model/openrouter/chat` 保留為 **deprecated alias**（內部 forward 到同 handler;Swagger 標 `deprecated: true`),**至少保留至 v1.4**。
- Request 採**平台簡化 schema**（`{ model, text, images }`),由後端改寫為各 provider 的 chat/completions 格式;目前 OpenRouter 與 Internal 都是 OpenAI-compatible,改寫邏輯一致。
- 本版本**不**做 OpenAI passthrough;後續版本若需擴充新 action,於同 `/model/` 命名空間下新增。
- 非代理端點（管理 UI 用）使用 `/api/v1/<resource>`,遵循 [20-backend.md § 3](./20-backend.md#3-路由與-api-命名)。

## 6. 請求改寫與欄位過濾

後端**必須**在送往 OpenRouter 前改寫 Request：

| 處理 | 說明 |
| --- | --- |
| Schema 展開 | `{ model, text, images }` → `messages:[{role:"user", content:[{type:"text", text}, {type:"image_url", image_url:{url}}]}]` |
| 白名單檢查 | 依 `models.is_active` DB 查詢（`models WHERE model_key=? AND is_active=TRUE AND is_deleted=FALSE`）；未通過或不存在均回 403 `model_forbidden`,不揭露差異 |
| 影片輸入 | 本版本**禁止**（`videos` 若出現 → 400 `feature_not_supported`） |
| 模型別名展開 | 可定義短別名對應 OpenRouter 實際模型字串（本版本不實作） |

Response 回傳給 Client 前：

| 處理 | 說明 |
| --- | --- |
| 保留 OpenRouter 原始 `id`、`choices`、`usage` | 便於 Client 後續引用 |
| 移除內部識別欄位 | **禁止**回傳 `department_uid`、`user_uid`、`openrouter_key_uid` 等內部資訊 |
| **禁止**回傳任何包含 API Key 的欄位 | 即使 OpenRouter 未回傳，代碼層仍需防禦性過濾 |

## 7. 串流（Streaming）

本版本（v1）**不**實作串流；後續版本若擴充，規範如下（預留）：

- 支援 `stream=true`，後端以 **SSE**（`text/event-stream`）回傳，Content-Type 與 chunk 格式**必須**與 OpenRouter 相同（`data: {...}\n\n` + `data: [DONE]\n\n`）。
- 串流中途若 OpenRouter 中斷，後端**必須**送出 `event: error` chunk 後關閉連線，**禁止**靜默截斷。
- 串流端點**不**套用統一 `ApiResponse` 包裝；但**啟動前**的錯誤（驗證、白名單、OpenRouter 拒絕）**必須**以 HTTP 4xx + `ApiResponse` 回絕，**不**開啟串流。
- Client 斷線時後端**必須**取消上游 httpx stream（`response.aclose()`），避免額外 Token 計費。

## 8. 重試策略

| 情境 | 重試 | 策略 |
| --- | --- | --- |
| HTTP 401（Key 失效） | ✅ | 換下一把同部門 active Key；最多嘗試 N 把（N = 該部門 active key 數，上限 5） |
| HTTP 5xx（非 502/504 具體指令） | ✅ | 指數退避，最多 2 次 |
| HTTP 429（rate limit） | ✅ | 依 `Retry-After` header，最多 1 次；超過仍失敗則回 429 給 Client |
| HTTP 4xx（除 401、429） | ❌ | 直接回傳 |
| 連線錯誤 / timeout | ✅ | 指數退避，最多 2 次 |
| Streaming 開始後 | ❌ | 開始後**禁止**重試（已有 chunk 送達 Client） |

## 9. 錯誤對應

| OpenRouter 行為 | 後端回應 HTTP | `detail` |
| --- | --- | --- |
| 400（欄位錯誤） | 400 | `invalid_request` |
| 401（單把 Key 失效） | — | 嘗試下一把；全部失敗 → 502 `openrouter_unavailable` |
| 402（餘額不足） | 502 | `openrouter_unavailable`；**必須**立即告警管理員 |
| 403（模型不可用） | 403 | `model_forbidden` |
| 404（模型不存在） | 404 | `model_not_found` |
| 429 | 429 | `rate_limited` |
| 5xx / timeout | 502 | `openrouter_unavailable` |
| 本平台白名單拒絕 | 403 | `model_forbidden` |
| 影片輸入（本版本未支援） | 400 | `feature_not_supported` |
| 模型同步進行中 | 425 | `sync_in_progress` |
| 模型同步距上次 < 10 min | 425 | `sync_throttled` |
| 刪除 model_tier 仍被引用 | 400 | `tier_in_use` |
| OR 所有 active Key 撞 RPM / 最小間隔 | 429 | `rate_limited` |
| Internal 排隊超過 RATE_WAIT_TIMEOUT | 429 | `internal_busy`(`data.retry_after_seconds`) |
| Internal server 連線失敗 / 5xx | 502 | `internal_unavailable` |
| `models.provider=internal` 但 env 未設 base_url | 500 | `provider_misconfigured` |
| POST `/api/v1/models` 傳 `provider=openrouter` | 400 | `provider_not_allowed`(openrouter 必須走同步) |

OpenRouter 原始錯誤**必須**完整寫入後端 Log（含 `X-Request-Id`），但**禁止**回傳前端。

## 10. 用量紀錄（Usage Log）

- 每次呼叫完成（含錯誤）**必須**寫入 `usage_logs` 表，欄位至少：
  - `usage_log_uid`（UUIDv7）
  - `user_uid`、`department_uid`、`openrouter_key_uid`
  - `model`
  - `openrouter_generation_id`（如有）
  - `prompt_tokens`、`completion_tokens`、`total_tokens`
  - `cost_usd`（USD，取自 OpenRouter `usage`）
  - `latency_ms`
  - `status`（`success` / `error`）、`error_code`
  - `request_content`（JSONB，**完整**原始 body;base64 影像以原文保留,供管理端分析使用者實際消費模型的方式)
  - `response_summary`（JSONB，首段文字 ≤ 500 字 + `usage`）
  - `created_at`
- 寫入**必須**於 response 回給 Client **之後**執行（`BackgroundTasks` 或 `asyncio.create_task`），避免拖慢呼叫。
- 此表屬高頻寫入，**應**加上 `(department_uid, created_at)`、`(user_uid, created_at)`、`(model, created_at)` 複合索引以利日報彙總。

## 11. 設定與健康檢查

### OpenRouter

- `OPENROUTER_API_BASE_URL` 預設 `https://openrouter.ai/api/v1`,**可**於 `.env` 覆寫以導向測試 / 私有 Gateway。
- `OPENROUTER_API_TIMEOUT` 預設 60（秒）;串流使用獨立 `OPENROUTER_STREAM_TIMEOUT`（預設 300 秒,本版本未啟用)。
- 後端**應**提供 `/api/v1/health/openrouter` 端點（僅限 admin),實呼低成本模型驗證金鑰與通路。

### Internal LLM(v1.2)

- `INTERNAL_LLM_BASE_URL`:留空 = 停用本地模型;設值後形如 `http://vllm.corp.local:8000/v1`。
- `INTERNAL_LLM_API_KEY`:可空(內網信任)或地端 server 設定的 token。
- `INTERNAL_LLM_REQUEST_TIMEOUT` 預設 120(秒)。
- `INTERNAL_LLM_RPM_LIMIT` 預設 60(0 = 不限);`INTERNAL_LLM_MIN_REQUEST_INTERVAL_MS` 預設 0;`INTERNAL_LLM_RATE_WAIT_TIMEOUT` 預設 60(秒)。
- v1.2 限 `UVICORN_WORKERS=1`(in-memory rate limiter 不跨 worker);multi-worker 需升級 Redis-backed limiter(v1.3)。

## 12. 禁止事項

- **禁止**將 OpenRouter API Key 以任何形式下發至前端或 Response。
- **禁止**在 Log 中完整列印 SDK Key 明文、User Token 明文、OpenRouter Key 明文；必要時只保留前後 4 字元。
- **禁止**繞過 `OpenRouterClient` 直接 `httpx` 呼叫 OpenRouter。
- **禁止**在代理端點接受管理 Cookie / Access Token；管理端點接受 `X-SDK-Key` / `X-User-Token`（兩者**必須**分離）。
- **禁止**於 Response 中分別揭露「SDK Key 無效」「User Token 解密失敗」「部門不一致」中的具體項目；一律回 401 `unauthorized`。

## 13. 模型同步

自 v1.1 起,OpenRouter 模型清單與 Key 餘額採 **DB 驅動**,取代過去的 `ALLOWED_MODELS` 環境變數白名單。模型資料落地於 `models` 表(`is_active` 控制白名單),分級資料落地於 `model_tiers` 表(管理 UI 顯示徽章與分類用)。

同步由 admin 於後台 `POST /api/v1/models/sync` 觸發,流程要點如下:

- **並發控制**:後端以 `pg_try_advisory_xact_lock(LOCK_KEY_MODELS_SYNC)` 取得交易鎖;失敗即回 425 `sync_in_progress`,**禁止**排隊等候。
- **限流(throttle)**:檢查 `max(models.last_synced_at)`,距今 < 10 分鐘回 425 `sync_throttled`,response `data.retry_after_seconds` 提示前端倒數;前端**應**將上次成功時間寫入 `localStorage` 以利重新進頁面時續算冷卻。
- **模型 UPSERT**:以任一把 `is_active=TRUE` 的 OpenRouter Key 呼叫 `GET /models`,對 `model_key` 做 UPSERT(v1.1 此欄稱 `openrouter_model_id`,v1.2 改名)— 新模型 `is_active=TRUE` 並依規則自動匹配 `tier_key`;既有僅更新元資料(`name` / `description` / `context_length` / `pricing` / `modality`),**不覆寫** `is_active` 與 `tier_key`;DB 有但 API 無者(僅針對 `provider='openrouter'` 的 row)標記 `is_active=FALSE`(軟下架,保留歷史)。
- **餘額同步(best-effort)**:對每把 `is_active=TRUE` Key 以該 Key 自身呼叫 `GET /auth/key`,回填 `credits_used_usd` / `credits_limit_usd` / `credits_is_free_tier` / `credits_synced_at`;個別 Key 失敗**不**整批 rollback,僅累計 `credits_failed` 計數於 response。
- **稽核**:寫入 `action="sync_models_and_credits"`,`detail` 包含 added / updated / deactivated / credits_synced / credits_failed。

詳細流程、錯誤對照與 SQL 細節參見 [../Tasks/v1.1/propose-v1.1.0.md § 6](../Tasks/v1.1/propose-v1.1.0.md)。

## 14. 速率限制(v1.2)

平台代理層採**主動限速**,避免被動撞 OR 429 或打爆地端 GPU server。兩設定疊加,取較大等待時間:

| 設定 | 儲存位置 | 適用範圍 |
| --- | --- | --- |
| `rpm_limit` | `openrouter_keys` 表 / env `INTERNAL_LLM_RPM_LIMIT` | 60 秒滾動視窗最大呼叫數;`0` = 不限 |
| `min_request_interval_ms` | 同上 | 連續兩次呼叫最短間隔;`0` = 不限 |

**撞限額行為**:

- **OpenRouter**:per-Key 計數;撞限額**換下一把 active Key**(failover,不 sleep);全撞牆 → 429 `rate_limited`。
- **Internal**:per-Provider 全域計數;撞限額**等待**至下一個 slot;等待超過 `INTERNAL_LLM_RATE_WAIT_TIMEOUT` → 429 `internal_busy`(回 `data.retry_after_seconds`)。

實作位置:[`backend/app/services/rate_limit.py`](../../backend/app/services/rate_limit.py);詳細演算法見 [../Tasks/v1.2/propose-v1.2.0.md § 6](../Tasks/v1.2/propose-v1.2.0.md)。

## 15. 內部 Provider(v1.2)

支援 OpenAI-compatible 地端 server(vLLM / Ollama / TGI / LiteLLM 等):

- **模型登記**:admin 透過 `POST /api/v1/models`(僅接受 `provider=internal`)手動建立;openrouter 模型仍須走同步流程。
- **白名單檢查**:沿用 `models.is_active`,與 openrouter 模型共用同一張表。
- **Client**:`backend/app/clients/internal/client.py`,OpenAI-compatible `/chat/completions`。
- **連線設定**:`INTERNAL_LLM_BASE_URL` / `INTERNAL_LLM_API_KEY`(env;單台 server)。
- **多台 server**:v1.2 不支援(留 v1.3 `internal_providers` 表)。
- **Usage log**:`openrouter_key_uid=NULL`,`cost_usd=0`(本版本不估算 internal cost)。
