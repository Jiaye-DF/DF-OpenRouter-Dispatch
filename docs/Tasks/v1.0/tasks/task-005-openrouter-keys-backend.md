---
id: task-005
title: OpenRouter Key 管理後端(AES-256-GCM 加密儲存 + CRUD + V3 migration)
status: done
parallel: true
depends_on: [task-001]
affected_files:
  - migrations/V3__openrouter_keys.sql
  - backend/app/api/v1/openrouter_keys.py
  - backend/app/services/openrouter_key/
  - backend/app/repositories/openrouter_key.py
  - backend/app/schemas/openrouter_key.py
  - backend/tests/api/test_openrouter_keys.py
  - backend/tests/core/test_crypto.py
estimated_hours: 3
---

## 目標

依 propose § 3 實作部門層 OpenRouter Key 管理:V3 建 `openrouter_keys`;明文以 `core/crypto.py`(task-001 提供)AES-256-GCM 加密存 `key_ciphertext`,僅存 prefix / last4;全 admin CRUD,建立時一次性回 last4,PATCH 僅可改 `name` / `is_active`(禁改 `key`),軟刪除。

## Acceptance

- [x] `uv run pytest tests/api/test_openrouter_keys.py tests/core/test_crypto.py` 全綠
- [x] `encrypt` → `decrypt` round-trip 還原明文;`grep -rn "key_ciphertext" backend/app/api` 無回傳明文路徑
- [x] 列表 / 單筆 response **不含** ciphertext,僅 `key_prefix` + `key_last4`(斷言過濾)
- [x] PATCH 帶 `key` 欄位被忽略 / 拒絕(測試斷言);DELETE 為軟刪除(`is_deleted=TRUE`)

## 必讀檔(Just-in-time)

- [`03-backend/01-routing.md`](../../../Design-Base/03-backend/01-routing.md) · [`04-config.md`](../../../Design-Base/03-backend/04-config.md)
- [`04-databases/03-passwords-and-pii.md`](../../../Design-Base/04-databases/03-passwords-and-pii.md)
- [`00-overview/02-secrets.md`](../../../Design-Base/00-overview/02-secrets.md)
