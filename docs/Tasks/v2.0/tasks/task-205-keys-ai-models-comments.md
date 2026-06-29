---
id: task-205
title: 金鑰+AI 群 7 表 model comment=
status: done
parallel: true
depends_on: []
affected_files:
  - backend/app/models/openrouter_key.py
  - backend/app/models/internal_key.py
  - backend/app/models/sdk_api_key.py
  - backend/app/models/api_key_request.py
  - backend/app/models/ai_eval_judge_setting.py
  - backend/app/models/ai_model_evaluation.py
  - backend/app/models/ai_model_eval_candidate.py
estimated_hours: 4
---

## 目標

為金鑰群(`openrouter_keys` / `internal_keys` / `sdk_api_keys` / `api_key_requests`)+ AI 分析群(`ai_eval_judge_settings` / `ai_model_evaluations` / `ai_model_eval_candidates`)共 7 張表的 model 各**非-mixin 欄位**補 `comment=`,作為 task-206 autogenerate 的真相源。

## 設計

- 逐欄 `mapped_column(..., comment=...)`,中英雙語。
- `pid` / `<entity>_uid` 用 tasks-v2.0.2.md §「罐頭文案基準」逐字文案。
- AI 三表(v2.0.0 建)欄位語意參考 propose-v2.0.0 §4 表格與 `0019` migration docstring。
- 金鑰類 model 的敏感欄位 comment **只描述用途,禁寫任何金鑰值 / 範例明文**(對齊 `90-project-task-spec §4.3`)。
- **不**改型別 / 約束;**不**動 `TimestampMixin`(task-202);**不**動 migration。

## Acceptance

- [ ] 7 表非-mixin 欄位皆有 comment:
```
cd backend && uv run python -c "
from app.models import OpenRouterKey, InternalKey, SdkApiKey, ApiKeyRequest, AiEvalJudgeSetting, AiModelEvaluation, AiModelEvalCandidate
MIXIN={'is_active','is_deleted','created_at','updated_at'}
for M in (OpenRouterKey,InternalKey,SdkApiKey,ApiKeyRequest,AiEvalJudgeSetting,AiModelEvaluation,AiModelEvalCandidate):
    for c in M.__table__.columns:
        if c.name in MIXIN: continue
        assert c.comment, f'{M.__tablename__}.{c.name} 缺 comment'
"
```
- [ ] 敏感欄位 comment 未洩漏值:`cd backend && ! grep -riE "(sk-|secret=|金鑰值為|example.*key)" app/models/openrouter_key.py app/models/internal_key.py app/models/sdk_api_key.py`
- [ ] `cd backend && uv run ruff check app/models/ && uv run mypy app/models/openrouter_key.py app/models/internal_key.py app/models/sdk_api_key.py app/models/api_key_request.py app/models/ai_eval_judge_setting.py app/models/ai_model_evaluation.py app/models/ai_model_eval_candidate.py`

## 必讀檔(Just-in-time)
- `04-databases/00-overview.md`(§ 自我說明)
- `04-databases/03-passwords-and-pii.md`
- `04-databases/90-project-database.md`(§ 1 / § 3.5)
- `01-propose/90-project-task-spec.md`(§ 4.3 敏感欄位)
