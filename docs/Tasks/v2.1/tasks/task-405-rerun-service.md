---
id: task-405
title: rerun service(challenger 串行 → discriminator → 寫一筆)
status: pending
parallel: true
depends_on: [task-401, task-403, task-404]
affected_files:
  - backend/app/services/ai_model_eval_rerun.py
  - backend/tests/services/test_ai_model_eval_rerun.py
estimated_hours: 4
---

## 目標

實作單筆評審的重跑核心業務(純業務、可獨立測,對齊 `evaluate_usage_log` 風格):對「三裁判推薦去重後、且 ≠ 原模型」的每個 challenger **串行**真實重跑 → 客觀指標 → AI discriminator 盲化裁決 → 寫一筆 `ai_model_eval_reruns`(propose §5.2 / §5.3)。

## 範圍(propose §5.2 / §5.3,決議 #1/#2/#4/#5/#7)

- 入口 `rerun_evaluation(ai_evaluation_uid, *, db, client)`:
  1. 取父評審 + 候選(用 task-303 `list_candidates_with_judge`)→ 算待重跑集合 = `{裁判推薦模型} − {原模型}`(**去重**,決議 #4;`ai_candidate_uid` 取代表者)。
  2. **跳過條件**(決議:標終局不重跑):無任何「推薦 ≠ 原模型」→ `mark_reran(status=1)`、challenger 0 筆。
  3. 對每個 challenger **串行**(非併發,propose §5.2 定案):
     - 組原輸入快照 payload → `chat_completion`(非串流,`DEFAULT_OPENROUTER_KEY`,**不**寫 `usage_logs`)→ 解析輸出 / usage → 算 `cost_usd`(沿用 proxy 計費:取回應 `usage.cost`/`total_cost`)→ `cost_delta = challenger − original`(無原成本 → NULL)。
     - **discriminator**(`AI_RERUN_DISCRIMINATOR_ENABLED=true` 才跑,決議 #2 推薦者自我裁決):用 **推薦該 challenger 的評審模型本人** 當裁判,`build_discriminator_prompt`(task-404)盲化比「原輸出 vs challenger 輸出」→ `winner`(映射回 original/challenger/tie)+ `score`(信心)+ `reason`;`compare_judge_model` = 該裁判 key。子開關 false → `compare_*` 留 NULL,仍寫客觀指標列。
     - `create_rerun(...)` 寫一筆(原子)。
  4. **單一 challenger 失敗不阻斷其他**;全 challenger 失敗 → `mark_reran(status=0)`;≥1 成功 → `mark_reran(status=1)`。
- 錯誤對外收斂 `AppError`,細節進結構化 log(**不洩金鑰**,對齊 `05-exceptions-and-logging.md`)。

## 實作要點

- A/B 盲化的隨機映射在本 service 決定後事後還原(prompt 端不知模型名);測試需可注入固定映射或斷言映射還原正確。
- challenger 呼叫 timeout / 內部呼叫模式沿用 `evaluate_usage_log`(自建 client 由 caller / task-406 提供)。
- 測試走 respx 攔截 challenger + discriminator 兩類呼叫;驗去重、串行、子開關、部分失敗、成本 delta。

## Acceptance

- [ ] `cd backend && uv run pytest tests/services/test_ai_model_eval_rerun.py` 全綠
- [ ] 測試涵蓋:(a) 三裁判推薦同模型 → 只 `create_rerun` 一筆(去重,決議 #4);(b) 推薦含原模型 → 該 challenger 跳過;全員維持原模型 → 0 筆 + `mark_reran(status=1)`;(c) `AI_RERUN_DISCRIMINATOR_ENABLED=false` → 寫列但 `compare_*` 全 NULL、**無** discriminator 呼叫;`=true` → `compare_winner`/`compare_score`/`compare_reason`/`compare_judge_model` 有值;(d) 單一 challenger 呼叫失敗 → 其餘照寫、不拋;全失敗 → `mark_reran(status=0)`;(e) `cost_delta = challenger − original`,無原成本 → NULL;(f) discriminator payload 盲化(不含模型名,沿用 404 斷言)
- [ ] `cd backend && uv run ruff check app/services/ai_model_eval_rerun.py && uv run mypy app/services/ai_model_eval_rerun.py` 全綠

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/03-async-and-tx.md`
- `docs/Design-Base/03-backend/05-exceptions-and-logging.md`
- `docs/Design-Base/03-backend/06-clients.md`
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/90-third-party-service/00-overview.md`
- `docs/Design-Base/90-third-party-service/01-client-design.md`
- `docs/Design-Base/90-third-party-service/02-rate-and-cost.md`
- `docs/Design-Base/90-third-party-service/50-openrouter.md`
- `docs/Design-Base/04-databases/05-precision.md`
- `docs/Design-Base/00-overview/05-timezone.md`
</content>
