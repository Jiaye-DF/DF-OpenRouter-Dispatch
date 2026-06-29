---
id: task-003
title: 同步 service + models / model-tiers / openrouter-keys 後端端點
status: done
parallel: false
depends_on: [task-001, task-002]
affected_files:
  - backend/app/models/model.py
  - backend/app/models/model_tier.py
  - backend/app/models/__init__.py
  - backend/app/schemas/model.py
  - backend/app/schemas/model_tier.py
  - backend/app/repositories/model.py
  - backend/app/repositories/model_tier.py
  - backend/app/services/sync.py
  - backend/app/api/v1/models.py
  - backend/app/api/v1/model_tiers.py
  - backend/app/api/v1/openrouter_keys.py
  - backend/app/api/v1/__init__.py
estimated_hours: 4
---

## 目標
建立 ORM models / Pydantic schemas / repositories,撰寫 `sync.py`(advisory lock + 10 min throttle + 模型 upsert + 自動分級 + 餘額同步 + 計數),並掛上 `/api/v1/models`(列表/單筆/PATCH/sync 4 端點)、`/api/v1/model-tiers`(CRUD 5 端點)、`/api/v1/openrouter-keys` GET response 加 4 餘額欄(僅 admin)。

## Acceptance
- [x] `uv run pytest backend/tests/test_models_sync.py backend/tests/test_model_tiers_crud.py -q` 通過(全新建表/既有更新/OR 下架/上游失敗 rollback/10min throttle/餘額部分失敗 best-effort/tier 唯一性/tier_in_use)
- [x] `curl -s localhost:8000/api/v1/models | jq '.data[0].model_uid'` 有值;PATCH 僅允許改 `is_active`/`tier_key`,送 `name` 不生效
- [x] `POST /api/v1/models/sync` 並發回 425 `sync_in_progress`;距上次同步 < 10min 回 425 `sync_throttled` 且 `data.retry_after_seconds` 有值
- [x] `DELETE /api/v1/model-tiers/{uid}` 仍被引用回 400 `tier_in_use`(`data.using_models[]`);重複 `key` POST 回 400 `tier_key_taken`
- [x] `openrouter-keys` GET 對 admin 回 `credits_*` 4 欄、對一般使用者剔除;sync / model PATCH / tier CRUD 均寫稽核 Log;`/api/docs` 可見全部新端點

## 必讀檔(Just-in-time)
- [`03-backend/01-routing.md`](../../../Design-Base/03-backend/01-routing.md) · [`03-backend/02-auth.md`](../../../Design-Base/03-backend/02-auth.md) · [`03-backend/03-async-and-tx.md`](../../../Design-Base/03-backend/03-async-and-tx.md) · [`03-backend/05-exceptions-and-logging.md`](../../../Design-Base/03-backend/05-exceptions-and-logging.md)
- [`03-backend/07-testing.md`](../../../Design-Base/03-backend/07-testing.md) · [`03-backend/90-project-backend.md`](../../../Design-Base/03-backend/90-project-backend.md) · [`03-backend/92-project-permission.md`](../../../Design-Base/03-backend/92-project-permission.md)
- [`04-databases/04-sql-safety.md`](../../../Design-Base/04-databases/04-sql-safety.md) · [`04-databases/07-connection.md`](../../../Design-Base/04-databases/07-connection.md) · [`90-third-party-service/50-openrouter.md`](../../../Design-Base/90-third-party-service/50-openrouter.md) · [`90-third-party-service/02-rate-and-cost.md`](../../../Design-Base/90-third-party-service/02-rate-and-cost.md)
