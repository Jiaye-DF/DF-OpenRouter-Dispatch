---
id: task-002
title: 後端 Schema/端點/Repository:列表精簡 ListItem + 詳情 Detail + used_tools 篩選
status: done
parallel: false
depends_on: [task-001]
affected_files:
  - app/schemas/usage_log.py
  - app/api/v1/usage_logs.py
  - app/repositories/usage_log.py
estimated_hours: 2
---

## 目標
拆分用量紀錄 schema 為精簡列表項與完整詳情,列表端點加 `used_tools` 篩選,詳情端點回傳完整 Input/Output 內容。

## Acceptance
- [x] `app/schemas/usage_log.py` 新增 `UsageLogListItem`(列表;加 `used_tools`;**不含** request_content/response_summary)與 `UsageLogDetail`(繼承 ListItem;補回 request_content/response_summary),並移除舊 `UsageLogResponse`(確認無其他引用)
- [x] `app/api/v1/usage_logs.py` 列表端點改回傳 `UsageLogListItem` 且加 `used_tools` query 參數;詳情端點回傳 `UsageLogDetail`
- [x] `app/repositories/usage_log.py` `_apply_filters` / `list` 加 `used_tools` 參數並對應過濾
- [x] `python -m py_compile` 對 schema / api / repository 通過
- [x] 列表 payload 不再含 base64 的 request_content(改 ListItem schema)

## 必讀檔(Just-in-time)
- [`03-backend/00-overview.md`](../../../../Design-Base/03-backend/00-overview.md) · [`03-backend/01-routing.md`](../../../../Design-Base/03-backend/01-routing.md) · [`03-backend/02-auth.md`](../../../../Design-Base/03-backend/02-auth.md) · [`03-backend/92-project-permission.md`](../../../../Design-Base/03-backend/92-project-permission.md)
- [`04-databases/02-soft-delete.md`](../../../../Design-Base/04-databases/02-soft-delete.md) · [`04-databases/10-statistics-log.md`](../../../../Design-Base/04-databases/10-statistics-log.md) · [`00-overview/04-api-docs.md`](../../../../Design-Base/00-overview/04-api-docs.md)
