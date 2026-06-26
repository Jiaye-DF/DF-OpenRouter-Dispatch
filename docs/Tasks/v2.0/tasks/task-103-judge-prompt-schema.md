---
id: task-103
title: 判別 prompt builder + 結構化輸出 schema(dim1–4)
status: pending
parallel: true
depends_on: []
affected_files:
  - backend/app/services/ai_model_eval_prompt.py
  - backend/app/schemas/ai_model_eval.py
estimated_hours: 3
---

## 目標

交付「判別 prompt 組裝」與「判別輸出解析 schema」兩個純函式/模型單元(無 I/O、無 DB),供 task-105 evaluation service 呼叫;對齊 propose §5(四方向)+ §6(輸出格式草案)。

## 範圍

- `backend/app/schemas/ai_model_eval.py`(新檔,**勿**動既有 `ai_eval.py`):Pydantic 模型對應 §6 JSON —
  `task_summary`(dim1)、`task_intent` + `task_complexity`(dim2,`low|medium|high`)、`output_fit{score:0–1, reason}`(dim3)、`recommend{model, reason}`(dim4)。含寬鬆解析(容忍模型多回欄位)。
- `backend/app/services/ai_model_eval_prompt.py`(新檔):`build_judge_prompt(request_content, response_summary, candidate_models) -> payload dict`。
  - **盲化**:prompt **不**揭露原 output 出自哪個模型(propose §5 約束)。
  - **候選白名單**:dim4 推薦只能從傳入的 `models` active 清單(`model_key` + `tier`)選;prompt 明列白名單。
  - 要求模型回 JSON 結構化輸出(對應上面 schema)。

> **待 user 確認(propose §8)**:(a) `request_content.text` 是否先 PII 遮罩;(b) dim2 意圖標籤是否固定枚舉。本 task 先依 §6 草案實作,枚舉以可選常數集合預留;user 拍板後微調不破壞介面。

## Acceptance

- [ ] `cd backend && uv run python -c "from app.schemas.ai_model_eval import JudgeOutput; JudgeOutput.model_validate({'task_summary':'x','task_intent':'code_generation','task_complexity':'medium','output_fit':{'score':0.8,'reason':'r'},'recommend':{'model':'anthropic/claude-opus-4.8','reason':'r'}})"` 通過驗證
- [ ] `score` 超出 0–1 時 schema 驗證 raise(`uv run python -c` 斷言 ValidationError)
- [ ] `build_judge_prompt(...)` 回傳的 prompt 文字含全部傳入候選 `model_key`,且**不**含原模型識別字串(單元測試斷言)
- [ ] `cd backend && uv run pytest tests/services/test_ai_model_eval_prompt.py` 全綠(本 task 一併新增此測試檔)
- [ ] `cd backend && uv run ruff check app/services/ai_model_eval_prompt.py app/schemas/ai_model_eval.py` 無 warning;`uv run mypy` green

## 必讀檔(Just-in-time)

- `AGENTS.md`
- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/01-routing.md`
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/90-third-party-service/00-overview.md`
- `docs/Design-Base/90-third-party-service/50-openrouter.md`
