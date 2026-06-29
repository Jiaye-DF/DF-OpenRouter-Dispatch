---
id: task-003
title: 登入系統後端(login/refresh/logout/me/改密 + admin 建立使用者, V1 migration)
status: done
parallel: true
depends_on: [task-001]
affected_files:
  - migrations/V1__init_auth.sql
  - backend/app/api/v1/auth.py
  - backend/app/api/v1/users.py
  - backend/app/services/auth/
  - backend/app/services/user/
  - backend/app/repositories/user.py
  - backend/app/repositories/refresh_token.py
  - backend/app/schemas/auth.py
  - backend/app/schemas/user.py
  - backend/tests/api/test_auth.py
  - backend/tests/api/test_users.py
estimated_hours: 4
---

## 目標

依 `03-backend/91-project-auth.md` 實作本地登入:Access + Refresh(rotation + 重用偵測)、logout、me、自行改密、admin 建立 / 列表 / 改 / 重設密碼使用者;V1 migration 建 `users` + `refresh_tokens` + `set_updated_at()` trigger + 初始 admin Seed(argon2id)。

## Acceptance

- [x] `uv run pytest tests/api/test_auth.py tests/api/test_users.py` 全綠
- [x] refresh rotation:舊 refresh 再用 → 401 `refresh_reuse_detected`(測試斷言)
- [x] 密碼以 argon2id 雜湊,`grep -r "password_hash" backend/app | grep -vi argon` 無明文/弱演算法
- [x] 受保護端點未帶 Access → 401 `unauthorized`;非 admin 打 admin 端點 → 403 `forbidden`
- [x] `alembic`/Flyway round-trip:`V1__init_auth.sql` 套用後 `users` 含必備欄位(`pid`/`user_uid`/`is_active`/`is_deleted`/`created_at`/`updated_at`)

## 必讀檔(Just-in-time)

- [`03-backend/02-auth.md`](../../../Design-Base/03-backend/02-auth.md) · [`91-project-auth.md`](../../../Design-Base/03-backend/91-project-auth.md)
- [`04-databases/00-overview.md`](../../../Design-Base/04-databases/00-overview.md) · [`01-identifiers.md`](../../../Design-Base/04-databases/01-identifiers.md) · [`03-passwords-and-pii.md`](../../../Design-Base/04-databases/03-passwords-and-pii.md)
- [`03-backend/03-async-and-tx.md`](../../../Design-Base/03-backend/03-async-and-tx.md)(argon2id 走 `asyncio.to_thread`)
