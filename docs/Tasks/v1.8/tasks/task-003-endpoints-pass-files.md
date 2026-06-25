---
id: task-003
title: 兩端點傳遞 files 至 service
status: done
parallel: false
depends_on: [task-002]
affected_files:
  - backend/app/api/v1/model_chat.py
estimated_hours: 1
---

## 目標
於 `model_chat.py` 的非串流 `/model/chat`(含 deprecated alias 共用 `_chat_handler`)與串流 `/model/chat/stream` 兩處,將 `body.files` 轉 dict 後傳入 service。

## Acceptance
- [x] `_chat_handler` 以 `files=[f.model_dump() for f in body.files] if body.files else None` 傳入 `run_chat()`。
- [x] `chat_stream` 以同樣方式將 `body.files` 傳入 `run_chat_stream()`。
- [x] `videos` 非空仍回 `400 feature_not_supported`(不變);驗證沿用 `SdkCallerDep`。
- [x] 不帶 `files` 的請求兩端點行為與既有完全一致(向後相容)。

## 必讀檔(Just-in-time)
- [`03-backend/01-routing.md`](../../../Design-Base/03-backend/01-routing.md) · [`03-backend/02-auth.md`](../../../Design-Base/03-backend/02-auth.md) · [`03-backend/05-exceptions-and-logging.md`](../../../Design-Base/03-backend/05-exceptions-and-logging.md) · [`90-third-party-service/50-openrouter.md`](../../../Design-Base/90-third-party-service/50-openrouter.md)
