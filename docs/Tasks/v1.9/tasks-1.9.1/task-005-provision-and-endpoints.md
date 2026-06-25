---
id: task-005
title: 自動開通 service 與生命週期 API 端點
status: done
parallel: false
depends_on: [task-001, task-002, task-003, task-004]
affected_files:
  - backend/app/services/api_key_request_provision.py
  - backend/app/api/v1/api_key_requests.py
estimated_hours: 4
---

## 目標
實作單一 transaction 的自動開通 service,並擴充/新增申請單生命週期端點(送出同步跑 route→AI→provision、取消、撤銷、人工處理、詳情、領取憑證),含權限與稽核。

## Acceptance
- [x] `services/api_key_request_provision.py` `provision(db, req, route) -> ProvisionResult`:單一 transaction 沿用部門 → 建專案(`code` 走 Snowflake)→ 沿用/建使用者 → 沿用/建 SDK Key → 發 User Token;任一步失敗 rollback 並回 `manual_pending` + `error_message`。
- [x] 開通寫回 `created_project_uid`/`created_user_uid`/`created_sdk_key_uid`/`matched_department_uid`/`processed_at`,並組 `provisioned_secrets={sdk_key,user_token,project_code}`(沿用 Key 無留存明文則 `sdk_key=null` 並提示);各步 `write_audit` + 一筆 `auto_provision_api_key_request`。
- [x] `POST /api-key-requests`(擴充):同步 `route→(AI)→provision`,終態與一次性憑證寫回並於回應帶回。
- [x] `POST /{uid}/cancel`(本人):限 `manual_pending` 否則 409,缺 `reason` 回 422,寫 `cancel_reason`/`cancel_source='user'`/`status='cancelled'`。
- [x] `POST /{uid}/revoke`(本人/admin):限 `manual_pending`,已處理(`agent_done`/`done`)回 409。
- [x] `POST /{uid}/process`(admin):確定性開通 → `done`、寫 `handled_by_user_uid`。
- [x] `GET /{uid}`(本人/admin):詳情,本人僅能看自己(否則 403)。
- [x] `POST /{uid}/claim-secrets`(本人):回 `provisioned_secrets` 後以 `NULL` 覆寫。
- [x] 所有寫入動作寫對應 `write_audit`(`cancel`/`revoke`/`process`/`auto_provision`)。

## 必讀檔(Just-in-time)
- [`03-backend/01-routing.md`](../../../Design-Base/03-backend/01-routing.md) · 端點與路由
- [`03-backend/02-auth.md`](../../../Design-Base/03-backend/02-auth.md) · 本人/admin 權限
- [`03-backend/03-async-and-tx.md`](../../../Design-Base/03-backend/03-async-and-tx.md) · 單一 transaction 與 rollback
- [`03-backend/05-exceptions-and-logging.md`](../../../Design-Base/03-backend/05-exceptions-and-logging.md) · 409/403/422 與稽核
- [`03-backend/92-project-permission.md`](../../../Design-Base/03-backend/92-project-permission.md) · 稽核 action 與後台存取
