---
id: task-004
title: internal_keys 後端 — schema/repository/service + /api/v1/internal-keys CRUD 5 端點
status: done
parallel: true
depends_on: [task-001]
affected_files:
  - backend/app/schemas/internal_key.py
  - backend/app/repositories/internal_key.py
  - backend/app/services/internal_key.py
  - backend/app/api/v1/internal_keys.py
  - backend/app/api/v1/__init__.py
estimated_hours: 3
---

## 目標
建立 internal_keys 的 schema / repository / service 與 admin-only CRUD 5 端點;`api_key` 加密儲存(`key_ciphertext` + `key_last4`),response 僅回 `has_api_key` 旗標不含明文。

## Acceptance
- [x] `schemas/internal_key.py`:`InternalKeyResponse`(含 `has_api_key` / `key_last4`,不含明文 `api_key`)、`InternalKeyCreateRequest`、`InternalKeyUpdateRequest`(`api_key` 傳值即換、omit 不動)
- [x] `repositories/internal_key.py` / `services/internal_key.py`:CRUD + 軟刪除(`is_deleted`)+ `api_key` 加密為 `key_ciphertext` 並取 `key_last4`
- [x] `/api/v1/internal-keys` 5 端點(GET 列表分頁、POST、GET 單筆、PATCH、DELETE 軟刪)全為 admin-only,response 走 `success_response()`/`failure_response()`,並掛載到 `api/v1/__init__.py`
- [x] `GET` / `POST` / `PATCH` 任何 response 皆不外洩明文 `api_key`

## 必讀檔(Just-in-time)
- [`03-backend/01-routing.md`](../../../Design-Base/03-backend/01-routing.md) · [`03-backend/91-project-auth.md`](../../../Design-Base/03-backend/91-project-auth.md) · [`03-backend/92-project-permission.md`](../../../Design-Base/03-backend/92-project-permission.md) · [`04-databases/02-soft-delete.md`](../../../Design-Base/04-databases/02-soft-delete.md) · [`04-databases/03-passwords-and-pii.md`](../../../Design-Base/04-databases/03-passwords-and-pii.md) · [`00-overview/02-secrets.md`](../../../Design-Base/00-overview/02-secrets.md)
