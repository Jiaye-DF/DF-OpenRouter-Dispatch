# Tasks v2.2.0 · 模型清單自動同步排程 + 申請單判決後通知系統管理員

> 狀態:進行中(已完成 0/5)
> 來源:[propose-v2.2.0.md](./propose-v2.2.0.md)
> 並行:5 個 task,並行 2(批 A 零依賴)/ 序列由 `depends_on` 驅動 / 預估總時數:12 hr / 阻塞點:0(propose §D 全數拍板)

## 任務清單

| # | 標題 | 狀態 | 並行 | 依賴 | 影響檔案 |
| --- | --- | --- | --- | --- | --- |
| 501 | 三顆 env 開關 + Settings 欄位 + `.env.example` | pending | ✓ | — | `backend/app/core/config.py`、`.env.example` |
| 502 | 模型自動同步排程 task + scheduler 掛載 + `trigger` 稽核標記 | pending | ✓ | 501 | `backend/app/tasks/model_sync.py`、`backend/app/tasks/scheduler.py`、`backend/app/services/sync.py`、`backend/tests/tasks/test_model_sync_dispatch.py` |
| 503 | docker-compose 更新(worker command 追加模組 + prod env 注入) | pending | ✓ | 502 | `docker-compose.dev.yml`、`docker-compose-prod.yml` |
| 511 | M365 寄信抽共用底層 + 管理員通知函式 + 模板 | pending | ✓ | — | `backend/app/services/email_graph.py`、`backend/app/templates/email/admin_apireq_verdict.html`、`backend/app/templates/email/admin_apireq_verdict.txt`、`backend/tests/services/test_email_graph_admin_notify.py` |
| 512 | 申請單各終態觸發管理員通知(整合 api_key_requests) | pending | ✓ | 501, 511 | `backend/app/api/v1/api_key_requests.py`、`backend/tests/api/test_api_key_requests_admin_notify.py` |

## 並行批次

- **批次 A(可同時認領,零依賴)**:501(env)、511(寄信底層 + 模板)。兩者 `affected_files` 互不重疊。
- **批次 B**:502(待 501)。與 511 可並行(檔案不重疊)。
- **批次 C**:503(待 502)、512(待 501 + 511)。兩者檔案不重疊,可並行。

> 依賴鏈(功能一):**env(501)→ 排程 task(502)→ compose(503)**。
> 依賴鏈(功能二):**env(501)+ 寄信底層(511)→ 觸發整合(512)**。
> **無前端 / e2e task**:propose 明列前端呈現排程狀態、模型管理頁改動皆 Out of Scope;兩功能皆後端,Playwright 預設停用,驗證走 pytest + 手動。

## 檔案零重疊驗證

- 501(config + env)、502(tasks/model_sync + scheduler + services/sync + task test)、503(兩 compose 檔)、511(email_graph + 兩模板 + email test)、512(api_key_requests + api test)——`affected_files` **互不重疊**,序列化純由 `depends_on` 驅動。
- 502 觸及 `services/sync.py`:僅**新增一個 optional 參數**(`audit_meta`,預設 `None` = 現況),不改同步邏輯本體;無其他 task 觸及該檔。

## 已決議(2026-07-16 user 拍板;對齊 propose §D 決議表)

worker 不必再問 user:

- **D.1 排程精確度**:env `MODEL_SYNC_INTERVAL_DAYS`(整數,預設 3)於 import 時組 cron `0 0 */N * *`(每 N 天 00:00,接受月底邊界近似);**不**做嚴格游標版。影響 501 / 502。
- **D.2 稽核 actor + trigger**:排程同步 actor = 種子系統管理員(`get_by_account(INITIAL_ADMIN_ACCOUNT)`);稽核 `extra` 加 `trigger="scheduler"` 以區分排程 vs 手動。影響 502。
- **D.3 節流 / 鎖**:排程遇 `sync_throttled` / `sync_in_progress`(`AppError` code=425)→ log(info)後 return,**不** raise、不重試。影響 502。
- **D.4 收件解析**:管理員收件以 `get_by_account(INITIAL_ADMIN_ACCOUNT).email` 取;無 email → log 略過。影響 512。
- **D.5 觸發範圍**:**所有終態轉換都寄**(建立時自動判決 `cancelled` / `manual_pending` / `agent_done` + 人工 `done` / `revoked` / `cancelled`)。影響 512。
- **D.6 通知結果**:**僅 log,不落 DB**(零 migration)。影響 512。
- **D.7 寄信落點**:抽共用內部 `_send_mail(*, to, subject, html, text)`,`send_provision_email` 與新 `send_admin_notify_email` 共用底層。影響 511。

## 拆解註記(orchestrator)

- **scope 守門**:5 task 全數映自 propose `In Scope`(功能一:排程 task / 掛載 / 系統 actor / 節流相容 / env;功能二:收件解析 / 通知寄送 / 觸發點 / env),無 orphan、無超出 scope 偷渡。
- **§B.1「不動 sync」與 D.2「加 trigger 標記」的調和**:propose §B.1 原文「不動 `sync_models_and_credits`」指**同步邏輯本體不改**;為落實已拍板的 D.2 trigger 標記,502 於 `sync_models_and_credits` **新增一個 optional `audit_meta` 參數**(預設 `None`,merge 進既有 `audit_extra` 後傳 `write_audit`),行為向下相容、手動同步路徑零影響。此為最小侵入解,已於本註記顯式記錄。
- **無 DB migration**:兩功能皆不動 schema(D.6 僅 log);全版無 alembic 產出。
- **env 集中一 task**:三顆新 env(`MODEL_SYNC_SCHEDULE_ENABLED` / `MODEL_SYNC_INTERVAL_DAYS` / `APIREQ_ADMIN_NOTIFY_ENABLED`)同動 `config.py` + `.env.example`,合為 501 一 task 避免同檔互鎖。
