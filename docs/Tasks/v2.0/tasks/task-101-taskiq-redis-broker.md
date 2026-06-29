---
id: task-101
title: taskiq + Redis broker 基建 + 設定(env/config)
status: pending
parallel: true
depends_on: []
affected_files:
  - backend/pyproject.toml
  - backend/app/tasks/__init__.py
  - backend/app/tasks/broker.py
  - backend/app/core/config.py
  - .env.example
estimated_hours: 3
---

## 目標

建立 taskiq + Redis 排程基建底座(broker + result backend)與對應設定,供 task-106 的派發/評審任務掛載;本 task **不寫任何業務任務**,只交付可被 import 的 broker 與 env/Settings。

## 範圍

- `backend/pyproject.toml`:加 `taskiq`、`taskiq-redis`(broker 用 `ListQueueBroker`、result backend 用 `RedisAsyncResultBackend`),版本鎖到 patch(對齊 `00-overview/01-versions.md`)。
- `backend/app/tasks/broker.py`:建立 `broker = ListQueueBroker(TASKIQ_BROKER_URL).with_result_backend(RedisAsyncResultBackend(TASKIQ_RESULT_BACKEND_URL)).with_middlewares(SimpleRetryMiddleware())`;**禁**在 import 時連線(lazy)。可參考 [`examples/taskiq-demo/broker.py`](../../../../examples/taskiq-demo/broker.py)。
  - **必掛 `SimpleRetryMiddleware`**:否則 task-106 在 task 上標的 `retry_on_error` / `AI_EVAL_TASK_MAX_RETRIES` **不會生效**。
- `backend/app/core/config.py`:於 `Settings` 加 propose §7 變數 — `AI_EVAL_ENABLED`(預設 `false`)、`TASKIQ_BROKER_URL`、`TASKIQ_RESULT_BACKEND_URL`、`REDIS_URL`、`AI_EVAL_BEAT_INTERVAL_SECONDS`(300)、`AI_EVAL_DISPATCH_BATCH_SIZE`(100)、`AI_EVAL_TASK_MAX_RETRIES`(3)。`DEFAULT_OPENROUTER_KEY` 已存在則不重複。
- `.env.example`:同步加上述鍵與預設值(對齊 `00-overview/02-secrets.md`、`03-env-layers.md`;機密不填實值)。

## Acceptance

- [ ] `cd backend && uv sync` 成功,`uv run python -c "import taskiq, taskiq_redis"` 無錯
- [ ] `cd backend && uv run python -c "from app.tasks.broker import broker; print(type(broker).__name__)"` 印出 broker 類名且**不**發起連線
- [ ] `cd backend && uv run python -c "from app.core.config import get_settings; s=get_settings(); print(s.AI_EVAL_ENABLED, s.TASKIQ_BROKER_URL, s.AI_EVAL_BEAT_INTERVAL_SECONDS)"` 印出三值,預設 `False redis://... 300`
- [ ] `.env.example` 含全部 7 個新鍵:`grep -E 'AI_EVAL_ENABLED|TASKIQ_BROKER_URL|TASKIQ_RESULT_BACKEND_URL|REDIS_URL|AI_EVAL_BEAT_INTERVAL_SECONDS|AI_EVAL_DISPATCH_BATCH_SIZE|AI_EVAL_TASK_MAX_RETRIES' .env.example | wc -l` ≥ 7
- [ ] `cd backend && uv run ruff check app/tasks app/core/config.py` 無 warning;`uv run mypy app/tasks app/core/config.py` green

## 必讀檔(Just-in-time)

- `AGENTS.md`
- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/00-overview/01-versions.md`
- `docs/Design-Base/00-overview/02-secrets.md`
- `docs/Design-Base/00-overview/03-env-layers.md`
- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/04-config.md`
