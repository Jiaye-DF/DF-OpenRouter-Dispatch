---
id: task-004
title: 觸發點接線 + resend-notify 端點 + Schema + 稽核
status: done
parallel: false
depends_on: [task-001, task-003]
affected_files:
  - backend/app/api/v1/api_key_requests.py
  - backend/app/schemas/api_key_request.py
  - backend/app/core/audit.py
estimated_hours: 4
---

## 目標
在兩個開通成功終態(`agent_done` / `done`)`commit` 後寄信並寫回結果,新增 admin `resend-notify` 重送端點,回應 Schema 補 `notified_at` / `notify_error`,並加入稽核 action。

## Acceptance
- [x] `POST /api-key-requests`(`agent_done`)與 `POST /api-key-requests/{uid}/process`(`done`)皆於 `db.commit()` 之後寄信給 `req.owner_email`;寄送後另起一次 `update + commit` 寫回 `notified_at`(成功)或 `notify_error`(失敗),失敗不影響已開通結果。
- [x] `POST /api-key-requests/{uid}/resend-notify`(admin):以該單現有 `provisioned_secrets` 重寄並更新 `notified_at` / `notify_error`;憑證已清空回 `409 secrets_already_claimed`、非 admin 回 `403`、未設定回 200 + `notify_error="m365_not_configured"`。
- [x] `schemas/api_key_request.py`:`ApiKeyRequestResponse` / `ApiKeyRequestDetailResponse` 加 `notified_at: datetime | None`、`notify_error: str | None`,含欄位 `description` 與範例。
- [x] 稽核 action `notify_api_key_request`(記 result + 收件網域,不記憑證);`resend-notify` 另記 `resend_notify_api_key_request`。

## 必讀檔(Just-in-time)
- [`03-backend/01-routing.md`](../../../Design-Base/03-backend/01-routing.md) · 端點與路由
- [`03-backend/02-auth.md`](../../../Design-Base/03-backend/02-auth.md) · admin 權限守衛
- [`03-backend/92-project-permission.md`](../../../Design-Base/03-backend/92-project-permission.md) · 本專案權限矩陣
- [`03-backend/03-async-and-tx.md`](../../../Design-Base/03-backend/03-async-and-tx.md) · commit 後寄信與獨立 update commit
- [`04-databases/10-statistics-log.md`](../../../Design-Base/04-databases/10-statistics-log.md) · 稽核 action 記錄
- [`00-overview/04-api-docs.md`](../../../Design-Base/00-overview/04-api-docs.md) · 回應 schema 範例與文件
