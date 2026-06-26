---
id: task-404
title: AI discriminator 盲化對比 prompt + 解析 schema
status: done
parallel: true
depends_on: []
affected_files:
  - backend/app/services/ai_model_eval_rerun_prompt.py
  - backend/app/schemas/ai_model_eval.py
  - backend/tests/services/test_ai_model_eval_rerun_prompt.py
estimated_hours: 2.5
---

## 目標

提供對比裁決(discriminator)的**純函式** prompt builder 與寬鬆解析 schema:輸入「使用者原輸入 + 輸出 A + 輸出 B + 任務」,要求裁判**盲選**何者較適合任務,輸出結構化 `{winner, reason, score}`(propose §5.3、決議 #7 盲化)。

## 範圍(propose §5.3)

- `build_discriminator_prompt(...)`:純函式、無 I/O,對齊既有 `ai_model_eval_prompt.build_judge_prompt` 風格。
  - 輸入:使用者原輸入(沿用 `request_content` 渲染,**保留 mask hook**,決議 #5 不遮罩)、輸出 A、輸出 B、任務脈絡。
  - **盲化**(決議 #7):prompt **不**揭露兩側模型名,只給「輸出 A / 輸出 B」;A/B 與 original/challenger 的對應由 caller(task-405)隨機映射後事後還原。
  - 回傳 OpenAI-compatible payload:`{messages, response_format: json_object, temperature: 0}`(對齊 v2.0 fixed §2 `temperature=0`)。
  - `winner` ∈ A/B;`score` = **信心分數 0–1**(對「原 AI 推薦該換成 challenger 是否合理」的信心,propose §4.1 `compare_score` 語意)。
- `DiscriminatorOutput`(Pydantic,加入既有 `backend/app/schemas/ai_model_eval.py`,與 `JudgeOutput` 同檔):欄位 `winner`(A/B 枚舉)、`reason`(str)、`score`(0–1,寬鬆)。
- 解析助手:容忍 ```` ```json ```` 圍欄與前後夾帶文字(對齊 `ai_model_eval.py:_parse_judge_content` 慣例;若該 parse 邏輯在 service 端,則本 task 在 prompt 模組提供等價 `_parse_discriminator_content`)。

## 實作要點

- **禁**在本 task 發網路請求 / 動 DB(純函式 + schema)。
- A/B 匿名化的**隨機映射本身**屬 service(task-405)職責;本 prompt 只需接受「已決定好的 A 文字 / B 文字」並產 payload,確保盲化(不在 payload 內寫出模型名)。
- 枚舉與範例 JSON 直寫進 prompt(對齊 `build_judge_prompt` 的 `_OUTPUT_SCHEMA_HINT` 作法),讓回傳落在固定集合。

## Acceptance

- [ ] `cd backend && uv run pytest tests/services/test_ai_model_eval_rerun_prompt.py` 全綠
- [ ] 測試涵蓋:(a) payload 含 `temperature == 0` 且 `response_format.type == "json_object"`;(b) payload 文字**不含**任一模型 key(盲化斷言);(c) `DiscriminatorOutput` 能解析含 ```` ```json ```` 圍欄與夾帶文字的回覆;(d) `winner` 非 A/B 時驗證失敗
- [ ] `cd backend && uv run python -c "from app.services.ai_model_eval_rerun_prompt import build_discriminator_prompt; from app.schemas.ai_model_eval import DiscriminatorOutput; print('ok')"` 印 `ok`
- [ ] `cd backend && uv run ruff check app/services/ai_model_eval_rerun_prompt.py app/schemas/ai_model_eval.py && uv run mypy app/services/ai_model_eval_rerun_prompt.py` 全綠

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/90-third-party-service/00-overview.md`
- `docs/Design-Base/90-third-party-service/01-client-design.md`
- `docs/Design-Base/90-third-party-service/50-openrouter.md`
</content>
