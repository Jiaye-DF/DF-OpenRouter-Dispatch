---
id: task-003
title: Microsoft Graph 寄信 service(client credentials + sendMail)
status: done
parallel: false
depends_on: [task-002]
affected_files:
  - backend/app/services/email_graph.py
  - backend/app/core/config.py
  - backend/.env.example
estimated_hours: 3
---

## 目標
新增 `email_graph.py`,以 client credentials 取 Graph token → 呼叫 `sendMail` 寄開通信;設定缺鍵時優雅降級,失敗不外洩憑證且不阻斷開通。同步加入 `M365_*` 四個設定與 `m365_mail_enabled`。

## Acceptance
- [x] `async def send_provision_email(*, to_email, owner_name, project_name, secrets: dict) -> EmailResult` 回 `EmailResult(ok: bool, error: str | None)`。
- [x] 取 token `POST https://login.microsoftonline.com/{M365_TENANT_ID}/oauth2/v2.0/token`(`grant_type=client_credentials`、`scope=https://graph.microsoft.com/.default`);寄信 `POST https://graph.microsoft.com/v1.0/users/{M365_MAIL_SENDER}/sendMail`,body `contentType=HTML`、`content=render_email("provision.html", ...)`、`saveToSentItems=false`。
- [x] `core/config.py` 新增 `M365_TENANT_ID` / `M365_CLIENT_ID` / `M365_CLIENT_SECRET` / `M365_MAIL_SENDER`(預設 `""`)與 `m365_mail_enabled` property(四者皆非空才 True);`.env.example` 同步四鍵,`M365_CLIENT_SECRET` 標 `[COOLIFY]`。
- [x] 降級:`m365_mail_enabled` 為 False → 回 `EmailResult(ok=False, error="m365_not_configured")`,呼叫端不視為錯誤。
- [x] 失敗(取 token 非 2xx → `m365_token_error`、sendMail 非 2xx → `m365_sendmail_<code>`、連線錯誤)→ `logger.warning` 僅記 request_uid / 收件網域 / 結果(不含憑證明文)+ 回 `ok=False`;httpx 用法與逾時對齊 `clients/sso.py`(獨立 `AsyncClient` + `httpx.Timeout`)。

## 必讀檔(Just-in-time)
- [`90-third-party-service/01-client-design.md`](../../../Design-Base/90-third-party-service/01-client-design.md) · 外部 client 設計
- [`90-third-party-service/03-smtp.md`](../../../Design-Base/90-third-party-service/03-smtp.md) · 寄信管道與降級
- [`03-backend/06-clients.md`](../../../Design-Base/03-backend/06-clients.md) · httpx AsyncClient/Timeout 慣例
- [`03-backend/05-exceptions-and-logging.md`](../../../Design-Base/03-backend/05-exceptions-and-logging.md) · 失敗記錄不含憑證
- [`00-overview/02-secrets.md`](../../../Design-Base/00-overview/02-secrets.md) · 機密 env 注入與禁 log
