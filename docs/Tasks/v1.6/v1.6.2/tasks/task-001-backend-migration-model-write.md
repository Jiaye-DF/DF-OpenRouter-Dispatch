---
id: task-001
title: 後端 DB/寫入:usage_logs 加 used_tools 欄 + partial index,proxy 推導與存完整 output_text
status: done
parallel: true
depends_on: []
affected_files:
  - alembic/versions/0011_usage_log_used_tools.py
  - app/models/usage_log.py
  - app/services/proxy.py
estimated_hours: 2
---

## 目標
為 `usage_logs` 新增 `used_tools` 持久化布林欄與 partial index,並讓 proxy 由請求快照推導寫入該欄、改存完整 `output_text` 取代原截斷 500 字內容。

## Acceptance
- [x] `alembic/versions/0011_usage_log_used_tools.py` revises 0010,upgrade 加 `used_tools BOOLEAN NOT NULL DEFAULT FALSE`(server_default false → 舊紀錄自動回填)+ partial index `idx_usage_logs_used_tools_time ON usage_logs (created_at DESC) WHERE used_tools = TRUE AND is_deleted = FALSE`
- [x] downgrade 對稱 drop index + drop column
- [x] `app/models/usage_log.py` 加 `used_tools` Mapped 欄(server_default "false")
- [x] `app/services/proxy.py` `schedule_usage_log` 由 `request_log.tools` 推導 `used_tools = bool(...)` 寫入(只改一處,不在各呼叫點傳參)
- [x] `app/services/proxy.py` `_summarize_response` 改存完整 `output_text`(沿用 `_extract_content`),取代原 `first_text` 截斷
- [x] `python -m py_compile` 對 model / proxy / migration 通過

## 必讀檔(Just-in-time)
- [`04-databases/00-overview.md`](../../../../Design-Base/04-databases/00-overview.md) · [`04-databases/02-soft-delete.md`](../../../../Design-Base/04-databases/02-soft-delete.md) · [`04-databases/09-indexes-and-perf.md`](../../../../Design-Base/04-databases/09-indexes-and-perf.md) · [`04-databases/10-statistics-log.md`](../../../../Design-Base/04-databases/10-statistics-log.md)
- [`90-third-party-service/50-openrouter.md`](../../../../Design-Base/90-third-party-service/50-openrouter.md) · [`03-backend/03-async-and-tx.md`](../../../../Design-Base/03-backend/03-async-and-tx.md)
