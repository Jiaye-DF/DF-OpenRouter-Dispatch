---
id: task-436
title: 後端:update_user 停用即 revoke_tokens("user_disabled") + 不可停用自己(400) + 測試
status: done
parallel: true
depends_on: []
affected_files:
  - backend/app/api/v1/users.py
  - backend/tests/api/test_users_disable.py
estimated_hours: 3
---

## 目標

`backend/app/api/v1/users.py` `update_user`(現 L154-203)補兩件事:❶ 偵測 `is_active` 由 `true → false` 時呼叫既有 `user_token_service.revoke_tokens(db, user_uid=..., reason="user_disabled")`(雙表:落地 token 標 `revoked_at`/`revoked_reason` + 寫 `UserTokenRevocation` 浮水印);❷ 擋 admin 停用自己(`actor.user_uid == target` 且停用 → 400)。`false → true`(重新啟用)不觸發任何 token 動作。

## 實作要點(對齊 propose §B.4 / §D.3 / §D.5)

- 停用偵測以「異動前 `user.is_active` 為 True 且 payload `is_active` 為 False」判定(注意 `exclude_unset`;重複送 `is_active=false` 不重複撤銷——`revoke_tokens` 對無有效 token 情境須冪等,以現況 service 行為為準)。
- **不動**驗證鏈程式碼:`sdk_auth.py` / `deps.py` / `auth.py` / `sso.py` 的 `is_active` 檢查為現況已存在,本 task 僅以測試補護欄(不列入 affected_files、不得改動)。
- `generate_token`(`user_token.py:26`)已擋停用者,不需改;測試斷言即可。

## 稽核說明(`92-project-permission.md §9`)

- 沿用既有 `update_user` 稽核(users.py 現 L183-195):`extra` 含變更欄位(將自然含 `is_active`)+ `tokens_revoked` 旗標;**不**另立獨立 action(§D.5 定案)。
- 確認停用路徑的稽核 `extra.tokens_revoked` 正確反映本次是否觸發撤銷。

## 錯誤處理對照表

| 情境 | HTTP | 說明 |
| --- | --- | --- |
| admin 對自己送 `is_active: false` | 400 | 錯誤訊息明示不可停用自己;錯誤碼樣式對齊 `90-project-backend.md §2` |
| 停用不存在 / 已刪除使用者 | 404 | 現況不變 |
| 非 admin 呼叫 | 403/401 | `AdminDep` 現況不變 |
| 重複停用(已停用再送 false) | 200 | 冪等,不重複撤銷、不噴錯 |

## Acceptance

- [ ] `uv run pytest backend/tests/api/test_users_disable.py` 全綠;案例至少涵蓋:
  - [ ] 停用 → `user_tokens` 有效 token 標 `revoked_at` + `revoked_reason="user_disabled"`;`user_token_revocations` 新增浮水印
  - [ ] 停用後 `x-user-token` SDK 呼叫 → 401(走 `resolve_sdk_caller` 整合測試)
  - [ ] 停用後本地登入 → 401;既有 session 下一請求(`require_user`)→ 401
  - [ ] 重新啟用 → 可登入;原 token 仍 401;`get_or_create_token` 可重發新 token 且新 token 可用
  - [ ] 停用中 `POST /{uid}/tokens` 產 token → 404(現況 `generate_token` 擋下)
  - [ ] admin 停用自己 → 400;重複停用 → 200 冪等
  - [ ] 稽核:停用/啟用各留 `update_user` 紀錄,`extra` 含 `is_active` 與 `tokens_revoked`
- [ ] `uv run pytest backend/tests` 全綠;`uv run mypy backend/app/api/v1/users.py`、`uv run ruff check backend/app/api/v1/users.py` 零錯誤零 warning
- [ ] `git diff backend/app/core/ backend/app/services/auth.py backend/app/services/sso.py backend/app/services/user_token.py` 為空(驗證鏈與撤銷 service 零改動)

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/01-routing.md` + `90-project-backend.md`(錯誤訊息規範)
- `docs/Design-Base/03-backend/02-auth.md` + `91-project-auth.md`(認證鏈)
- `docs/Design-Base/03-backend/92-project-permission.md`(§9 稽核)
- `docs/Design-Base/03-backend/07-testing.md`(真 DB 整合)
- `docs/Design-Base/04-databases/90-project-database.md`(is_active 語意)
- `docs/Tasks/v2.1/propose-v2.1.2.md` §B.4/§D.3/§D.5
