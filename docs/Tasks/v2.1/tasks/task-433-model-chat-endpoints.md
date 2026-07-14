---
id: task-433
title: 後端:model_chat 端點打通(chat / chat/stream / deprecated alias)+ 整合測試 + /api/docs
status: done
parallel: true
depends_on: [task-432]
affected_files:
  - backend/app/api/v1/model_chat.py
  - backend/tests/api/test_model_chat_messages.py
estimated_hours: 2
---

## 目標

`backend/app/api/v1/model_chat.py` 把 `body.messages` 傳入 service:`_chat_handler`(現 L27-60)、`chat_stream`(L77-134)逐欄位傳參擴充;canonical `/model/chat`、串流 `/model/chat/stream`、deprecated `/model/openrouter/chat` 三入口行為一致。整合測試覆蓋端到端(mock 下游)。

## 實作要點(對齊 propose §B.2 / 對外承諾)

- `_chat_handler` 與 `chat_stream` 新增 `messages=body.messages` 與 `temperature` / `max_tokens` / `response_format` 傳遞;其餘欄位傳遞不動。
- 回應格式**不變**:`success_response(data=<純文字>)`;串流 SSE 格式不變(`90-project-backend.md §1` 串流例外處理現況)。
- `/api/docs` OpenAPI 自動反映 `messages` 與三生成參數欄位(schema 由 431 提供;確認 examples/description 可讀)。
- 代理端雙因子認證(`x-sdk-key` + `x-user-token`)、白名單、配額鏈路**不動**。

## 錯誤處理對照表

| 情境 | HTTP | 說明 |
| --- | --- | --- |
| `messages` 與 `text/images/files` 同時帶 / `[]` / 非法 role / 非法 part | 400 | 431 schema 驗證,經統一包裝 |
| `temperature` 越界 / `max_tokens` < 1 / `response_format` 非白名單 | 400 | 431 schema 驗證,經統一包裝 |
| 認證失敗(sdk key / user token) | 401 | 現況不變 |
| 模型不在白名單 | 現況碼 | 不變 |
| 上游 OpenRouter 錯誤 | 現況對應 | 沿 `50-openrouter.md § 錯誤對應` |

## usage_logs / 稽核

- 代理端 usage_logs 寫入由 432 落地(本 task 不動寫入鏈);整合測試斷言 messages 模式有寫入且 `request_content.messages` 存在。
- 代理端不寫管理稽核(現況慣例:代理端業務紀錄入 usage_logs)。

## Acceptance

- [ ] `uv run pytest backend/tests/api/test_model_chat_messages.py` 全綠;案例至少涵蓋(respx/mock 下游):messages 多輪 200 且回純文字 / stream 端點同 body 可用 / deprecated alias 行為一致 / 互斥 400 / 空陣列 400 / temperature 越界 400 / response_format 非白名單 400 / 帶三生成參數時下游收到的 payload 含對應鍵(mock 斷言)/ 舊模式(text)回歸不變 / usage_log 寫入含 messages 快照與生成參數
- [ ] `curl -s http://localhost:8000/api/openapi.json | python -c "import sys,json; s=json.load(sys.stdin); p=s['components']['schemas']['ChatRequest']['properties']; assert all(k in p for k in ('messages','temperature','max_tokens','response_format'))"` 通過(路徑依現況 `/api/docs` 對應 openapi.json 調整)
- [ ] `uv run pytest backend/tests` 全綠;`uv run mypy backend/app/api/v1/model_chat.py`、`uv run ruff check backend/app/api/v1/model_chat.py` 零錯誤零 warning

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/01-routing.md`(ApiResponse 外殼)
- `docs/Design-Base/03-backend/02-auth.md` + `03-backend/92-project-permission.md`(代理端/管理端分離)
- `docs/Design-Base/03-backend/07-testing.md`(respx)
- `docs/Design-Base/00-overview/04-api-docs.md`(`/api/docs`)
- `docs/Design-Base/90-third-party-service/50-openrouter.md`(430 修訂後版本)
- `docs/Tasks/v2.1/propose-v2.1.2.md` §B.2/對外承諾/驗收標準
