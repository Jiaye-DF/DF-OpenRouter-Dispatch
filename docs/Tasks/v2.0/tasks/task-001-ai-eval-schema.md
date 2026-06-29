---
id: task-001
title: 建評審地基三張表 + SQLAlchemy 模型 + Alembic migration
status: done
parallel: true
depends_on: []
affected_files:
  - backend/app/models/ai_eval_judge_setting.py
  - backend/app/models/ai_model_evaluation.py
  - backend/app/models/ai_model_eval_candidate.py
  - backend/app/models/__init__.py
  - backend/alembic/versions/0018_ai_eval_foundation.py
estimated_hours: 3
---

## 目標

依 propose §4 建立模型適配評審的三張地基表(全 `ai_` 前綴),含 SQLAlchemy 模型與單一 Alembic migration;**本版只建表,無任何資料寫入**。

## 範圍

- `ai_eval_judge_settings`(判別模型設定):`model_uid`(FK→`models`)、`ai_judge_slot`(SMALLINT 1/2/3,唯一)。
- `ai_model_evaluations`(評審結果父表,**僅判別階段欄位**):`usage_log_uid`(FK,UNIQUE)、`department_uid`/`user_uid`(denormalize, null)、`ai_original_model`、`ai_task_summary`/`ai_task_intent`/`ai_task_complexity`(null)、`status`、`ai_evaluated_at`(null)。
- `ai_model_eval_candidates`(候選子表):`ai_evaluation_uid`(FK)、`model_uid`(FK→`models`)、`ai_recommend_model`/`ai_recommend_tier`/`ai_recommend_reason`(null)、`ai_fit_score`(NUMERIC(4,3), null)、`ai_self_vote`(null)。
- **重跑 / 人類裁決 / 成本欄位本版不建**(各留 v2.0.2 / v2.0.3 / v2.0.4 以後續 migration 增補)。

## Acceptance

- [ ] 三表皆含專案必備欄位 `pid` / `<table>_uid`(UUIDv7)/ `is_active` / `is_deleted` / `created_at` / `updated_at`(對齊 `04-databases/90-project-database.md`、`04-databases/00-overview.md`)
- [ ] `cd backend && uv run alembic upgrade head` 成功建立三表
- [ ] `uv run alembic downgrade -1` round-trip 成功(三表移除無殘留)
- [ ] migration **revision id ≤ 32 字元**(避免重蹈 0016/0017 超過 `alembic_version VARCHAR(32)` 的 deploy 失敗)
- [ ] 三模型已註冊於 `backend/app/models/__init__.py`;`uv run python -c "import app.models"` 無錯
- [ ] FK 正確:`ai_eval_judge_settings.model_uid` / `ai_model_eval_candidates.model_uid` → `models`;`ai_model_evaluations.usage_log_uid` → `usage_logs`(UNIQUE);`ai_model_eval_candidates.ai_evaluation_uid` → `ai_model_evaluations`
- [ ] `uv run ruff check app/models` 無 warning;`uv run mypy app/models` green

## 必讀檔(Just-in-time)

- `AGENTS.md`
- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/04-databases/00-overview.md`
- `docs/Design-Base/04-databases/01-identifiers.md`
- `docs/Design-Base/04-databases/06-timezone.md`
- `docs/Design-Base/04-databases/08-alembic.md`
- `docs/Design-Base/04-databases/90-project-database.md`
