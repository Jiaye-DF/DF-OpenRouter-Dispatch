---
id: task-003
title: model_chat 端點透傳 body.tools 並補 docstring
status: done
parallel: false
depends_on: [task-002]
affected_files:
  - backend/app/api/v1/model_chat.py
estimated_hours: 1
---

## 目標
`_chat_handler` 將 `body.tools` 透傳給 `run_chat`,並為 `_chat_handler` / `chat` / `chat_deprecated` 補上 docstring 與參數說明。

## Acceptance
- [x] `_chat_handler` 把 `body.tools` 傳給 `run_chat`
- [x] `_chat_handler` / `chat` / `chat_deprecated` 補繁中 Google-style docstring
- [x] 未帶 `tools` 的舊呼叫行為不變(`tools` 預設 None)
- [x] `python -m py_compile backend/app/api/v1/model_chat.py` 通過

## 必讀檔(Just-in-time)
- [`03-backend/01-routing.md`](../../../../Design-Base/03-backend/01-routing.md) · API 端點路由與 handler 規範
- [`90-third-party-service/50-openrouter.md`](../../../../Design-Base/90-third-party-service/50-openrouter.md) · 代理端點 tools 透傳規範
- [`00-overview/04-api-docs.md`](../../../../Design-Base/00-overview/04-api-docs.md) · Swagger/OpenAPI 文件規範
