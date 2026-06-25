---
id: task-002
title: .env.example 分區註記 + 前端 NEXT_PUBLIC_API_BASE_URL build-time 注入
status: done
parallel: true
depends_on: []
affected_files:
  - .env.example
  - frontend/Dockerfile
  - docker-compose-prod.yml
estimated_hours: 2
---

## 目標
重整 `.env.example` 以作用域分區註記,並修正前端 `NEXT_PUBLIC_API_BASE_URL` 於 Coolify build 階段未帶入導致 bundle 內為空字串的問題。

## Acceptance
- [x] `.env.example` 每個變數以 `[BOTH]` / `[LOCAL]` / `[REMOTE]` / `[COOLIFY]` 註記適用環境
- [x] `frontend/Dockerfile` builder stage 加入 `NEXT_PUBLIC_API_BASE_URL` 的 `ARG` 與 `ENV`,值於 build 階段內聯進 client bundle
- [x] `docker-compose-prod.yml` frontend `build.args` 帶入 `NEXT_PUBLIC_API_BASE_URL`
- [x] build 後 client bundle 內 `NEXT_PUBLIC_API_BASE_URL` 為實際值而非空字串

## 必讀檔(Just-in-time)
- [`06-Coolify-CD/03-dockerfile-frontend.md`](../../../Design-Base/06-Coolify-CD/03-dockerfile-frontend.md) · [`06-Coolify-CD/04-env-and-secrets.md`](../../../Design-Base/06-Coolify-CD/04-env-and-secrets.md) · [`06-Coolify-CD/01-compose.md`](../../../Design-Base/06-Coolify-CD/01-compose.md)
- [`00-overview/03-env-layers.md`](../../../Design-Base/00-overview/03-env-layers.md) · [`00-overview/91-project-naming-env.md`](../../../Design-Base/00-overview/91-project-naming-env.md)
