---
id: task-403
title: rerun repository + 父表重跑游標查詢
status: done
parallel: true
depends_on: [task-402]
affected_files:
  - backend/app/repositories/ai_model_eval_rerun.py
  - backend/app/repositories/ai_model_evaluation.py
  - backend/tests/repositories/test_ai_model_eval_rerun.py
estimated_hours: 3
---

## 目標

提供 challenger 重跑列的寫入(原子、冪等)與讀取(供查詢 API),並在父表 repository 加重跑游標的派發掃描 / 終局標記方法(propose §4 / §5.1)。

## 範圍

### 新檔 `repositories/ai_model_eval_rerun.py`(`AiModelEvalRerunRepository`)

- `create_rerun(...)`:寫一筆 `ai_model_eval_reruns`(原子);**冪等以 `UNIQUE(ai_evaluation_uid, rerun_model)`**——已存在則回既有列、不重寫(對齊 `ai_model_evaluation.py` 冪等慣例)。以 dataclass 輸入(對齊 `CandidateInput` 風格)。
- `list_by_usage_log_uid(usage_log_uid)`:取該 log 對應評審的所有 challenger 重跑(過濾軟刪,`is_deleted=false`),供 task-407 讀取 service。
- `list_by_evaluation_uid(ai_evaluation_uid)`:同上以父評審 UID 取。

### 既有檔 `repositories/ai_model_evaluation.py` 增方法

- `fetch_unreran_evaluation_uids(limit)`:撈父表 `ai_reran_at IS NULL 且 status='evaluated' 且 is_deleted=false` 前 N 筆(**FIFO `created_at ASC`**,對齊既有 `fetch_unevaluated_log_uids` 的反餓死設計)。
- `mark_reran(ai_evaluation_uid, *, status)`:標 `ai_reran_at=now()`(UTC+8)+ `ai_rerun_status`(1 成功 / 0 失敗);成敗皆標(終局,不重派)。

## 實作要點

- 軟刪命名 / 過濾對齊 `04-databases/02-soft-delete.md`;raw 比較禁字串拼接(`04-sql-safety.md`)。
- 多表 / 原子寫入沿用既有 `begin_nested()` / `begin()` 模式(見 `create_evaluation_with_candidates`)。
- 測試走真 DB 整合(對齊既有 `tests/repositories/test_ai_model_evaluation.py`):驗冪等(重複 `create_rerun` 同 `(eval_uid, rerun_model)` 只一筆)、FIFO 撈序、`mark_reran` 終局值。

## Acceptance

- [ ] `cd backend && uv run pytest tests/repositories/test_ai_model_eval_rerun.py` 全綠
- [ ] 測試涵蓋:(a) `create_rerun` 二次同 `(ai_evaluation_uid, rerun_model)` → DB 僅一列(冪等);(b) `fetch_unreran_evaluation_uids` 回 `ai_reran_at IS NULL` 且 `status='evaluated'`,順序 `created_at ASC`;(c) `mark_reran(status=0/1)` 寫入 `ai_reran_at` 非空 + 對應 `ai_rerun_status`;(d) `list_by_usage_log_uid` 過濾軟刪
- [ ] `cd backend && uv run ruff check app/repositories/ai_model_eval_rerun.py app/repositories/ai_model_evaluation.py && uv run mypy app/repositories/` 全綠

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/03-async-and-tx.md`
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/04-databases/00-overview.md`
- `docs/Design-Base/04-databases/02-soft-delete.md`
- `docs/Design-Base/04-databases/04-sql-safety.md`
- `docs/Design-Base/04-databases/90-project-database.md`
</content>
