---
id: task-001
title: Migration 0014 — api_key_requests 新增 notified_at / notify_error
status: done
parallel: true
depends_on: []
affected_files:
  - backend/app/alembic/versions/0014_api_key_requests_notify.py
  - backend/app/models/api_key_request.py
estimated_hours: 1
---

## 目標
為 `api_key_requests` 表新增寄信留痕兩欄(`notified_at` / `notify_error`),並建立可逆 migration `0014`,供開通通知流程寫回寄送結果。

## Acceptance
- [x] migration `0014_api_key_requests_notify`(`down_revision = "0013_api_key_requests_lifecycle"`)`ALTER TABLE api_key_requests` 新增 `notified_at`(DateTime tz, nullable)與 `notify_error`(Text, nullable)。
- [x] `downgrade` 移除上述兩欄,無資料轉換需求。
- [x] `models/api_key_request.py` ORM 同步加上 `notified_at` / `notify_error` 兩欄位映射。
- [x] revision id 長度未超過 `alembic_version` VARCHAR(32) 限制,`alembic upgrade head` 與 `downgrade -1` 皆可執行。

## 必讀檔(Just-in-time)
- [`04-databases/08-alembic.md`](../../../Design-Base/04-databases/08-alembic.md) · migration 撰寫與 revision 規範
- [`04-databases/01-identifiers.md`](../../../Design-Base/04-databases/01-identifiers.md) · 欄位命名與型別
- [`04-databases/02-soft-delete.md`](../../../Design-Base/04-databases/02-soft-delete.md) · 時間欄位 tz 慣例
- [`00-overview/05-timezone.md`](../../../Design-Base/00-overview/05-timezone.md) · DateTime(tz) 時區處理
