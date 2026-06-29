---
id: task-001
title: 新增 api_key_requests 資料表與 Alembic migration 0012
status: done
parallel: false
depends_on: []
affected_files:
  - backend/app/models/api_key_request.py
  - backend/app/models/__init__.py
  - backend/alembic/versions/0012_api_key_requests.py
estimated_hours: 3
---

## 目標
建立 `api_key_requests` 資料表的 SQLAlchemy Model(含 `TimestampMixin`)與 Alembic migration `0012`,接於現有最新 `0011_usage_log_used_tools` 之後,作為全端功能的資料地基。

## Acceptance
- [x] 新增 `models/api_key_request.py`:`Base` + `TimestampMixin`,`request_uid` 為對外 UUID v7,欄位 `department_name(128)` / `department_code(32)` / `project_name(128)` / `project_url(512)` / `owner_name(64)` / `owner_email(255)` / `status(16, server_default 'pending')` / `applicant_user_uid` 皆 not null。
- [x] 於 `models/__init__.py` export `ApiKeyRequest`。
- [x] 新增 migration `0012_api_key_requests`,`down_revision = "0011_usage_log_used_tools"`。
- [x] migration 建 `updated_at` trigger(沿用既有 `set_updated_at()`)與 index:`applicant_user_uid`(member 過濾)、`created_at`(排序)。
- [x] `alembic upgrade head` 與 `alembic downgrade -1` 對稱(drop table / trigger / index 可還原)。

## 必讀檔(Just-in-time)
- [`04-databases/00-overview.md`](../../../Design-Base/04-databases/00-overview.md) · 資料層總覽
- [`04-databases/01-identifiers.md`](../../../Design-Base/04-databases/01-identifiers.md) · pid / UUID v7 識別碼慣例
- [`04-databases/02-soft-delete.md`](../../../Design-Base/04-databases/02-soft-delete.md) · is_active / is_deleted 軟刪除
- [`04-databases/08-alembic.md`](../../../Design-Base/04-databases/08-alembic.md) · migration / trigger 慣例
- [`04-databases/09-indexes-and-perf.md`](../../../Design-Base/04-databases/09-indexes-and-perf.md) · index 設計
