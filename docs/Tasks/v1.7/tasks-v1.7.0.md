# Tasks v1.7.0

## 版本資訊

- 前置依賴:v1.2 多 provider 代理(`/model/chat`、Key failover、rate limiter、usage_logs)已完成。
- 本版本範圍:新增 **OpenRouter 串流(SSE)回應端點** `POST /api/v1/model/chat/stream`,邊收邊解析,簡化為只含 `{ id, content }` 的 SSE 轉給呼叫端(不外露 OpenRouter 內部欄位)。
- 對齊的 Design-Base 章節:
  - [50-openrouter.md § 4 呼叫流程](../../Design-Base/50-openrouter.md)
  - [50-openrouter.md § 7 串流（Streaming）](../../Design-Base/50-openrouter.md)
  - [50-openrouter.md § 8 重試策略](../../Design-Base/50-openrouter.md)
  - [50-openrouter.md § 9 錯誤對應](../../Design-Base/50-openrouter.md)
  - [50-openrouter.md § 10 用量紀錄](../../Design-Base/50-openrouter.md)
  - [50-openrouter.md § 11 設定與健康檢查](../../Design-Base/50-openrouter.md)
  - [20-backend.md § 1 統一 Response 格式（串流端點例外）](../../Design-Base/20-backend.md)
  - [90-task-spec.md § 4 / § 5](../../Design-Base/90-task-spec.md)
- 母本 propose:[`propose-v1.7.0.md`](./propose-v1.7.0.md)(包含設計推導與決議過程)

> 本 Tasks 為**實作契約**;設計理由與替代方案請參考母本 propose。內容若與 propose 衝突,以本檔為準。

## Definition of Done

### 後端

- [ ] `POST /api/v1/model/chat/stream` 可用:OpenRouter 模型回應以 `text/event-stream` 逐 chunk 串流,**簡化格式** `data: {"id":"...","content":"..."}\n\n` … `data: [DONE]`(OpenRouter 內部欄位不外露)。
- [ ] 開串流**前**的錯誤(驗證 / 白名單 / provider=internal / Key 全失敗)以 HTTP 4xx/5xx + `ApiResponse` 回絕,**不**開串流。
- [ ] 開串流**後**不重試;呼叫端斷線時取消上游 httpx stream(`aclose`)。
- [ ] 每次串流(含成功 / 中斷 / 錯誤)寫入一筆 `usage_logs`,含完整 `output_text` 與 `usage`(若有)。
- [ ] `provider=internal` 的模型呼叫串流端點回 `400 feature_not_supported`。
- [ ] Swagger 可於 `/api/docs` 查閱新端點(含「回應為 SSE、非 ApiResponse」之描述)。
- [ ] 單元 / 整合測試覆蓋:成功串流、pre-stream 錯誤回 ApiResponse、failover、斷線記帳。
- [ ] `.env.example` 與 `.env` 同步新增 `OPENROUTER_STREAM_TIMEOUT`。
- [ ] SDK 對外文件 / `docs/INTEGRATION.md` 新增串流呼叫與 SSE 解析說明。

### 前端

- [ ] 無(chat 由 SDK 直呼,管理後台不呼叫;本版本無前端改動)。

## 功能設計

### A. 端點 `POST /api/v1/model/chat/stream`

- 掛於既有 `model` router([`api/v1/model_chat.py`](../../../backend/app/api/v1/model_chat.py)),沿用 `SdkCallerDep`(X-SDK-Key + X-User-Token)。
- Request body 沿用既有 `ChatRequest`(`model / text / images / videos / tools`);**不**新增 `stream` 欄位(端點本身即代表串流)。`videos` 非空仍回 400。
- handler 流程:
  1. 取得 service 的 async generator `run_chat_stream(...)`。
  2. **Prime**:`await agen.__anext__()` 取第一個 chunk。
     - 若於此前拋 `AppError`(pre-stream 錯誤)→ 由既有 exception handler 轉 `ApiResponse`(尚未送 200)。
     - 若 `StopAsyncIteration`(空串流)→ 回只含 `data: [DONE]\n\n` 的串流。
  3. 成功取得第一個 chunk → 建立 `StreamingResponse(media_type="text/event-stream")`,body 先 yield 第一個 chunk 再續傳其餘;header 加 `Cache-Control: no-cache`、`X-Accel-Buffering: no`。

### B. Client 串流方法 `OpenRouterClient.stream_chat_completion()`

- 位置:[`clients/openrouter/client.py`](../../../backend/app/clients/openrouter/client.py)。
- 以 `self._client.stream("POST", f"{base}/chat/completions", json=payload, headers=headers, timeout=httpx.Timeout(OPENROUTER_STREAM_TIMEOUT))` 開連線。
- **先**判斷 `resp.status_code`(`await resp.aread()` 取錯誤 body),沿用既有錯誤映射:401→`OpenRouterAuthError`、403→`Forbidden`、404→`ModelNotFound`、429→`RateLimit`、≥400→`OpenRouterError`;200 才 `async for line in resp.aiter_lines(): yield line`。
- 為 async generator;狀態碼錯誤在 yield 第一行**之前**拋出,供 service failover 判斷。

### C. Service 串流邏輯 `run_chat_stream()` + `_stream_openrouter()`

- 位置:[`services/proxy.py`](../../../backend/app/services/proxy.py)。
- `run_chat_stream()`(async generator):`videos` → 400;白名單檢查;`provider != "openrouter"` → 400 `feature_not_supported`;`payload = _rewrite_request(...)` 後加 `payload["stream"]=True`、`payload["stream_options"]={"include_usage":True}`;委派 `_stream_openrouter()` 並 `yield` 其輸出。
- `_stream_openrouter()`(async generator):
  - 沿用 `pick_random_active` + `get_limiter`(`wait_timeout=0`)的 Key failover 迴圈(最多 `_MAX_RETRIES`)。
  - 對每把 Key:`candidate = client.stream_chat_completion(payload, api_key=raw_key)`;`first = await candidate.__anext__()` 試連:
    - `OpenRouterAuthError` → `aclose` 換下一把;`OpenRouterError`(連線 / 5xx)→ 換下一把。
    - `ModelNotFound`/`Forbidden`/`RateLimit` → 記 error log + 拋對應 `AppError`(pre-stream)。
  - 成功取得 `first` = **commit point**:relay 階段對每行呼叫 `_simplify_sse_line` —— 解析後**只吐 `{ id, content }`**(空行 / keep-alive 註解 / 無文字的 role·結束·usage chunk 不轉發),同時累積 `delta.content` / `usage` / `id` 供記帳。
  - 全部失敗(未連上)→ `rate_limited`(429,全撞速率) / `openrouter_unavailable`(502)。
  - `finally`:`await agen.aclose()` 關上游;合成 `resp` dict 呼叫 `schedule_usage_log`(串完 `status=success`;中斷 / 上游錯 `status=error`,寫已累積部分內容)。
  - 上游中途出錯:OpenRouter 的 error chunk(無 content)由 `_simplify_sse_line` 轉成 `data: {"error":"upstream_error"}` 並標記 `state["error"]`(→ usage_log status=error);後端側無預警斷線(`OpenRouterError`)則補送 `data: {"error":"openrouter_unavailable"}` + `data: [DONE]`。皆不靜默截斷,且不外露 OpenRouter 原始錯誤明細。

### D. 設定

- [`core/config.py`](../../../backend/app/core/config.py) 新增 `OPENROUTER_STREAM_TIMEOUT: int = 300`。
- [`.env.example`](../../../.env.example) `# --- OpenRouter ---` 區段新增同名 key。

## 敏感欄位過濾表

| 欄位 | 來源 | 處理 |
| --- | --- | --- |
| 解密後 OpenRouter Key | 後端解密 | **禁止**出現於任何 SSE chunk / error chunk / response;只可進後端 Log 前後 4 字元 |
| `department_uid` / `user_uid` / `openrouter_key_uid` / `provider` / `cost` / `usage` | 內部 | 串流只回 `{ id, content }`;OpenRouter 內部欄位(供應商 / 成本 / 路由 / role / finish_reason / usage)一律剝除不外露 |
| OpenRouter 原始錯誤明細 | 上游 | 完整寫後端 Log(含 X-Request-Id);回呼叫端僅限 OR 原生 error chunk,不附加內部資訊 |

## 錯誤處理對照表

| 情境 | 時機 | HTTP / 行為 | detail |
| --- | --- | --- | --- |
| SDK Key / User Token 無效 / 部門不一致 | pre-stream | 401 + ApiResponse | `unauthorized` |
| `videos` 非空 | pre-stream | 400 + ApiResponse | `feature_not_supported` |
| provider=internal | pre-stream | 400 + ApiResponse | `feature_not_supported` |
| 模型未過白名單 | pre-stream | 403 + ApiResponse | `model_forbidden` |
| OR 404 / 403 / 429 | pre-stream | 404 / 403 / 429 + ApiResponse | `model_not_found` / `model_forbidden` / `rate_limited` |
| 單把 Key 401 | pre-stream | 換下一把;全失敗 → 502 | `openrouter_unavailable` |
| 所有 active Key 撞速率 | pre-stream | 429 + ApiResponse | `rate_limited` |
| OR 5xx / 連線失敗(未收 chunk) | pre-stream | 502 + ApiResponse | `openrouter_unavailable` |
| 上游中途中斷 / 出錯(已收 chunk) | in-stream | 轉發 error chunk + 關閉,不重試 | usage_log `error_code=openrouter_unavailable` |
| 呼叫端斷線 | in-stream | `aclose` 上游 | usage_log `error_code=stream_incomplete`(記部分內容) |

> in-stream 的 `error_code` 為**內部** `usage_logs` 欄位值(供後台篩選),非回給呼叫端的 HTTP detail —— 呼叫端此時已收到 200 + 部分串流。`stream_incomplete` 為本版新增,專指「呼叫端中途斷線」,與「上游掛掉」(`openrouter_unavailable`)區分。

## 用量與稽核

- 對齊 [50-openrouter.md § 10](../../Design-Base/50-openrouter.md):relay 逐 chunk 累積 `output_text` 與 `usage`/`id`,串流結束於 `finally` 以 `schedule_usage_log`(背景 task、獨立 session)寫入。`latency_ms` 以請求起算到串流結束計。`used_tools` 由請求快照推導(同非串流)。
- 本版無管理端異動操作,無稽核 Log 變更。

## 交付物清單

- 後端檔案:
  - 修改 [`backend/app/clients/openrouter/client.py`](../../../backend/app/clients/openrouter/client.py)(加 `stream_chat_completion`)
  - 修改 [`backend/app/services/proxy.py`](../../../backend/app/services/proxy.py)(加 `run_chat_stream` / `_stream_openrouter` / SSE 累積 helper)
  - 修改 [`backend/app/api/v1/model_chat.py`](../../../backend/app/api/v1/model_chat.py)(加串流端點)
  - 修改 [`backend/app/core/config.py`](../../../backend/app/core/config.py)(加 `OPENROUTER_STREAM_TIMEOUT`)
- 前端檔案:無(消費端為 SDK)。
- Migration:無(不改 DB schema)。
- 環境變數:`OPENROUTER_STREAM_TIMEOUT`(預設 300)。
- 文件:更新 [50-openrouter.md § 7](../../Design-Base/50-openrouter.md);更新 SDK 對外文件 / `docs/INTEGRATION.md`。

## 測試重點

- 成功串流:mock OpenRouter SSE,驗證逐 chunk 簡化為 `{ id, content }` + `[DONE]`,且 usage_log 寫入完整文字與 usage。
- pre-stream 錯誤:provider=internal / 白名單失敗 / 全 Key 撞速率 → 回 `ApiResponse` 且 **未** 開串流。
- failover:第一把 Key 401 → 換第二把成功。
- 斷線:消費端中途關閉 → 上游 `aclose` 被呼叫、usage_log 記 status=error + 部分內容。
