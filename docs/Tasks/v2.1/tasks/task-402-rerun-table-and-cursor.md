---
id: task-402
title: 新表 model + 父表游標欄 + migration
status: done
parallel: true
depends_on: []
affected_files:
  - backend/app/models/ai_model_eval_rerun.py
  - backend/app/models/ai_model_evaluation.py
  - backend/app/models/__init__.py
  - backend/alembic/versions/0026_ai_eval_reruns.py
estimated_hours: 3
---

## 目標

建立 challenger 真實重跑 + 對比結果新表 `ai_model_eval_reruns`,並為父表 `ai_model_evaluations` 增重跑游標兩欄;以單一 migration `0026` 落地(propose §4)。

## 範圍(propose §4.1 / §4.2)

### 新表 `ai_model_eval_reruns`(一筆 = 一個 challenger 的真實重跑 + 對比)

必備欄位(`pid` / `ai_eval_rerun_uid` / `is_active` / `is_deleted` / `created_at` / `updated_at`,對齊 `04-databases/90-project-database.md` + `base.py` Mixin)外,逐欄對照 propose §4.1 表:

- `ai_evaluation_uid` UUID(軟引用父評審)、`usage_log_uid` UUID(軟引用原 log)、`ai_candidate_uid` UUID?(去重取代表者)
- `original_model` String(128)、`rerun_model` String(128)、`model_uid` UUID?
- `request_content` JSONB?、`response_summary` JSONB?
- `prompt_tokens` / `completion_tokens` / `total_tokens` Integer
- `cost_usd` Numeric(12,6)、`original_cost_usd` Numeric(12,6)?、`cost_delta_usd` Numeric(12,6)?
- `latency_ms` Integer、`status` String(16)、`error_code` String(64)?、`openrouter_generation_id` String(64)?
- `compare_winner` String(16)?、`compare_score` Numeric(4,3)?(信心分數 0–1)、`compare_reason` Text?、`compare_judge_model` String(128)?
- `triggered_at` TIMESTAMPTZ(UTC+8,對齊 `06-timezone.md`)
- **冪等**:`UNIQUE(ai_evaluation_uid, rerun_model)`(不分軟刪)
- **索引**:`(usage_log_uid)`、`(ai_evaluation_uid)` partial(`is_deleted=false`)

### 父表 `ai_model_evaluations` 增重跑游標(§4.2)

- `ai_reran_at TIMESTAMPTZ NULL`:最新一次重跑執行時間;NULL=待重跑(派發掃描鍵)
- `ai_rerun_status SMALLINT NULL`:NULL=未重跑 / 0=失敗 / 1=成功(成敗皆標,終局不重派)

## 實作要點

- model 風格、欄位 comment(中英)對齊既有 `ai_model_eval_candidate.py` / `ai_model_evaluation.py`(每欄 `comment=` 必填,table comment 必填)。
- `backend/app/models/__init__.py` import + `__all__` 加入 `AiModelEvalRerun`(維持英數排序)。
- migration `0026_ai_eval_reruns.py`:`down_revision = "0025"`;`upgrade` 建表 + 兩游標欄 + UNIQUE + 兩索引;`downgrade` 完整對稱還原(drop 索引 / UNIQUE / 表 + 父表兩欄)。對齊 `08-alembic.md` round-trip。
- 金額精度沿用 propose 指定 `Numeric(12,6)`(cost)/`Numeric(4,3)`(score),非預設 `Numeric(18,2)`;`05-precision.md` 允許依語意調整,於 model docstring 註明理由。

## Acceptance

- [ ] `cd backend && uv run alembic upgrade head` 成功且建出 `ai_model_eval_reruns`
- [ ] `cd backend && uv run alembic downgrade -1 && uv run alembic upgrade head` round-trip 全綠(對稱還原)
- [ ] `cd backend && uv run python -c "from app.models import AiModelEvalRerun; from app.models.ai_model_evaluation import AiModelEvaluation; assert hasattr(AiModelEvaluation,'ai_reran_at') and hasattr(AiModelEvaluation,'ai_rerun_status'); print('ok')"` 印 `ok`
- [ ] SQL 驗 `UNIQUE(ai_evaluation_uid, rerun_model)` 存在:`psql ... -c "\d ai_model_eval_reruns"` 顯示該 unique constraint(或 `uv run` 等價檢查)
- [ ] `cd backend && uv run ruff check app/models/ && uv run mypy app/models/` 全綠

## 必讀檔(Just-in-time)

- `docs/Design-Base/04-databases/00-overview.md`
- `docs/Design-Base/04-databases/01-identifiers.md`
- `docs/Design-Base/04-databases/05-precision.md`
- `docs/Design-Base/04-databases/06-timezone.md`
- `docs/Design-Base/04-databases/08-alembic.md`
- `docs/Design-Base/04-databases/09-indexes-and-perf.md`
- `docs/Design-Base/04-databases/90-project-database.md`
- `docs/Design-Base/00-overview/05-timezone.md`
</content>
