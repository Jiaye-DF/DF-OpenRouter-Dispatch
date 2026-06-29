---
id: task-006
title: SDK Key 管理後端(argon2id hash 儲存 + prefix 候選查詢 + V4 migration)
status: done
parallel: true
depends_on: [task-001]
affected_files:
  - migrations/V4__sdk_api_keys.sql
  - backend/app/api/v1/sdk_keys.py
  - backend/app/services/sdk_key/
  - backend/app/repositories/sdk_api_key.py
  - backend/app/schemas/sdk_key.py
  - backend/tests/api/test_sdk_keys.py
estimated_hours: 2
---

## 目標

依 propose § 4.2 實作部門層 SDK Key:V4 建 `sdk_api_keys`;明文格式 `ordsk_<12hex>_<32 base62>`,DB 僅存 `argon2id` hash + 公開 `key_prefix`,明文僅建立時一次性回應;驗證以 prefix 候選查詢再 argon2 比對 secret。全 admin CRUD(PATCH 限 `name` / `is_active`,軟刪除)。

## Acceptance

- [x] `uv run pytest tests/api/test_sdk_keys.py` 全綠
- [x] DB 僅存 hash:`grep -rn "key_hash" backend/app | grep -vi argon` 無明文 / 弱演算法
- [x] 建立 response 一次性回明文,後續列表 / 單筆**不**回明文(斷言過濾)
- [x] V4 套用後 `sdk_api_keys` 含 `idx_sdk_api_keys_prefix`(WHERE `is_deleted=FALSE`)

## 必讀檔(Just-in-time)

- [`03-backend/02-auth.md`](../../../Design-Base/03-backend/02-auth.md) · [`01-routing.md`](../../../Design-Base/03-backend/01-routing.md)
- [`04-databases/03-passwords-and-pii.md`](../../../Design-Base/04-databases/03-passwords-and-pii.md) · [`01-identifiers.md`](../../../Design-Base/04-databases/01-identifiers.md)
- [`03-backend/03-async-and-tx.md`](../../../Design-Base/03-backend/03-async-and-tx.md)(argon2id 走 `asyncio.to_thread`)
