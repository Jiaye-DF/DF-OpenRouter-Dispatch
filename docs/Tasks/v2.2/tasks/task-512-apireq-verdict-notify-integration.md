---
id: task-512
title: 申請單各終態觸發管理員通知(整合 api_key_requests)
status: pending
parallel: true
depends_on: [task-501, task-511]
affected_files:
  - backend/app/api/v1/api_key_requests.py
  - backend/tests/api/test_api_key_requests_admin_notify.py
estimated_hours: 3
---

## 目標

申請單(金鑰申請單)判決出終態後,除既有寄申請人通知外,加寄一封通知信給系統管理員;涵蓋所有終態轉換,best-effort 不擋主流程(propose §B.2 / §D.4 / §D.5 / §D.6)。

## 範圍(只做這些)

- **新 helper** `notify_admin_on_verdict(db, row, actor, ip)`(與既有 `_notify_owner` 平行、獨立 try/except best-effort):
  - `APIREQ_ADMIN_NOTIFY_ENABLED` false → 直接 return(不寄)。
  - 解析收件:`UserRepository(db).get_by_account(settings.INITIAL_ADMIN_ACCOUNT)`;查無 / `.email` 為 None → log(info)後 return(不寄、不報錯)。
  - 有 email → 呼叫 `send_admin_notify_email(...)`(511),帶申請人 / 部門 / 專案 / `row.status` / reason(`agent_decision.reason` 若有)/ `row.<uid 欄>`。
  - 寄送成敗**僅落結構化 log**(**不**寫 DB 欄位,D.6);失敗 `except` 吞掉、**不**回滾申請單狀態、**不**影響既有申請人通知。
- **觸發點整合**(所有終態,D.5):於 `create_api_key_request`(`cancelled` / `manual_pending` / `agent_done` 三分支決定 status 之後)、`process_api_key_request`(→`done`)、`cancel_api_key_request`(→`cancelled`)、`revoke_api_key_request`(→`revoked`)各呼叫 `notify_admin_on_verdict`;與既有 `_notify_owner` 呼叫點同層、互不連坐。
- **不動**:`_notify_owner` 既有邏輯(申請人信照舊)、`route` / `provision` / AI 判決(`validate_fields`)/ 狀態機本體 / response schema。

## Acceptance

- [ ] `cd backend && uv run pytest tests/api/test_api_key_requests_admin_notify.py -q` 全綠;測試涵蓋:❶ `APIREQ_ADMIN_NOTIFY_ENABLED=true` 且 admin 有 email → 建立申請單判出終態後,`send_admin_notify_email` 被呼叫(mock/respx),收件為 admin email;❷ `=false` → 不呼叫;❸ admin 無 email → 不呼叫、不報錯、主流程 201/200 正常;❹ `send_admin_notify_email` 拋例外 → 申請單建立仍成功(best-effort),申請人通知不受影響;❺ 人工 `process` / `cancel` / `revoke` 終態亦觸發一次
- [ ] `cd backend && uv run python -c "import inspect,app.api.v1.api_key_requests as m; assert 'notify_admin_on_verdict' in dir(m); print('ok')"` 印出 `ok`
- [ ] 既有申請單測試回歸:`cd backend && uv run pytest tests/api/test_api_key_requests.py -q` 全綠(申請人通知 / 狀態機不受影響)
- [ ] `cd backend && uv run ruff check app/api/v1/api_key_requests.py && uv run mypy app/api/v1/api_key_requests.py` 全綠

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/01-routing.md`
- `docs/Design-Base/03-backend/05-exceptions-and-logging.md`
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/03-backend/92-project-permission.md`
- `docs/Design-Base/90-third-party-service/03-smtp.md`
- `docs/Design-Base/04-databases/03-passwords-and-pii.md`
