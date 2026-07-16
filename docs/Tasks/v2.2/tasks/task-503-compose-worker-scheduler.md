---
id: task-503
title: docker-compose 更新(worker command 追加模組 + prod env 注入)
status: done
parallel: true
depends_on: [task-502]
affected_files:
  - docker-compose.dev.yml
  - docker-compose-prod.yml
estimated_hours: 1.5
---

## 目標

讓 taskiq worker 註冊新排程任務模組、讓 scheduler / worker 進程拿得到新 env,使模型自動同步排程實際生效(propose §B.1 / §C「compose 注入」)。

## 範圍(只做這些)

- **worker command 追加模組**(兩檔):`taskiq-worker` 的 `command` 由 `["taskiq", "worker", "app.tasks.broker:broker", "app.tasks.ai_model_eval"]` 追加 `"app.tasks.model_sync"`(worker 才註冊 `scheduled_sync_models`)。
- **dev(`docker-compose.dev.yml`)**:taskiq 服務走 `env_file: .env`,新 env 自動可見 → **僅需**改 worker command(無需手動列 env)。
- **prod(`docker-compose-prod.yml`)**:無 `env_file`、走顯式 `environment:` mapping → 於 **`taskiq-worker` 與 `taskiq-scheduler` 兩者**的 `environment:` 追加 `MODEL_SYNC_SCHEDULE_ENABLED: ${MODEL_SYNC_SCHEDULE_ENABLED}` 與 `MODEL_SYNC_INTERVAL_DAYS: ${MODEL_SYNC_INTERVAL_DAYS}`(scheduler 尤其必要:cron label 於 import 時讀該 env);`APIREQ_ADMIN_NOTIFY_ENABLED: ${APIREQ_ADMIN_NOTIFY_ENABLED}` 追加至 **backend / api 服務** 的 `environment:`(申請單通知於 API 進程觸發)。
- **不動**:scheduler command(不變;它 import `scheduler.py`,由 502 掛載模組)、Redis / postgres / 其他服務定義、既有 env。

## Acceptance

- [ ] `grep -q "app.tasks.model_sync" docker-compose.dev.yml && grep -q "app.tasks.model_sync" docker-compose-prod.yml`(兩檔 worker command 皆含新模組)
- [ ] `grep -c "MODEL_SYNC_INTERVAL_DAYS" docker-compose-prod.yml | grep -qE "^[2-9]"`(prod 至少 worker + scheduler 兩處注入)
- [ ] `grep -q "APIREQ_ADMIN_NOTIFY_ENABLED" docker-compose-prod.yml`(prod backend 服務注入通知開關)
- [ ] `docker compose -f docker-compose.dev.yml config -q && docker compose -f docker-compose-prod.yml config -q`(兩 compose 檔 YAML 合法、可解析;若本機無 docker,改以 `python -c "import yaml,sys; [yaml.safe_load(open(f)) for f in ['docker-compose.dev.yml','docker-compose-prod.yml']]; print('ok')"` 驗 YAML 合法)

## 必讀檔(Just-in-time)

- `docs/Design-Base/06-Coolify-CD/00-overview.md`
- `docs/Design-Base/06-Coolify-CD/01-compose.md`
- `docs/Design-Base/06-Coolify-CD/04-env-and-secrets.md`
- `docs/Design-Base/06-Coolify-CD/90-project-deployment.md`
- `docs/Design-Base/00-overview/03-env-layers.md`
