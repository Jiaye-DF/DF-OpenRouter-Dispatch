---
id: task-105
title: 三評審執行 + 回寫 service
status: pending
parallel: false
depends_on: [task-103, task-104]
affected_files:
  - backend/app/services/ai_model_eval.py
estimated_hours: 4
---

## 目標

組裝單筆評審流程:讀 v2.0.0 設定的 3 個判別模型 → 對同一份 I/O 各內部呼叫一次(`DEFAULT_OPENROUTER_KEY`,**不寫 usage_logs**)→ 解析 → 透過 task-104 repository 回寫並標旗標。是 task-106 taskiq task 的純業務核心(無排程依賴,可獨立測)。

## 範圍

- `backend/app/services/ai_model_eval.py`(新檔):`evaluate_usage_log(usage_log_uid)` —
  1. 讀 `ai_eval_judge_settings`(3 模型,既有 repo `ai_eval_judge_setting.py`)+ 該筆 `usage_logs`(`request_content` / `response_summary` / 原模型)+ `models` active 白名單。
  2. 用 task-103 `build_judge_prompt` 組 payload,對 3 模型各 `await openrouter_client.chat_completion(payload, api_key=DEFAULT_OPENROUTER_KEY)`(沿用 v1.9.1 內部呼叫模式:不經 SDK proxy、不寫 usage_logs)。
  3. 以 task-103 schema 解析;**某評審失敗該筆標記、不阻斷其他評審**;三方全失敗 → 父 `status='error'`(propose §5)。
  4. 用 task-104 `create_evaluation_with_candidates` + `mark_usage_log_evaluated` 回寫。
- 錯誤轉 `AppError`、結構化 log + 機密過濾(`03-backend/05`、`06`)。

## Acceptance

- [ ] `cd backend && uv run pytest tests/services/test_ai_model_eval.py` 全綠(本 task 新增,使用 `respx` mock 三次 OpenRouter 呼叫,對齊 `03-backend/07-testing.md`)
- [ ] 測試:3 評審皆成功 → 父 1 列 + 子 3 列、`status` 非 error、`ai_evaluated_at` 已標
- [ ] 測試:1 評審失敗、2 成功 → 仍回寫、父 `status` 非 error、失敗評審該子列標記
- [ ] 測試:3 評審全失敗 → 父 `status='error'`、不誤標完成(依冪等定義驗 `ai_evaluated_at` 行為)
- [ ] 測試斷言三次 `chat_completion` 皆帶 `api_key=DEFAULT_OPENROUTER_KEY` 且**未**寫入 `usage_logs`
- [ ] `cd backend && uv run ruff check app/services/ai_model_eval.py` 無 warning;`uv run mypy app/services/ai_model_eval.py` green

## 必讀檔(Just-in-time)

- `AGENTS.md`
- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/03-async-and-tx.md`
- `docs/Design-Base/03-backend/05-exceptions-and-logging.md`
- `docs/Design-Base/03-backend/06-clients.md`
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/90-third-party-service/00-overview.md`
- `docs/Design-Base/90-third-party-service/01-client-design.md`
- `docs/Design-Base/90-third-party-service/50-openrouter.md`
