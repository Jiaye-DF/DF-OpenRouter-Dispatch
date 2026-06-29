---
id: task-001
title: Migration V8-V11 建立 models / model_tiers 表 + openrouter_keys/usage_logs 加欄位
status: done
parallel: true
depends_on: []
affected_files:
  - migrations/V8__models.sql
  - migrations/V9__model_tiers.sql
  - migrations/V10__openrouter_keys_credits.sql
  - migrations/V11__usage_logs_model_uid.sql
estimated_hours: 3
---

## 目標
建立 `models` 與 `model_tiers` 兩張主檔表(含 index / set_updated_at Trigger / 必備欄位),`model_tiers` seed 4 級(free/cheap/standard/expensive);ALTER `openrouter_keys` 加 4 餘額欄、ALTER `usage_logs` 加 `model_uid` FK + index。

## Acceptance
- [x] `alembic upgrade head` 與 `alembic downgrade` round-trip 成功,V8-V11 皆可正反向遷移
- [x] `models` 表含 `model_uid UUID UNIQUE`、`openrouter_model_id VARCHAR(128) UNIQUE`、`is_active`/`is_deleted`/`created_at`/`updated_at` 必備欄位,且 `idx_models_active`、`idx_models_tier_key` partial index(`WHERE is_deleted = FALSE`)存在
- [x] `model_tiers` seed 4 列,`SELECT key FROM model_tiers ORDER BY sort_order` 回 `free,cheap,standard,expensive`;`key` 有 UNIQUE 約束
- [x] `openrouter_keys` 新增 `credits_used_usd`/`credits_limit_usd`/`credits_is_free_tier`/`credits_synced_at` 4 欄;`usage_logs` 新增 `model_uid UUID REFERENCES models(model_uid)` 與 `idx_usage_logs_model_uid_time` index
- [x] 兩表皆掛 `set_updated_at` Trigger(`grep trg_models_updated_at` 與 `grep trg_model_tiers_updated_at` 命中)

## 必讀檔(Just-in-time)
- [`04-databases/00-overview.md`](../../../Design-Base/04-databases/00-overview.md) · [`04-databases/01-identifiers.md`](../../../Design-Base/04-databases/01-identifiers.md) · [`04-databases/02-soft-delete.md`](../../../Design-Base/04-databases/02-soft-delete.md)
- [`04-databases/05-precision.md`](../../../Design-Base/04-databases/05-precision.md) · [`04-databases/08-alembic.md`](../../../Design-Base/04-databases/08-alembic.md) · [`04-databases/09-indexes-and-perf.md`](../../../Design-Base/04-databases/09-indexes-and-perf.md)
- [`04-databases/06-timezone.md`](../../../Design-Base/04-databases/06-timezone.md) · [`04-databases/90-project-database.md`](../../../Design-Base/04-databases/90-project-database.md)
