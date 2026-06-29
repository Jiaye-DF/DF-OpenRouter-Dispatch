---
id: task-204
title: 模型管理+稽核+計量群 5 表 model comment=
status: done
parallel: true
depends_on: []
affected_files:
  - backend/app/models/model.py
  - backend/app/models/model_tier.py
  - backend/app/models/allowed_model.py
  - backend/app/models/audit_log.py
  - backend/app/models/usage_log.py
estimated_hours: 3
---

## 目標

為模型管理 / 稽核 / 計量群 5 張表(`models` / `model_tiers` / `allowed_models` / `audit_logs` / `usage_logs`)的 model 各**非-mixin 欄位**補 `comment=`,作為 task-206 autogenerate 的真相源。

## 設計

- 逐欄 `mapped_column(..., comment=...)`,中英雙語。
- `pid` / `<entity>_uid` 用 tasks-v2.0.2.md §「罐頭文案基準」逐字文案。
- `usage_logs` 業務欄位(含 v1.x 既有 + v2.0.1 新加的 `ai_evaluated_at` / `ai_evaluated_status`)**直接轉用 model 既有行內中文註解**為 comment。
- **不**改型別 / 約束;**不**動 `TimestampMixin`(task-202);**不**動 migration。

## Acceptance

- [ ] 5 表非-mixin 欄位皆有 comment:
```
cd backend && uv run python -c "
from app.models import Model, ModelTier, AllowedModel, AuditLog, UsageLog
MIXIN={'is_active','is_deleted','created_at','updated_at'}
for M in (Model,ModelTier,AllowedModel,AuditLog,UsageLog):
    for c in M.__table__.columns:
        if c.name in MIXIN: continue
        assert c.comment, f'{M.__tablename__}.{c.name} 缺 comment'
"
```
- [ ] `cd backend && uv run ruff check app/models/ && uv run mypy app/models/model.py app/models/model_tier.py app/models/allowed_model.py app/models/audit_log.py app/models/usage_log.py`

## 必讀檔(Just-in-time)
- `04-databases/00-overview.md`(§ 自我說明)
- `04-databases/90-project-database.md`(§ 1 / § 3.5)
