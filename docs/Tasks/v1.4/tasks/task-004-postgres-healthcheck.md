---
id: task-004
title: postgres healthcheck 避免 alembic 競態啟動失敗
status: done
parallel: true
depends_on: []
affected_files:
  - docker-compose-prod.yml
estimated_hours: 1
---

## 目標
為 postgres 加上 healthcheck,讓 alembic / backend service 等 postgres ready 後再啟動,消除第一次啟動的競態 false-positive 錯誤。

## Acceptance
- [x] `docker-compose-prod.yml` 為 postgres 加 `healthcheck`(使用 `pg_isready`)
- [x] alembic service `depends_on` 改為 `condition: service_healthy`
- [x] backend service `depends_on` 改為 `condition: service_healthy`
- [x] 冷啟動時 alembic 不再因 postgres 未 ready 而首次失敗

## 必讀檔(Just-in-time)
- [`06-Coolify-CD/01-compose.md`](../../../Design-Base/06-Coolify-CD/01-compose.md) · [`06-Coolify-CD/05-deploy-flow.md`](../../../Design-Base/06-Coolify-CD/05-deploy-flow.md)
