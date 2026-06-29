---
id: task-001
title: 後端骨架 + 核心模組(config / response / exceptions / crypto)+ compose
status: done
parallel: true
depends_on: []
affected_files:
  - backend/app/main.py
  - backend/app/core/config.py
  - backend/app/core/response.py
  - backend/app/core/exceptions.py
  - backend/app/core/deps.py
  - backend/app/core/security.py
  - backend/app/core/crypto.py
  - backend/pyproject.toml
  - backend/Dockerfile
  - docker-compose.yml
  - docker-compose.dev.yml
  - .env.example
estimated_hours: 4
---

## 目標

建立 FastAPI 後端骨架與跨功能核心:`ApiResponse` 外殼、`AppError` + 三個 exception handler、`Settings`(pydantic-settings + production fail-fast)、依賴注入、JWT/argon2id security、AES-256-GCM crypto helper,以及可一鍵啟動的 compose。

## Acceptance

- [x] `docker compose -f docker-compose.dev.yml up --build` 後端起,`curl -s localhost:8000/api/docs | grep -q swagger`
- [x] `cd backend && uv run ruff check . && uv run mypy .` 全綠
- [x] `main.py` 以 `docs_url="/api/docs"` 初始化(對齊 `00-overview/04-api-docs.md`)
- [x] 未捕捉例外回 `{success:false, code:500, detail:"操作失敗"}`(`uv run pytest tests/core/test_response.py`)
- [x] production 模式缺 `JWT_SECRET` / `ENCRYPTION_KEY` 時 fail-fast(`tests/core/test_config.py`)

## 必讀檔(Just-in-time)

- [`03-backend/00-overview.md`](../../../Design-Base/03-backend/00-overview.md)
- [`03-backend/01-routing.md`](../../../Design-Base/03-backend/01-routing.md)
- [`03-backend/04-config.md`](../../../Design-Base/03-backend/04-config.md)
- [`03-backend/05-exceptions-and-logging.md`](../../../Design-Base/03-backend/05-exceptions-and-logging.md)
- [`00-overview/02-secrets.md`](../../../Design-Base/00-overview/02-secrets.md) · [`04-api-docs.md`](../../../Design-Base/00-overview/04-api-docs.md)
