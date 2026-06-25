---
id: task-104
title: 評審結果 repository(父表 + 三子表寫入 + 標旗標)
status: pending
parallel: true
depends_on: []
affected_files:
  - backend/app/repositories/ai_model_evaluation.py
estimated_hours: 3
---

## 目標

交付評審結果的資料層:寫 `ai_model_evaluations`(父)+ `ai_model_eval_candidates`(子 ×3)+ 將 `usage_logs.ai_evaluated_at` 標記為已評審,全程冪等。模型已於 v2.0.0(task-001)建立,本 task 只寫 Repository。

## 範圍

- `backend/app/repositories/ai_model_evaluation.py`(新檔):
  - `create_evaluation_with_candidates(...)`:單一 transaction 寫父表 dim1/2 + 三筆子表 dim3/4(對齊 `03-backend/03-async-and-tx.md` 多表 tx)。
  - **冪等**:以 `usage_log_uid`(父表 UNIQUE)防重複;已存在 → 不重寫(回傳既有或 no-op),對齊 propose §4 冪等。
  - `mark_usage_log_evaluated(usage_log_uid)`:設 `ai_evaluated_at = now()`(UTC+8)。
  - `fetch_unevaluated_log_uids(limit)`:撈 `ai_evaluated_at IS NULL` 待派發筆(供 task-106 dispatcher 用)。
  - 遵守軟刪除命名慣例(`04-databases/02-soft-delete.md`)。

> **待 user 確認(propose §8.2)**:父表 summary/intent 三評審不一致時取誰、是否存 raw JSON 供稽核 — 介面預留 `raw_json` 可選參數,預設不存;user 拍板後切換。

## Acceptance

- [ ] `cd backend && uv run pytest tests/repositories/test_ai_model_evaluation.py` 全綠(本 task 一併新增,使用真 DB 整合測試,對齊 `03-backend/07-testing.md`)
- [ ] 測試涵蓋:同一 `usage_log_uid` 重複呼叫 `create_evaluation_with_candidates` **不**產生重複父/子列(冪等斷言)
- [ ] 測試涵蓋:`mark_usage_log_evaluated` 後該 log `ai_evaluated_at IS NOT NULL`,且 `fetch_unevaluated_log_uids` 不再回傳該 uid
- [ ] 寫父 + 3 子於單一 transaction;中途 raise 時無半寫(測試斷言 rollback)
- [ ] `cd backend && uv run ruff check app/repositories/ai_model_evaluation.py` 無 warning;`uv run mypy app/repositories/ai_model_evaluation.py` green

## 必讀檔(Just-in-time)

- `AGENTS.md`
- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/03-async-and-tx.md`
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/04-databases/00-overview.md`
- `docs/Design-Base/04-databases/02-soft-delete.md`
- `docs/Design-Base/04-databases/06-timezone.md`
- `docs/Design-Base/04-databases/90-project-database.md`
