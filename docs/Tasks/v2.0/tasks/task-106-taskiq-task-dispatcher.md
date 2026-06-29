---
id: task-106
title: taskiq task + dispatcher/scheduler 接線
status: pending
parallel: false
depends_on: [task-101, task-102, task-105]
affected_files:
  - backend/app/tasks/ai_model_eval.py
  - backend/app/tasks/scheduler.py
estimated_hours: 3
---

## 目標

把 task-105 的 `evaluate_usage_log` 掛上 task-101 的 broker,並以 TaskiqScheduler 定期掃 task-102 旗標欄派發任務,形成 24/7 常駐評審管線(propose §4)。

## 範圍

- `backend/app/tasks/ai_model_eval.py`(新檔):
  - `@broker.task` 包裝 `evaluate_usage_log(usage_log_uid)`,設 `retry_on_error` + backoff,上限讀 `AI_EVAL_TASK_MAX_RETRIES`;超限標 `status='error'` 不卡整批。
  - `dispatch_unevaluated()`:`AI_EVAL_ENABLED` 為真才動;以 repo `fetch_unevaluated_log_uids(AI_EVAL_DISPATCH_BATCH_SIZE)` 撈待派,逐筆 `.kiq(uid)`;派發時上「派發中」標記防重複派發。
- `backend/app/tasks/scheduler.py`(新檔):TaskiqScheduler 設定,`AI_EVAL_BEAT_INTERVAL_SECONDS` 週期觸發 `dispatch_unevaluated`。
- **冪等**:依賴父表 `usage_log_uid` UNIQUE(task-104),重複投遞/重試不產生重複評審。

> **待 user 確認(propose §8.3)**:本版全量派發(逐筆未評審都跑),抽樣留 v2.1。

## Acceptance

- [ ] `cd backend && uv run python -c "from app.tasks.ai_model_eval import evaluate_usage_log_task, dispatch_unevaluated"` 無錯(task 已註冊於 broker)
- [ ] `cd backend && uv run python -c "from app.tasks.scheduler import scheduler"` 無錯
- [ ] `cd backend && uv run pytest tests/tasks/test_ai_model_eval_dispatch.py` 全綠(本 task 新增):mock repo 回 N 筆 → 斷言 `.kiq` 被呼叫 N 次;`AI_EVAL_ENABLED=false` → 0 次
- [ ] 測試:重複派發同一 uid 不致重複評審(以 mock service 斷言冪等守門)
- [ ] `cd backend && uv run ruff check app/tasks` 無 warning;`uv run mypy app/tasks` green

## 必讀檔(Just-in-time)

- `AGENTS.md`
- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/03-async-and-tx.md`
- `docs/Design-Base/03-backend/04-config.md`
- `docs/Design-Base/03-backend/05-exceptions-and-logging.md`
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/03-backend/08-performance.md`
