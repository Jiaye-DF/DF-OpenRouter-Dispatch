---
id: task-407
title: 重跑結果 Response schema + 讀取 service
status: pending
parallel: true
depends_on: [task-403]
affected_files:
  - backend/app/schemas/ai_model_eval_rerun_result.py
  - backend/app/services/ai_model_eval_rerun_result.py
  - backend/tests/services/test_ai_model_eval_rerun_result.py
estimated_hours: 2.5
---

## 目標

提供查詢 API(task-408)的唯讀對外 schema 與無副作用讀取 service:依 `usage_log_uid` 取該筆所有 challenger 重跑 + 對比(propose §5.4),讀寫分檔對齊 v2.0.3 `ai_model_eval_result.py`。

## 範圍(propose §5.4 / §6)

- `schemas/ai_model_eval_rerun_result.py`(全唯讀 Pydantic,**Decimal → 字串**慣例):
  - `RerunResult`(逐 challenger):模型(`rerun_model` / `model_uid`)、tokens(prompt/completion/total)、`cost_usd`、`original_cost_usd`、`cost_delta_usd`、`latency_ms`、`status`、`error_code`、`compare_winner`、**`compare_score`(信心分數,`str | None`)**、`compare_reason`、`compare_judge_model`、`triggered_at`。所有金額 / 分數欄宣告 `str | None`。
  - `RerunListResponse`:頂層 wrapper `{ reruns: list[RerunResult] }`(無資料 → `reruns: []`,對齊 propose 對外承諾「無則 `200 + data.reruns=[]`」)。
- `services/ai_model_eval_rerun_result.py`:`build_rerun_results(usage_log_uid, *, db)` → 用 task-403 `list_by_usage_log_uid` 取列、Decimal→str 轉換、組 `RerunResult[]`;**純讀**(不寫 audit、不開 transaction、不 commit)。

## 實作要點

- Decimal→str 轉換責任在 service(schema 只宣告型別),對齊 v2.0.3 `ai_model_eval_result.py` 註解。
- 無評審 / 無重跑列 → 回空 list(非 None / 非 404);與 task-408 的 `200 + reruns:[]` 對齊。

## Acceptance

- [ ] `cd backend && uv run pytest tests/services/test_ai_model_eval_rerun_result.py` 全綠
- [ ] 測試涵蓋:(a) 有重跑列 → `build_rerun_results` 回對應筆數,`cost_delta_usd` / `compare_score` 為字串(或 None);(b) 無列 → 回 `[]`;(c) `compare_*` 為 NULL 的列(子開關關)→ 對應欄 None 不爆
- [ ] `cd backend && uv run python -c "from app.schemas.ai_model_eval_rerun_result import RerunResult, RerunListResponse; from app.services.ai_model_eval_rerun_result import build_rerun_results; print('ok')"` 印 `ok`
- [ ] `cd backend && uv run ruff check app/schemas/ai_model_eval_rerun_result.py app/services/ai_model_eval_rerun_result.py && uv run mypy app/schemas/ai_model_eval_rerun_result.py app/services/ai_model_eval_rerun_result.py` 全綠

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/01-routing.md`
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/04-databases/05-precision.md`
</content>
