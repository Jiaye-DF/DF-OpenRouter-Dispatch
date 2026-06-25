---
id: task-007
title: User Token 簽發 / 撤銷 + SDK 雙因子驗證 Dependency(V5 migration)
status: done
parallel: false
depends_on: [task-003, task-006]
affected_files:
  - migrations/V5__user_tokens_revocations.sql
  - backend/app/api/v1/user_tokens.py
  - backend/app/services/user_token/
  - backend/app/repositories/user_token_revocation.py
  - backend/app/core/sdk_auth.py
  - backend/app/schemas/user_token.py
  - backend/tests/api/test_user_tokens.py
estimated_hours: 3
---

## 目標

依 propose § 4.1 / 4.3 實作雙因子代理驗證地基:V5 建 `user_tokens_revocations`;admin 以 `POST /users/{uid}/tokens` 簽發 AES-256-GCM 加密 Token(payload 取自 users + departments,一次性顯示)、`/tokens/revoke` 寫撤銷時點;`core/sdk_auth.py` Dependency 解析 `X-SDK-Key` + `X-User-Token`、驗 revocation、檢查兩者 `department_uid` 一致。`parallel:false`:需 users(003)與 sdk_api_keys(006)模組。

## Acceptance

- [x] `uv run pytest tests/api/test_user_tokens.py` 全綠
- [x] Token `encrypt` → `decrypt` round-trip 取回 payload;`issued_at < latest_revocation` → 401 `unauthorized`(斷言)
- [x] `X-SDK-Key` 與 `X-User-Token` 部門不一致 → 401 `unauthorized`;缺任一 / 解密失敗 → **統一** 401(不分別揭露)
- [x] 簽發 response 一次性回加密字串,不落地 DB(payload 可由 users 重建)

## 必讀檔(Just-in-time)

- [`03-backend/02-auth.md`](../../../Design-Base/03-backend/02-auth.md)
- [`90-third-party-service/50-openrouter.md`](../../../Design-Base/90-third-party-service/50-openrouter.md)(§3 雙因子驗證)
- [`04-databases/03-passwords-and-pii.md`](../../../Design-Base/04-databases/03-passwords-and-pii.md) · [`00-overview/02-secrets.md`](../../../Design-Base/00-overview/02-secrets.md)
