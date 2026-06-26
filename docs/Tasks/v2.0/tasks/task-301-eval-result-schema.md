---
id: task-301
title: 評審結果 Response schema(對外結構)
status: pending
parallel: true
depends_on: []
affected_files:
  - backend/app/schemas/ai_model_eval_result.py
estimated_hours: 1.5
---

## 目標

新增評審結果對外 response schema(propose §4.2),供 service(303)組裝、API(304)回傳、前端(305)鏡像。純資料結構,無業務邏輯。

## 範圍

`backend/app/schemas/ai_model_eval_result.py`(新檔),定義 pydantic 模型:

- `TaskAnalysisRead`:`summary: str | None`、`intent: str | None`、`complexity: str | None`(原始枚舉值,不做中文化)。
- `RecommendConsensus`:`model: str | None`、`tier: str | None`、`votes: int`、`is_split: bool`。
- `EvaluationSummary`:`judge_count: int`、`succeeded_count: int`、`avg_fit_score: str | None`、`min_fit_score: str | None`、`max_fit_score: str | None`、`recommend_consensus: RecommendConsensus`、`self_vote_count: int`。
- `EvalCandidateRead`:`ai_candidate_uid`、`judge_model_uid`、`judge_model_key: str | None`、`judge_model_name: str | None`、`ai_recommend_model: str | None`、`ai_recommend_tier: str | None`、`ai_recommend_reason: str | None`、`ai_fit_score: str | None`、`ai_self_vote: bool | None`。
- `EvaluationResultRead`:`ai_evaluation_uid`、`usage_log_uid`、`ai_original_model: str`、`status: str`、`ai_evaluated_at: datetime | None`、`task_analysis: TaskAnalysisRead`、`summary: EvaluationSummary`、`candidates: list[EvalCandidateRead]`。
- 外層回應 data 由 304 以 `{"evaluation": EvaluationResultRead | None}` 包裝(本 task 僅定義內層 schema;可額外定義 `EvaluationResultEnvelope` 帶 `evaluation: EvaluationResultRead | None`)。

**Decimal 以字串傳輸**:所有 `*_fit_score` 欄位型別為 `str | None`(對齊 `04-databases/05-precision.md` + 前端 Decimal-as-string 慣例),由 303 service 將 `Decimal` 量化後轉 `str`。

## Acceptance

- [ ] `[ -f backend/app/schemas/ai_model_eval_result.py ]`
- [ ] 可匯入:`cd backend && uv run python -c "from app.schemas.ai_model_eval_result import EvaluationResultRead, EvaluationResultEnvelope, EvaluationSummary, RecommendConsensus, EvalCandidateRead, TaskAnalysisRead; print('ok')"` 印出 `ok`
- [ ] fit_score 欄位皆宣告為 `str | None`(非 `Decimal`):`cd backend && uv run python -c "from app.schemas.ai_model_eval_result import EvaluationSummary, EvalCandidateRead; import typing; assert EvaluationSummary.model_fields['avg_fit_score'].annotation == (str | None); assert EvalCandidateRead.model_fields['ai_fit_score'].annotation == (str | None); print('ok')"` 印出 `ok`
- [ ] `cd backend && uv run ruff check app/schemas/ai_model_eval_result.py` 無 warning;`uv run mypy app/schemas/ai_model_eval_result.py` green

## 必讀檔(Just-in-time)

- `AGENTS.md`
- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/01-routing.md`
- `docs/Design-Base/04-databases/05-precision.md`
- `docs/Design-Base/03-backend/90-project-backend.md`
