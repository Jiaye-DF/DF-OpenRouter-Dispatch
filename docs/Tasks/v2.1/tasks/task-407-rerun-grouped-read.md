---
id: task-407
title: 重跑結果「依用量紀錄分組」讀取 schema + service(+ 分組分頁 repo 查詢)
status: done
parallel: true
depends_on: []
affected_files:
  - backend/app/schemas/ai_model_eval_rerun_result.py
  - backend/app/services/ai_model_eval_rerun_result.py
  - backend/app/repositories/ai_model_eval_rerun.py
  - backend/tests/services/test_ai_model_eval_rerun_result.py
  - backend/tests/repositories/test_ai_model_eval_rerun.py
estimated_hours: 3
---

## 目標

把唯讀展示層從「扁平、一列一推薦模型、且**不含輸出原文**」重構為 **依用量紀錄(usage_log)分組** 的結構,並把原模型 + 各推薦模型的**真實輸出原文**對外吐出,供 AI 判決總覽頁並排比較(propose §5.4 / §6.1)。DB **不動**(輸出原文已存於 `response_summary.output_text`)。

## 範圍與要點

- **新 schema(取代舊扁平 schema)**,`app/schemas/ai_model_eval_rerun_result.py`:
  - `RerunRecommendation`(逐推薦模型):`rerun_model`、`model_uid`、**`output_text: str | None`**(取自 `ai_model_eval_reruns.response_summary.output_text`)、`prompt/completion/total_tokens`、`cost_usd`、`cost_delta_usd`、`latency_ms`、`status`、`error_code`、`compare_winner`、`compare_score`、`compare_reason`、`compare_judge_model`、`triggered_at`。
  - `RerunGroup`(一筆用量紀錄):`usage_log_uid`、`original_model`、**`original_output_text: str | None`**(取自 `usage_logs.response_summary.output_text`)、`original_cost_usd`、`evaluated_at?`、`recommendations: list[RerunRecommendation]`。
  - `RerunStats`:`total_recommendations`、`keep_count`、`swap_count`、`tie_count`、`unjudged_count`、`failed_count`。
  - `RerunOverviewPage`:`items: list[RerunGroup]`、`total`(分組後的總組數)、`page`、`size`、`stats: RerunStats`。
  - **移除** `RerunResult` / `RerunListResponse` / `RerunOverviewItem`(舊扁平、無輸出原文)。
- **金額 / 信心一律 Decimal → str**(`cost_usd` / `original_cost_usd` / `cost_delta_usd` / `compare_score`),沿用既有 `_COST_QUANT` / `_SCORE_QUANT` 量化慣例。
- **repo 新增分組分頁查詢**,`app/repositories/ai_model_eval_rerun.py`:取「最新 `triggered_at` 優先」的 distinct `usage_log_uid` 分頁(每頁 size 組),再撈這些 usage_log 底下全部(未軟刪)重跑列;`total` = distinct usage_log 組數。
- **service 重寫** `build_rerun_overview`:呼叫 repo 取分組原料 → 反查 `usage_logs.response_summary.output_text` 補 `original_output_text`(用既有 usage_log repository,純讀)→ 組 `RerunGroup[]` → 同時彙總 `RerunStats`。維持**純讀、無副作用**(不打 OpenRouter、不寫 DB、不開 tx)。
- `stats` 計數定義:`keep_count`=`compare_winner='original'`、`swap_count`='challenger'、`tie_count`='tie'、`unjudged_count`=success 但 `compare_winner IS NULL`、`failed_count`=`status!='success'`。

## Acceptance

- [ ] `uv run pytest backend/tests/services/test_ai_model_eval_rerun_result.py backend/tests/repositories/test_ai_model_eval_rerun.py` 全綠
- [ ] `grep -E "class (RerunGroup|RerunRecommendation|RerunStats|RerunOverviewPage)" backend/app/schemas/ai_model_eval_rerun_result.py` 四者皆命中
- [ ] `grep -E "class (RerunResult|RerunListResponse|RerunOverviewItem)" backend/app/schemas/ai_model_eval_rerun_result.py` **零命中**(舊扁平 schema 已移除)
- [ ] `grep -n "original_output_text" backend/app/schemas/ai_model_eval_rerun_result.py` 與 `grep -n "output_text" backend/app/schemas/ai_model_eval_rerun_result.py` 皆命中(原模型 + 推薦模型輸出原文都有對外欄)
- [ ] test 驗證:同一 `usage_log_uid` 的多個推薦模型被併入**同一個 `RerunGroup`**;`stats` 各計數正確;`compare_score`/`cost_*` 皆為字串型別
- [ ] `uv run mypy app/` 與 `uv run ruff check .`(於 backend/)零錯誤零 warning

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/01-routing.md`
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/04-databases/02-soft-delete.md`
- `docs/Design-Base/04-databases/05-precision.md`
- `docs/Design-Base/03-backend/90-project-backend.md`
- `docs/Design-Base/01-propose/90-project-task-spec.md`
