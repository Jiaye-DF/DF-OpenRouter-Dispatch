---
id: task-002
title: 後端 Schema 與 Repository(含 project_url / email 驗證)
status: done
parallel: false
depends_on: [task-001]
affected_files:
  - backend/app/schemas/api_key_request.py
  - backend/app/repositories/api_key_request.py
estimated_hours: 3
---

## 目標
建立 `ApiKeyRequestCreateRequest`(6 欄全必填,含 `project_url` GitHub/Replit 與 `owner_email` 格式驗證)與 `ApiKeyRequestResponse`,以及 Repository 的 `add()` / `list()` / `get_by_uid()`。

## Acceptance
- [x] `schemas/api_key_request.py`:`ApiKeyRequestCreateRequest`(6 欄,皆 `min_length>=1`)、`ApiKeyRequestResponse`(`from_attributes=True`)。
- [x] `project_url` field validator:scheme 為 http/https,host(小寫去 port)屬 `github.com` / `www.github.com` / `replit.com` / `*.replit.com` / `replit.dev` / `*.replit.dev`,否則 422。
- [x] `owner_email` 以 email 格式驗證(`EmailStr` 或等效),不符回 422。
- [x] `repositories/api_key_request.py`:`add()` / `list(applicant_user_uid=None, page, size)`(回 `(items, total)`)/ `get_by_uid()`,`list` 依 `applicant_user_uid` 條件過濾並依 `created_at` 排序。

## 必讀檔(Just-in-time)
- [`03-backend/00-overview.md`](../../../Design-Base/03-backend/00-overview.md) · 後端分層總覽
- [`03-backend/03-async-and-tx.md`](../../../Design-Base/03-backend/03-async-and-tx.md) · async repository / 交易
- [`03-backend/05-exceptions-and-logging.md`](../../../Design-Base/03-backend/05-exceptions-and-logging.md) · 422 / 例外慣例
- [`04-databases/01-identifiers.md`](../../../Design-Base/04-databases/01-identifiers.md) · request_uid UUID v7
- [`04-databases/02-soft-delete.md`](../../../Design-Base/04-databases/02-soft-delete.md) · 查詢排除軟刪
