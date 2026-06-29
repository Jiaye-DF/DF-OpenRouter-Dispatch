---
id: task-107
title: docker-compose 常駐服務(worker / scheduler / redis)
status: pending
parallel: false
depends_on: [task-101, task-106]
affected_files:
  - docker-compose.dev.yml
  - docker-compose-prod.yml
estimated_hours: 2
---

## 目標

把評審管線變成 24/7 常駐:compose 新增 `redis`(AOF 持久化)、`taskiq-worker`、`taskiq-scheduler`,皆 `restart: unless-stopped`,對齊 propose §4「持續運行保證」。

## 範圍

- `docker-compose.dev.yml` + `docker-compose-prod.yml`:
  - `redis`:開 AOF(`--appendonly yes`),掛 volume 持久化,加 healthcheck(`redis-cli ping`)。
  - `taskiq-worker`:`taskiq worker app.tasks.broker:broker ...`,`restart: unless-stopped`,`depends_on: redis`(healthy)。
  - `taskiq-scheduler`:`taskiq scheduler app.tasks.scheduler:scheduler ...`,`restart: unless-stopped`,`depends_on: redis`(healthy)。
  - 沿用既有 backend image / env_file 注入(`06-Coolify-CD/01-compose.md`、`90-project-deployment.md`);鎖映像版本,**禁** `latest`。
- 延遲語意:worker/scheduler **常駐**,非間歇排程(propose §4)。

## Acceptance

- [ ] `docker compose -f docker-compose.dev.yml config` 解析無錯,輸出含 `redis`、`taskiq-worker`、`taskiq-scheduler` 三服務
- [ ] `docker compose -f docker-compose-prod.yml config` 解析無錯,同上三服務存在
- [ ] 三服務皆有 `restart: unless-stopped`:`grep -c 'unless-stopped' docker-compose-prod.yml` ≥ 3(含既有服務則更多)
- [ ] `redis` 服務 command 含 `--appendonly yes` 且掛載具名 volume(grep 斷言)
- [ ] worker/scheduler command 指向 `app.tasks.broker:broker` / `app.tasks.scheduler:scheduler`(grep 斷言)
- [ ] `docker compose -f docker-compose.dev.yml up -d redis taskiq-worker taskiq-scheduler` 後三 container 進入 running/healthy(手測,記錄於 commit)

## 必讀檔(Just-in-time)

- `AGENTS.md`
- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/00-overview/03-env-layers.md`
- `docs/Design-Base/06-Coolify-CD/00-overview.md`
- `docs/Design-Base/06-Coolify-CD/01-compose.md`
- `docs/Design-Base/06-Coolify-CD/04-env-and-secrets.md`
- `docs/Design-Base/06-Coolify-CD/90-project-deployment.md`
