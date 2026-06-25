---
id: task-008
title: 用量紀錄後端(usage_logs 背景寫入 + 查詢端點 + V6 migration)
status: done
parallel: true
depends_on: [task-001]
affected_files:
  - migrations/V6__usage_logs.sql
  - backend/app/api/v1/usage_logs.py
  - backend/app/services/usage/
  - backend/app/repositories/usage_log.py
  - backend/app/schemas/usage_log.py
  - backend/tests/api/test_usage_logs.py
estimated_hours: 2
---

## 目標

依 propose § 5 實作用量紀錄:V6 建 `usage_logs`(含 dept/user/model 三組時間索引);提供 `schedule_usage_log` 於 response 回 Client **之後**以背景任務寫入(含失敗一律寫一筆),`request_content` 保留原始 body、`response_summary` 裁切 ≤ 500 字;查詢端點 admin 看全部、user 僅自部門。

## Acceptance

- [x] `uv run pytest tests/api/test_usage_logs.py` 全綠
- [x] 寫入發生於回應之後(`grep -n "BackgroundTasks\|create_task" backend/app/services/usage` 有背景排程)
- [x] 驗證失敗情境仍寫一筆 `status='error'`(`user_uid`/`department_uid` 可 NULL,測試斷言)
- [x] `GET /usage-logs` user 僅見自部門(跨部門查詢被過濾,測試斷言)

## 必讀檔(Just-in-time)

- [`03-backend/03-async-and-tx.md`](../../../Design-Base/03-backend/03-async-and-tx.md)(背景寫入不阻塞回應)
- [`04-databases/00-overview.md`](../../../Design-Base/04-databases/00-overview.md) · [`10-statistics-log.md`](../../../Design-Base/04-databases/10-statistics-log.md)
- [`03-backend/01-routing.md`](../../../Design-Base/03-backend/01-routing.md) · [`92-project-permission.md`](../../../Design-Base/03-backend/92-project-permission.md)
