---
id: task-003
title: 代理服務與用量寫入串入 project_uid
status: done
parallel: false
depends_on: [task-002]
affected_files:
  - backend/app/services/proxy.py
  - backend/app/api/v1/model_chat.py
estimated_hours: 3
---

## 目標
把 `project_uid` 串進代理服務全鏈，並寫入 `usage_logs.project_uid`，確保成功與各類錯誤的所有 log 寫入點都帶上專案維度。

## Acceptance
- [x] `app/services/proxy.py:schedule_usage_log` 簽名加 `project_uid: UUID | None`，`UsageLog(...)` row 寫入 `project_uid=project_uid`
- [x] `run_chat` / `_run_chat_openrouter` / `_run_chat_internal` / `_try_internal_call` 簽名加 `project_uid: UUID`
- [x] 所有 `schedule_usage_log(...)` 呼叫點（共 7 處：OpenRouter 4 處、Internal 3 處）都帶 `project_uid=project_uid`
- [x] `app/api/v1/model_chat.py:_chat_handler` 傳 `project_uid=caller.project_uid` 到 `run_chat`
- [x] 帶 3 個 header 的成功請求，`usage_logs` 該筆 `project_uid` 等於 header 對應專案

## 必讀檔(Just-in-time)
- [`90-third-party-service/50-openrouter.md`](../../../Design-Base/90-third-party-service/50-openrouter.md) · [`03-backend/03-async-and-tx.md`](../../../Design-Base/03-backend/03-async-and-tx.md) · [`03-backend/01-routing.md`](../../../Design-Base/03-backend/01-routing.md) · [`03-backend/05-exceptions-and-logging.md`](../../../Design-Base/03-backend/05-exceptions-and-logging.md) · [`04-databases/10-statistics-log.md`](../../../Design-Base/04-databases/10-statistics-log.md)
