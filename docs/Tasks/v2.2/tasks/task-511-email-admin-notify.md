---
id: task-511
title: M365 寄信抽共用底層 + 管理員通知函式 + 模板
status: pending
parallel: true
depends_on: []
affected_files:
  - backend/app/services/email_graph.py
  - backend/app/templates/email/admin_apireq_verdict.html
  - backend/app/templates/email/admin_apireq_verdict.txt
  - backend/tests/services/test_email_graph_admin_notify.py
estimated_hours: 3
---

## 目標

提供「寄申請單判決通知信給系統管理員」的寄送能力:把既有 M365 Graph 寄送底層抽為共用內部函式,新增收件人 / 模板可指定的管理員通知函式 + 通知信模板(propose §B.2 / §D.7)。

## 範圍(只做這些)

- **抽共用底層**:於 `email_graph.py` 抽出內部 `_send_mail(*, to_email, subject, html, text) -> EmailResult`(含既有 `_fetch_token` + Graph `sendMail` POST + best-effort 錯誤處理:未配置回 `EmailResult(ok=False, error="m365_not_configured")`,**不 raise**);既有 `send_provision_email` 改為組模板後呼叫 `_send_mail`(行為與現況一致,回歸測試不破)。
- **新通知函式** `send_admin_notify_email(*, to_email, applicant_name, department, project_name, status, reason, request_uid) -> EmailResult`:以 `render_email("admin_apireq_verdict", ...)`(既有 `email_render.render_email`,**不改**)組 html/text,呼叫 `_send_mail`。
- **新模板** `backend/app/templates/email/admin_apireq_verdict.{html,txt}`:沿 `base.html` 樣式;內容含申請人姓名 / 部門 / 專案、判決 `status`(中文語意)、`reason`(若有)、申請單對外 `request_uid`。**禁**含一次性密鑰(`provisioned_secrets`)、內部 pid、收件人以外 PII。
- **不動**:`email_render.py`、`config.py` 的 `M365_*`、`base.html`、`provision.html`。

## Acceptance

- [ ] `cd backend && uv run pytest tests/services/test_email_graph_admin_notify.py -q` 全綠;測試涵蓋:❶ M365 未配置 → `send_admin_notify_email` 回 `ok=False, error="m365_not_configured"` 且不 raise;❷ 模板渲染輸出含判決 status / 申請人 / request_uid,**不含**字串 `sdk_key` / `user_token`;❸ `send_provision_email` 回歸(仍寄申請人、走 `_send_mail`)
- [ ] `[ -f backend/app/templates/email/admin_apireq_verdict.html ] && [ -f backend/app/templates/email/admin_apireq_verdict.txt ]`(兩模板存在)
- [ ] `cd backend && uv run python -c "import inspect,app.services.email_graph as g; assert hasattr(g,'send_admin_notify_email') and hasattr(g,'_send_mail'); print('ok')"` 印出 `ok`
- [ ] `cd backend && uv run ruff check app/services/email_graph.py && uv run mypy app/services/email_graph.py` 全綠

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/05-exceptions-and-logging.md`
- `docs/Design-Base/03-backend/06-clients.md`
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/90-third-party-service/00-overview.md`
- `docs/Design-Base/90-third-party-service/03-smtp.md`
- `docs/Design-Base/04-databases/03-passwords-and-pii.md`
