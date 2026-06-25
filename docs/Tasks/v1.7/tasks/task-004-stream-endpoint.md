---
id: task-004
title: 新增 POST /api/v1/model/chat/stream 串流端點
status: done
parallel: false
depends_on: [task-003]
affected_files:
  - backend/app/api/v1/model_chat.py
estimated_hours: 3
---

## 目標
於既有 `model` router 新增 `POST /api/v1/model/chat/stream`,沿用 `SdkCallerDep` 與既有 `ChatRequest`;以 prime async generator 方式讓 pre-stream 錯誤回 `ApiResponse`、成功後改回 `text/event-stream`。

## Acceptance
- [x] 端點掛於既有 router,沿用 `SdkCallerDep`(X-SDK-Key + X-User-Token)與既有 `ChatRequest`,**不**新增 `stream` 欄位。
- [x] handler 先 `await agen.__anext__()` prime:pre-stream `AppError` 由既有 exception handler 轉 `ApiResponse`(尚未送 200);`StopAsyncIteration` 回只含 `data: [DONE]\n\n` 的串流。
- [x] 成功取得第一個 chunk 才建立 `StreamingResponse(media_type="text/event-stream")`,先 yield 第一個 chunk 再續傳,header 加 `Cache-Control: no-cache`、`X-Accel-Buffering: no`。
- [x] Swagger 於 `/api/docs` 可查閱新端點,含「回應為 SSE、非 ApiResponse」描述。

## 必讀檔(Just-in-time)
- [`03-backend/01-routing.md`](../../../Design-Base/03-backend/01-routing.md) · 路由規範
- [`03-backend/02-auth.md`](../../../Design-Base/03-backend/02-auth.md) · SDK Key + User Token 驗證
- [`00-overview/04-api-docs.md`](../../../Design-Base/00-overview/04-api-docs.md) · Swagger 文件
- [`90-third-party-service/50-openrouter.md`](../../../Design-Base/90-third-party-service/50-openrouter.md) · § 7 串流端點規格
