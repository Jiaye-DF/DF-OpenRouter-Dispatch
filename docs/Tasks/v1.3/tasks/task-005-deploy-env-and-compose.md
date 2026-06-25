---
id: task-005
title: 部署 env.example 與 docker-compose 注入 SSO 變數
status: done
parallel: true
depends_on: [task-002]
affected_files:
  - .env.example
  - docker-compose-prod.yml
estimated_hours: 1
---

## 目標
把 SSO 相關設定加進部署層:`.env.example` 補整段(含註解),`docker-compose-prod.yml` backend `environment` 注入對應變數,並以字面值 `8` 注入 `SSO_TIMEOUT_SECONDS` 避免空字串解析錯誤。

## Acceptance
- [x] `.env.example` 加 SSO 整段(`SSO_URL` / `SSO_APP_ID` / `SSO_APP_SECRET` / `BACKEND_URL` / `FRONTEND_URL` / `SSO_TIMEOUT_SECONDS`)含註解
- [x] `docker-compose-prod.yml` backend `environment` 段加上述 SSO 對應變數
- [x] `SSO_TIMEOUT_SECONDS` 以字面值 `8` 注入,避免空字串解析錯誤
- [x] config 用到的每個 SSO env 鍵名皆於 `.env.example` 定義,無缺漏

## 必讀檔(Just-in-time)
- [`06-Coolify-CD/01-compose.md`](../../../Design-Base/06-Coolify-CD/01-compose.md) · [`06-Coolify-CD/04-env-and-secrets.md`](../../../Design-Base/06-Coolify-CD/04-env-and-secrets.md) · [`00-overview/03-env-layers.md`](../../../Design-Base/00-overview/03-env-layers.md) · [`00-overview/02-secrets.md`](../../../Design-Base/00-overview/02-secrets.md)
