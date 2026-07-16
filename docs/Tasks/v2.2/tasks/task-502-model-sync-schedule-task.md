---
id: task-502
title: 模型自動同步排程 task + scheduler 掛載 + trigger 稽核標記
status: done
parallel: true
depends_on: [task-501]
affected_files:
  - backend/app/tasks/model_sync.py
  - backend/app/tasks/scheduler.py
  - backend/app/services/sync.py
  - backend/tests/tasks/test_model_sync_dispatch.py
estimated_hours: 3
---

## 目標

新增 taskiq 排程任務,每 N 天 00:00 自動呼叫既有 `sync_models_and_credits(...)` 同步 OpenRouter 模型清單;掛載進 scheduler 進程,並以 `trigger="scheduler"` 稽核標記區分排程 vs 手動(propose §B.1 / §D.1 / §D.2 / §D.3)。

## 範圍(只做這些)

- **新任務模組** `backend/app/tasks/model_sync.py`:
  - import 時 `_INTERVAL_DAYS = coerce_int_env("MODEL_SYNC_INTERVAL_DAYS", os.environ.get("MODEL_SYNC_INTERVAL_DAYS"), 3)`,排程任務 `scheduled_sync_models` 帶 `@broker.task(schedule=[{"cron": f"0 0 */{_INTERVAL_DAYS} * *"}])`(逐字沿 `ai_model_eval.py` 的 `_BEAT_INTERVAL` import 時定型 + CI-importability 慣例:標籤值讀 `os.environ`,函式體走 `get_settings()`、延遲 import `SessionLocal`)。
  - 任務體:`get_settings()`;`MODEL_SYNC_SCHEDULE_ENABLED` false → log(debug)後 `return`(對齊 `dispatch_unevaluated` 短路)。true → 自建 `SessionLocal` + `httpx.AsyncClient` + `OpenRouterClient`(沿 `evaluate_usage_log_task` 建法)。
  - **系統 actor**:`UserRepository(db).get_by_account(settings.INITIAL_ADMIN_ACCOUNT)`;查無 → log(warning)後 `return`(不同步)。有 → 帶 `actor_user_uid=admin.user_uid` / `actor_role=admin.role` + `audit_meta={"trigger": "scheduler"}` 呼叫 `sync_models_and_credits`,再 `await db.commit()`。
  - **節流 / 鎖**:`try` 包 `sync_models_and_credits`,`except AppError as e:` 若 `e.key in {"sync_throttled", "sync_in_progress"}` → log(info)後 `return`(不 raise);其他 `AppError` / 例外照拋(交 taskiq 重試)。
- **`sync_models_and_credits` 最小擴充**(調和 §B.1「不動本體」與 D.2):新增 keyword-only optional 參數 `audit_meta: dict[str, Any] | None = None`,於既有 `audit_extra` 後 `audit_extra.update(audit_meta or {})` 再傳 `write_audit(..., extra=audit_extra)`。**不動**其餘同步邏輯;預設 `None` = 現況完全一致,手動同步端點(`api/v1/models.py`)零影響。
- **scheduler 掛載**:`backend/app/tasks/scheduler.py` 追加 `import app.tasks.model_sync  # noqa: F401`(mirror 既有 `import app.tasks.ai_model_eval`)。
- **不動**:`_sync_models` / `ModelRepository` / `POST /models/sync` 端點 / 前端 `SyncButton`。

## Acceptance

- [ ] `cd backend && uv run python -c "import app.tasks.model_sync as m; print('ok')"` 印出 `ok`(模組可 import、cron label 定型無誤)
- [ ] `cd backend && uv run pytest tests/tasks/test_model_sync_dispatch.py -q` 全綠;測試涵蓋:❶ `MODEL_SYNC_SCHEDULE_ENABLED=false` → 不呼叫 `sync_models_and_credits`;❷ enable=true 且 admin 存在 → 呼叫一次且帶 `audit_meta={"trigger":"scheduler"}`;❸ `sync_models_and_credits` 拋 `AppError("sync_throttled")` → 任務不 re-raise(靜默略過);❹ admin 查無 → 不呼叫同步
- [ ] `grep -q "import app.tasks.model_sync" backend/app/tasks/scheduler.py`(scheduler 已掛載)
- [ ] `cd backend && uv run python -c "import inspect,app.services.sync as s; assert 'audit_meta' in inspect.signature(s.sync_models_and_credits).parameters; print('ok')"` 印出 `ok`
- [ ] `cd backend && uv run ruff check app/tasks/model_sync.py app/tasks/scheduler.py app/services/sync.py && uv run mypy app/tasks/model_sync.py app/services/sync.py` 全綠

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/03-async-and-tx.md`
- `docs/Design-Base/03-backend/05-exceptions-and-logging.md`
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/03-backend/92-project-permission.md`
- `docs/Design-Base/90-third-party-service/50-openrouter.md`
- `docs/Design-Base/00-overview/05-timezone.md`
