---
id: task-406
title: taskiq task + dispatcher(dispatch_unrerun / rerun_evaluation_task)
status: done
parallel: true
depends_on: [task-403, task-405]
affected_files:
  - backend/app/tasks/ai_model_eval.py
  - backend/tests/tasks/test_ai_model_eval_rerun_dispatch.py
estimated_hours: 3
---

## 目標

在既有 `tasks/ai_model_eval.py` 加重跑的 worker task 與排程派發器,沿用評審派發的 beat 排程與批量常數(決議 #8),自動觸發 §5 重跑管線(propose §5.1)。

## 範圍(propose §5.1,決議 #3 / #8)

- `rerun_evaluation_task(ai_evaluation_uid: str)`(`@broker.task`,`retry_on_error` + `max_retries` 沿用既有 `_MAX_RETRIES`):worker 端自建 `SessionLocal` + `OpenRouterClient`,呼叫 task-405 `rerun_evaluation`;呼叫前以 repo 短路(父表 `ai_reran_at` 已非 NULL → 跳過,省 API)。session 擁有者 `await db.commit()`。
- `dispatch_unrerun()`(`@broker.task(schedule=[{"interval": _BEAT_INTERVAL}])`,**沿用既有 beat interval / batch 常數**,決議 #8):
  - `AI_RERUN_ENABLED=false` → `return 0`(完全不派發,零成本)。
  - `=true` → `fetch_unreran_evaluation_uids(AI_EVAL_DISPATCH_BATCH_SIZE)` 撈待重跑父評審,逐筆 `await rerun_evaluation_task.kiq(str(uid))`;回派發筆數。
- **不**加抽樣 / 吻合度門檻(決議 #3);**不**新增 env(決議 #8)。
- 維持模組 CI-importability(對齊既有 docstring:task 標籤直讀 `os.environ`、延遲 import `app.core.database`)。

## 實作要點

- `scheduler.py` 已 `import app.tasks.ai_model_eval`,新 schedule label 自動被 `LabelScheduleSource` 撈到 → **不需動 scheduler.py**。
- 測試對齊既有 `tests/tasks/test_ai_model_eval_dispatch.py`:mock broker `.kiq` / repo,驗 enabled 旗標分流與派發筆數。

## Acceptance

- [ ] `cd backend && uv run pytest tests/tasks/test_ai_model_eval_rerun_dispatch.py` 全綠
- [ ] 測試涵蓋:(a) `AI_RERUN_ENABLED=false` → `dispatch_unrerun()` 回 0、**無** `.kiq` 呼叫;(b) `=true` → 對 `fetch_unreran_evaluation_uids` 回的每筆呼叫一次 `rerun_evaluation_task.kiq`,回派發筆數;(c) `rerun_evaluation_task` 對已重跑(`ai_reran_at` 非 NULL)父評審短路跳過
- [ ] `cd backend && uv run python -c "import app.tasks.ai_model_eval as m; assert hasattr(m,'dispatch_unrerun') and hasattr(m,'rerun_evaluation_task'); print('ok')"`(裸環境可 import,印 `ok`)
- [ ] `cd backend && uv run ruff check app/tasks/ai_model_eval.py && uv run mypy app/tasks/ai_model_eval.py` 全綠

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/03-async-and-tx.md`
- `docs/Design-Base/03-backend/05-exceptions-and-logging.md`
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/00-overview/02-secrets.md`
- `docs/Design-Base/90-third-party-service/02-rate-and-cost.md`
</content>
