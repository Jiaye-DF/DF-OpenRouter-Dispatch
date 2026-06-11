[//]: # (此檔為 v1.7 任務提案,實作前先由使用者確認範圍與設計取捨。)

# Propose v1.7.0 · 串流（SSE）回應支援

> 此為 **proposal**(規劃草案),確認後即轉為正式 `tasks-v1.7.0.md`。
>
> 對應母本:[v1.6 部門+SDK Key 管理整合 + 後台導引動線清理](../v1.6/propose-v1.6.0.md)。

## 1. 目標

讓代理端支援**串流回應**:SDK 呼叫後,模型生成的內容以 **SSE（Server-Sent Events）** 一段一段即時回傳,而非等整段生成完才一次回。對齊 [50-openrouter.md § 7](../../Design-Base/50-openrouter.md)(該章原為「預留」,本版落實)。

核心是「**邊收邊轉發**」:後端把 OpenRouter `stream=true` 回的 SSE chunk **解析後簡化**為 `{ id, content }` 再轉給 SDK(`data: {"id":"...","content":"..."}\n\n` … `data: [DONE]`),OpenRouter 內部欄位(provider / cost / 路由 / usage 等)不外露。

> 註:原規劃為「原樣轉發 OpenRouter SSE」,實測發現原始 chunk 會連 `provider` / `cost` 等內部欄位一起漏給 SDK,故改為簡化格式(對齊非串流端點只回純文字的精簡原則)。詳見 § 9 決議。

**這不是上傳功能**:串流是「輸出」方向(模型 → SDK),與檔案 / 影片上傳(輸入方向,屬 S3 那條獨立路線)無關。影片輸入維持本版本不支援。

## 2. 動機

- 現行 [`POST /api/v1/model/chat`](../../../backend/app/api/v1/model_chat.py) 是「等 OpenRouter 把整段答案生完 → 一次回整包」。長回答 / 慢模型時,呼叫端會乾等數秒到數十秒畫面無回饋。
- 串流可大幅改善體感:第一個 token 通常 < 1 秒就回,呈現「打字機」效果,適合聊天介面與要即時呈現的長輸出。
- OpenRouter 原生支援 `stream=true`,且為 OpenAI-compatible SSE;後端只需做轉發層,不需自行重組協定。

## 3. 範圍

### In Scope

**後端**:

- 新增串流端點 **`POST /api/v1/model/chat/stream`**(canonical;與非串流 `/model/chat` 分開,見 § 5.1)。
- `OpenRouterClient` 新增串流方法 `stream_chat_completion()`:以 `httpx.AsyncClient.stream()` 開連線,**先檢查 HTTP 狀態碼**(供 failover 判斷),200 才逐行 `yield` SSE 內容。
- `proxy.py` 新增 `run_chat_stream()` + `_stream_openrouter()`:沿用既有 Key 隨機挑選 + rate limiter + failover 邏輯,但「commit point」改為「成功連上、收到第一個 chunk」之前;之後不重試(對齊 [§ 8](../../Design-Base/50-openrouter.md) 「Streaming 開始後禁止重試」)。
- 用量紀錄:relay 過程累積 `delta.content` 與 `usage`,串流結束(或中斷)後於 `finally` 以 `schedule_usage_log` 寫入 `usage_logs`(對齊 [§ 10](../../Design-Base/50-openrouter.md))。
- 新增環境變數 `OPENROUTER_STREAM_TIMEOUT`(預設 300 秒,[§ 11](../../Design-Base/50-openrouter.md) 已預留命名)。

**文件**:

- 更新 [50-openrouter.md § 7](../../Design-Base/50-openrouter.md):由「預留」改為「正式規格」,補錯誤對照與記帳時機。
- 本檔(propose)→ 確認後產出 `docs/Tasks/v1.7/tasks-v1.7.0.md`。
- SDK 對外文件 / `docs/INTEGRATION.md`:新增串流端點的呼叫方式與 SSE 解析說明(對外 API 鏈路異動,須連帶更新)。

### Out of Scope

- **Internal provider 串流**:本版本只支援 `provider=openrouter`;internal 模型走串流端點先回 `400 feature_not_supported`,留待後續版本(internal client 雖同為 OpenAI-compatible,但其「failover + 排隊等待」與串流 commit point 的交互需另行設計)。
- **前端 UI 串流呈現**:目前 chat 由 SDK 直呼,管理後台不呼叫 chat;前端 [`lib/api/client.ts`](../../../frontend/src/lib/api/client.ts) 的 `await res.json()` 無法處理 SSE,但本版本不需前端改動。
- **檔案 / 影片上傳、S3 儲存**:屬另一條獨立路線(見 image-storage roadmap),不在本版本。
- **function calling / 會回 `tool_calls` 的串流**:沿用現況未開放;server 端工具(如 web search)若於串流中回純文字 delta 則自然支援。
- **非串流端點移除或合併**:`/model/chat` 維持不動。
- **Session / 對話記憶系統**:未來可能新增「多輪對話記憶」需求,屆時 chat 輸入會從本版的「單輪 `text` / `images`」演進為「多輪 `messages[]`」。本版本**不做**,但設計串流時保留「日後 payload 改帶多輪 messages」的彈性(串流轉發層與記帳不綁定單輪假設)。

## 4. 流程概要

```
SDK ──▶ POST /api/v1/model/chat/stream   Headers: X-SDK-Key, X-User-Token
                                          Body:    { model, text, images, tools }
  │
  │  [開串流前 — 失敗一律 4xx + ApiResponse,不開串流]
  │   1. 驗 SDK Key + User Token(沿用 SdkCallerDep)
  │   2. videos 非空 → 400 feature_not_supported
  │   3. 白名單檢查;provider != openrouter → 400 feature_not_supported
  │   4. payload 加 stream=true、stream_options={include_usage:true}
  │   5. Key failover 迴圈:挑 active Key → rate limiter(wait_timeout=0)
  │        撞限額 → 換下一把;401 → 換下一把
  │        404/403/429 → 對應 AppError(不開串流)
  │        全部撞速率 → 429 rate_limited;曾連線仍失敗 → 502 openrouter_unavailable
  │   6. 成功連上(HTTP 200、收到第一個 chunk)= commit point
  │
  ▼  [開串流後 — text/event-stream,不套 ApiResponse,禁止重試]
SDK ◀── data: {"id":"...","content":"以"}\n\n   (簡化:只回 id + content)
     ◀── data: {"id":"...","content":"下是用"}\n\n
     ◀── data: [DONE]\n\n
        (keep-alive 註解 / usage / provider / cost 等內部 chunk 不轉發)
  │
  └─ finally:累積的 content + usage → schedule_usage_log
       (串完 → status=success;中途中斷 / 上游錯 → status=error,記部分內容)
```

**「開串流前錯誤仍回 ApiResponse」如何實作**:端點先 prime async generator 一次(`__anext__`)。所有開串流前的檢查與 failover 都在「吐出第一個 chunk」之前完成,失敗以 `AppError` 拋出,由既有 exception handler 轉成 `ApiResponse`(此時尚未送出 200);成功拿到第一個 chunk 後才建立 `StreamingResponse` 開始串。

## 5. 設計重點

### 5.1 端點:為何另開 `/model/chat/stream` 而非 `/model/chat` 加 `stream` 旗標

| | A. 同端點 + `stream:true` | B. 另開 `/model/chat/stream`(採用) |
| --- | --- | --- |
| 回應契約 | 一隻端點兩種 content-type(JSON `ApiResponse` / SSE) | 一隻端點一種契約 |
| Swagger | response schema 不確定,難描述 | 各自清楚 |
| 錯誤語意 | 開串流前 / 後雙重語意塞同一隻 | 天然分離 |
| 與本平台契約 | 與「統一 `ApiResponse`」哲學衝突 | 一致;[§ 7](../../Design-Base/50-openrouter.md) 本即以「串流端點」描述 |

消費端為自家 SDK,不需遷就 OpenAI 的 `stream:true` 同端點慣例;故採 **B**。Request body 沿用既有 `ChatRequest`(`model / text / images / tools`,`videos` 仍 400),**不**新增 `stream` 欄位(端點本身即代表串流)。

### 5.2 回應格式:簡化 SSE(只回 id + content)

- `Content-Type: text/event-stream`,**不**套 `ApiResponse` 包裝([§ 5](../../Design-Base/90-task-spec.md) 串流端點例外)。
- 逐 chunk 解析後**只回 `{ id, content }`**:`data: {"id":"<gen-id>","content":"<本段文字>"}\n\n` … `data: [DONE]\n\n`。OpenRouter 原始欄位(`provider` / `cost` / `model` 路由 / `role` / `finish_reason` / `usage`)**一律剝除**;`: OPENROUTER PROCESSING` keep-alive 與無文字的 chunk 不轉發。對齊非串流端點只回純文字的精簡原則,並避免洩漏成本 / 供應商等內部資訊。
- `stream_options={include_usage:true}` 由後端注入,確保最後一個 chunk 帶 `usage` 供**記帳**(寫 usage_logs);usage **不**外露給 SDK。

### 5.3 敏感欄位過濾

- 串流只回 `{ id, content }`,OpenRouter 內部欄位(`provider` / `cost` / 路由 / `usage`)與本平台內部識別(`department_uid` / `user_uid` / `openrouter_key_uid`)一律剝除;程式仍須確保 **不**在 SSE 或錯誤 chunk 中帶入解密後的 OpenRouter Key 或內部 uid。
- OpenRouter 原始錯誤完整寫後端 Log(含 `X-Request-Id`),**不**额外回傳內部資訊。

## 6. 錯誤處理對照表

| 情境 | 時機 | 回應 |
| --- | --- | --- |
| SDK Key / User Token 無效 / 部門不一致 | 開串流前 | `401 unauthorized`(ApiResponse) |
| `videos` 非空 | 開串流前 | `400 feature_not_supported`(ApiResponse) |
| 模型未過白名單 | 開串流前 | `403 model_forbidden`(ApiResponse) |
| 模型 provider=internal | 開串流前 | `400 feature_not_supported`(ApiResponse;本版本未支援 internal 串流) |
| 單把 OR Key 401 | 開串流前 | 換下一把;全部失敗 → `502 openrouter_unavailable` |
| OR 404 / 403 / 429 | 開串流前 | `404 model_not_found` / `403 model_forbidden` / `429 rate_limited` |
| 所有 active Key 撞 RPM / 最小間隔 | 開串流前 | `429 rate_limited` |
| OpenRouter 5xx / 連線失敗(尚未收到 chunk) | 開串流前 | `502 openrouter_unavailable` |
| 上游中途中斷 / 出錯(已收到 chunk) | 開串流後 | **不**重試;依 [§ 7](../../Design-Base/50-openrouter.md) 不可靜默截斷(見 § 9 待確認 (2));usage_log 記 status=error |
| 呼叫端斷線 | 開串流後 | 取消上游 httpx stream(`aclose`),避免額外 token 計費;usage_log 記部分內容 |

## 7. 用量紀錄（usage_logs）

對齊 [50-openrouter.md § 10](../../Design-Base/50-openrouter.md):

- relay 過程逐 chunk 解析,累積 `choices[].delta.content` 為完整輸出文字,並擷取最後一個 chunk 的 `usage` 與首個 chunk 的 `id`(generation id)。
- 串流結束(`data: [DONE]`)後於 `finally` 合成 `resp` 物件,沿用既有 `schedule_usage_log` / `_summarize_response`(`output_text` 存完整文字、保留 `usage`、`used_tools` 由請求快照推導)。
- `latency_ms` 以「請求起算到串流結束」計。
- 串完 → `status=success`;中途中斷 / 上游錯 / 呼叫端斷線 → `status=error` 且寫入已累積的部分內容(便於稽核排查)。
- 寫入仍以 `asyncio.create_task` 背景進行,獨立 DB session。

## 8. 設定與相容

- 新增 `OPENROUTER_STREAM_TIMEOUT`(預設 300,秒),同步加入 `.env.example`(`# --- OpenRouter ---` 區段)。串流連線的 read timeout 套用此值,避免被 `OPENROUTER_API_TIMEOUT`(60s)提早中斷。
- 不改 DB schema、不需 migration。
- 既有非串流 `/model/chat` 行為完全不變;串流為純新增端點,向後相容。
- 對齊的 Design-Base 章節:
  - [50-openrouter.md § 4 呼叫流程 / § 7 串流 / § 8 重試 / § 9 錯誤對應 / § 10 用量紀錄 / § 11 設定](../../Design-Base/50-openrouter.md)
  - [20-backend.md § 1 統一 Response 格式(串流端點例外處理)](../../Design-Base/20-backend.md)
  - [90-task-spec.md § 4 產出內容規範 / § 5 禁止事項(串流例外)](../../Design-Base/90-task-spec.md)

## 9. 設計取捨 / 待確認事項

> **決議(2026-06-11,使用者確認)**:
> - (1) Internal 串流 **不做**(本版只 OpenRouter,internal 走串流端點回 400)。
> - (2) 上游中斷採 **(a)**:轉發 OpenRouter 自身 error chunk + 關閉連線;後端側無預警斷線才補送 `data:{"error":...}` + `data:[DONE]`。
> - (3) SDK 對外文件 / `docs/INTEGRATION.md` **本版一併更新**。
> - (4) `stream_options:{include_usage:true}` **直接注入**(僅供記帳,usage 不外露)。
> - 端點形狀採 **B(另開 `/model/chat/stream`)**(見 § 5.1)。
>
> **決議補充(2026-06-11,正式站實測後)**:回應格式由「原樣轉發 OpenRouter SSE」改為**簡化 `{ id, content }`**。原因:實測原始 chunk 會把 `provider`(如 "Amazon Bedrock")、`cost`、`upstream_inference_cost`、`model` 路由、`finish_reason` 等內部欄位漏給 SDK,違反 [§ 6](../../Design-Base/50-openrouter.md) / [§ 12](../../Design-Base/50-openrouter.md) 「不外露內部資訊、成本」原則,也與非串流端點只回純文字不一致。改為解析後只回 id + content;OpenRouter 中途 error chunk 轉成 `data:{"error":"upstream_error"}`,後端側斷線補 `data:{"error":"openrouter_unavailable"}`。連帶更新 § 1 / § 4 流程圖 / § 5.2 / § 5.3 / § 6 與 50-openrouter.md § 7、使用者指南。

1. **Internal provider 串流是否本版納入?** 建議**否**(本版只做 OpenRouter,internal 回 400),先把 OpenRouter 串流穩定上線;同意則維持 § 3 Out of Scope。
2. **上游中途中斷時的處理**:[§ 7](../../Design-Base/50-openrouter.md) 要求「不可靜默截斷」。兩種做法:
   - (a) 僅原樣轉發 OpenRouter 自身的 error chunk + 關閉連線(最貼近 OpenRouter 格式);
   - (b) 後端**額外**送一個 `data: {"error":...}` chunk 再 `data: [DONE]` 收尾。
   建議 (a) 為主、僅在「後端側」失敗(例如上游連線無預警斷)時補送 (b),確保不靜默截斷。待你定。
3. **SDK 端 / INTEGRATION.md 更新**:本版動到對外 API 鏈路,須同步 SDK 呼叫範例與串流解析說明。是否本版一併產出,或另開文件 patch?
4. **stream_options 注入**:預設注入 `include_usage:true` 以利記帳;若擔心個別下游模型不支援,可改為「best-effort」(無 usage 時記 0)。建議直接注入。
