---
id: task-001
title: Migration 為 users 加 sso_user_id 與 back-channel 反查 partial index
status: done
parallel: true
depends_on: []
affected_files:
  - migrations/0004_users_sso_user_id.py
estimated_hours: 1
---

## 目標
為 `users` 表新增 `sso_user_id` 欄位與供 back-channel logout 反查的 partial index,讓 SSO 使用者可被唯一定位。

## Acceptance
- [x] 新增 migration `0004_users_sso_user_id.py`,`down_revision` 正確銜接前一版且 revision ID 不超過 VARCHAR(32)
- [x] `users` 加 `sso_user_id VARCHAR(128) NULL`
- [x] 建 partial index `idx_users_sso_user_id WHERE is_deleted = FALSE`
- [x] `downgrade()` 對稱移除 index 與欄位

## 必讀檔(Just-in-time)
- [`04-databases/08-alembic.md`](../../../Design-Base/04-databases/08-alembic.md) · [`04-databases/01-identifiers.md`](../../../Design-Base/04-databases/01-identifiers.md) · [`04-databases/02-soft-delete.md`](../../../Design-Base/04-databases/02-soft-delete.md)
