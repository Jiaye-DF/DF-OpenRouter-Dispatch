---
id: task-001
title: usage_logs 加 project_uid 欄位 + Alembic migration + partial index
status: done
parallel: false
depends_on: []
affected_files:
  - backend/app/models/usage_log.py
  - backend/alembic/versions/0005_usage_logs_project_uid.py
estimated_hours: 2
---

## 目標
為 `usage_logs` 增加 `project_uid UUID NULL` 欄位(FK to `projects`，`ON DELETE SET NULL`)與對應 partial index，作為專案維度串接的資料層地基。

## Acceptance
- [x] `app/models/usage_log.py` 新增 `project_uid: Mapped[UUID | None]`（nullable）
- [x] Alembic revision `0005_usage_logs_project_uid` 建立 `usage_logs.project_uid UUID NULL`，FK 到 `projects(project_uid)` 且 `ON DELETE SET NULL`
- [x] 建立 partial index `idx_usage_logs_project_uid_time ON usage_logs (project_uid, created_at) WHERE is_deleted = FALSE`
- [x] `alembic upgrade head` 成功，`usage_logs` 表確認有 `project_uid` 欄位、index 與 FK
- [x] 既有歷史紀錄 `project_uid` 為 NULL，不回填、不遷移

## 必讀檔(Just-in-time)
- [`04-databases/08-alembic.md`](../../../Design-Base/04-databases/08-alembic.md) · [`04-databases/01-identifiers.md`](../../../Design-Base/04-databases/01-identifiers.md) · [`04-databases/09-indexes-and-perf.md`](../../../Design-Base/04-databases/09-indexes-and-perf.md) · [`04-databases/02-soft-delete.md`](../../../Design-Base/04-databases/02-soft-delete.md) · [`04-databases/10-statistics-log.md`](../../../Design-Base/04-databases/10-statistics-log.md)
