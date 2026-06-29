---
id: task-001
title: Alembic 0002/0003 migration — models.provider/model_key rename、openrouter_keys RPM 欄位、internal_keys 表
status: done
parallel: false
depends_on: []
affected_files:
  - backend/alembic/versions/0002_provider_rate_limit.py
  - backend/alembic/versions/0003_internal_keys.py
  - backend/app/models/model.py
  - backend/app/models/openrouter_key.py
  - backend/app/models/internal_key.py
estimated_hours: 3
---

## 目標
建立 v1.2 schema 變更:`models` 加 `provider` 並把 `openrouter_model_id` 改名 `model_key`、`openrouter_keys` 加 RPM/最小間隔欄位與 CHECK,並新增 `internal_keys` 表(DB-driven internal provider),同步 SQLAlchemy model。

## Acceptance
- [x] `0002_provider_rate_limit.py`:`models` 加 `provider VARCHAR(32) NOT NULL DEFAULT 'openrouter'`、rename `openrouter_model_id`→`model_key`(含 unique index rename)、加 `idx_models_provider ... WHERE is_deleted = FALSE`
- [x] `0002` 對 `openrouter_keys` 加 `rpm_limit INT NOT NULL DEFAULT 0`、`min_request_interval_ms INT NOT NULL DEFAULT 0` 及兩條 `CHECK (>= 0)`
- [x] `0003_internal_keys.py` 建立 `internal_keys` 表(`internal_key_uid UUID UNIQUE`、`base_url`、`key_ciphertext BYTEA NULL`、`key_last4`、RPM/interval、`is_active`/`is_deleted`、兩條 CHECK),無 `department_uid`
- [x] `app/models/{model,openrouter_key,internal_key}.py` SQLAlchemy 屬性與上述欄位一致;`model.py` 以 `model_key` 取代 `openrouter_model_id`
- [x] `alembic upgrade head` 與 `downgrade` 皆可逆且不報錯

## 必讀檔(Just-in-time)
- [`04-databases/08-alembic.md`](../../../Design-Base/04-databases/08-alembic.md) · [`04-databases/01-identifiers.md`](../../../Design-Base/04-databases/01-identifiers.md) · [`04-databases/02-soft-delete.md`](../../../Design-Base/04-databases/02-soft-delete.md) · [`04-databases/09-indexes-and-perf.md`](../../../Design-Base/04-databases/09-indexes-and-perf.md) · [`04-databases/03-passwords-and-pii.md`](../../../Design-Base/04-databases/03-passwords-and-pii.md)
