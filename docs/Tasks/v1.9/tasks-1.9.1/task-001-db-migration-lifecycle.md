---
id: task-001
title: api_key_requests 生命週期欄位 migration 0013
status: done
parallel: true
depends_on: []
affected_files:
  - backend/alembic/versions/0013_api_key_requests_lifecycle.py
estimated_hours: 2
---

## 目標
新增 migration `0013_api_key_requests_lifecycle`(`down_revision = "0012_api_key_requests"`),擴充 `api_key_requests` 生命週期相關欄位,並把既有 `pending` 資料轉為 `manual_pending`。

## Acceptance
- [x] migration `0013_api_key_requests_lifecycle` 建立,`down_revision` 指向 `0012_api_key_requests`。
- [x] `upgrade` 對 `api_key_requests` 新增欄位:`cancel_reason`(Text null)、`cancel_source`(String(8) null)、`handled_by_user_uid`(UUID null)、`agent_decision`(JSONB null)、`error_message`(Text null)、`created_project_uid`/`created_user_uid`/`created_sdk_key_uid`/`matched_department_uid`(UUID null)、`provisioned_secrets`(JSONB null)、`processed_at`(DateTime tz null)。
- [x] `upgrade` 內 `UPDATE api_key_requests SET status='manual_pending' WHERE status='pending'`。
- [x] `downgrade` 移除上述新增欄位,並把 `manual_pending` 還原為 `pending`(其餘狀態略過)。
- [x] `status` 沿用既有 String(16),不改型別。

## 必讀檔(Just-in-time)
- [`04-databases/08-alembic.md`](../../../Design-Base/04-databases/08-alembic.md) · migration 規範與 revision 鏈
- [`04-databases/01-identifiers.md`](../../../Design-Base/04-databases/01-identifiers.md) · UID / 識別碼欄位
- [`04-databases/00-overview.md`](../../../Design-Base/04-databases/00-overview.md) · 資料表設計基準
