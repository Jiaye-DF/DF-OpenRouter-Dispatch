---
id: task-303
title: 彙總 service(三評審 → 單一判決)
status: pending
parallel: false
depends_on: [task-301, task-302]
affected_files:
  - backend/app/services/ai_model_eval_result.py
  - backend/tests/services/test_ai_model_eval_result.py
estimated_hours: 3
---

## 目標

組裝唯讀評審結果:依 `usage_log_uid` 取父列 + 候選(含裁判)→ 計算彙總 → 回 task-301 schema。彙總在後端算(單一真相源、可單元測試),前端只渲染(propose §5)。

## 範圍

`backend/app/services/ai_model_eval_result.py`(新檔):

- `build_evaluation_result(usage_log_uid: UUID, *, db) -> EvaluationResultEnvelope`:
  1. `find_by_usage_log_uid`(既有 repo)取父列;**無父列 → 回 `{"evaluation": None}`**(propose §3 未評審狀態,非例外)。
  2. `list_candidates_with_judge`(task-302)取候選 + 裁判 key/name。
  3. 算彙總(下表),組 `EvaluationResultRead`。
- 純讀、無副作用、**不打 OpenRouter**、不寫 DB。

### 彙總規則(propose §5,逐條實作 + 測試)

| 欄 | 規則 |
| --- | --- |
| `avg_fit_score` | 非 null `ai_fit_score` 平均,量化到 3 位小數轉 `str`;全 null → `None` |
| `min/max_fit_score` | 非 null 值極值轉 `str`;全 null → `None` |
| `recommend_consensus.model` / `votes` | 非 null `ai_recommend_model` 取眾數與其票數;全 null → `model=None, votes=0` |
| `recommend_consensus.tier` | 眾數模型對應的 `ai_recommend_tier`;`None` 安全 |
| `recommend_consensus.is_split` | **無嚴格過半即分歧**:設 `succeeded` = 有推薦的候選數、`top` = 眾數票數 → `is_split = (top * 2 <= succeeded) and succeeded > 1`(即 1:1:1→true、1:1→true、2:1→false、單一→false) |
| `self_vote_count` | `ai_self_vote == True` 的候選數(null 不計;對齊 0024/0025 更正後語意) |
| `judge_count` / `succeeded_count` | 候選總數 / 其中 AI 欄位非 null(評審成功)數 |

- `task_analysis` 直接取父表 `ai_task_summary` / `ai_task_intent` / `ai_task_complexity`(已是單值)。
- 錯誤轉 `AppError` + 結構化 log(`03-backend/05`)。

## Acceptance

- [ ] `cd backend && uv run pytest tests/services/test_ai_model_eval_result.py` 全綠(本 task 新增,真 DB 整合)
- [ ] 測試:3 評審成功、推薦 2:1 → `avg/min/max_fit_score` 正確(字串、3 位)、`recommend_consensus.votes==2`、`is_split==False`、`succeeded_count==3`
- [ ] 測試:推薦 1:1:1(三家不同)→ `is_split==True`、`votes==1`
- [ ] 測試:部分成功(2 成功 1 失敗)→ `judge_count==3`、`succeeded_count==2`;失敗候選不污染平均
- [ ] 測試:`ai_self_vote` 有 1 筆 True → `self_vote_count==1`(null 不計)
- [ ] 測試:無父列 → 回 `evaluation is None`(不丟例外)
- [ ] `cd backend && uv run ruff check app/services/ai_model_eval_result.py` 無 warning;`uv run mypy app/services/ai_model_eval_result.py` green

## 必讀檔(Just-in-time)

- `AGENTS.md`
- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/03-async-and-tx.md`
- `docs/Design-Base/03-backend/05-exceptions-and-logging.md`
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/04-databases/05-precision.md`
- `docs/Design-Base/03-backend/90-project-backend.md`
