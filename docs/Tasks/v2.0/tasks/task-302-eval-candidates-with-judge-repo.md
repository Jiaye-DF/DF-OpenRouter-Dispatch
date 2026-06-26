---
id: task-302
title: repository — 取候選並 join 判別模型(key/name)
status: pending
parallel: true
depends_on: []
affected_files:
  - backend/app/repositories/ai_model_evaluation.py
  - backend/tests/repositories/test_ai_model_evaluation.py
estimated_hours: 2
---

## 目標

子表 `ai_model_eval_candidates` 只存 `model_uid`,前端需顯示判別模型 key/name。新增一個一次查回「候選 + 裁判 key/name」的 repository 方法,避免逐筆查 models 造成 N+1(propose §4.3)。

## 範圍

`backend/app/repositories/ai_model_evaluation.py`(既有檔,**僅本版本 task-302 觸碰**):

- 新增 `list_candidates_with_judge(ai_evaluation_uid: UUID) -> list[...]`:在既有 `list_candidates` 基礎上 `outerjoin` `models`(`AiModelEvalCandidate.model_uid == Model.model_uid`),一次 SELECT 取回每筆候選 + 對應裁判 `model_key` / `name`。
  - 過濾軟刪候選(沿用 `list_candidates` 的 `is_deleted == False`)。
  - 用 `outerjoin`(非 inner):裁判模型若被軟刪 / 不存在,候選仍回傳、key/name 為 `None`。
  - 回傳型別自訂(具名 tuple / `Row` / 輕量 dataclass 皆可),須同時帶候選 ORM 欄位與 `model_key` / `name`,供 303 service 直接取用。
- **不**改既有方法簽名與行為。

## Acceptance

- [ ] `cd backend && uv run pytest tests/repositories/test_ai_model_evaluation.py` 全綠(本 task 新增測試,真 DB 整合,對齊 `03-backend/07-testing.md`)
- [ ] 新測試:寫入 1 父 + 3 候選(裁判指向既有 models)→ `list_candidates_with_judge` 回 3 筆且每筆帶正確 `model_key` / `name`
- [ ] 新測試:候選的裁判 model 軟刪 / 不存在 → 該候選仍回傳、`model_key` 與 `name` 為 `None`(驗 outerjoin)
- [ ] 新測試斷言單次查詢(無 per-candidate 額外 query):以 `list_candidates_with_judge` 取回後不再觸發 models 查詢即可組裝(可用回傳物件直接含 key/name 驗證)
- [ ] `cd backend && uv run ruff check app/repositories/ai_model_evaluation.py` 無 warning;`uv run mypy app/repositories/ai_model_evaluation.py` green

## 必讀檔(Just-in-time)

- `AGENTS.md`
- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/04-databases/00-overview.md`
- `docs/Design-Base/04-databases/02-soft-delete.md`
- `docs/Design-Base/04-databases/09-indexes-and-perf.md`
- `docs/Design-Base/03-backend/08-performance.md`
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/04-databases/90-project-database.md`
