---
id: task-408
title: 查詢 API 收斂為單一分組總覽端點 + 移除 by-usage-log 端點
status: done
parallel: false
depends_on: [task-407]
affected_files:
  - backend/app/api/v1/ai_eval_reruns.py
  - backend/tests/api/test_ai_eval_reruns.py
estimated_hours: 2
---

## 目標

把唯讀查詢收斂為**單一**分組總覽端點 `GET /api/v1/ai-eval/reruns`,回傳 task-407 的 `RerunOverviewPage`(依用量紀錄分組 + 輸出原文 + stats);**移除** `GET /api/v1/ai-eval/reruns/by-usage-log/{usage_log_uid}` 端點(usage-log 明細頁不再內嵌重跑,無消費者)。對齊 propose 對外承諾 / §5.4。

## 範圍與要點

- `app/api/v1/ai_eval_reruns.py`:
  - `list_reruns_overview` 改回傳 `RerunOverviewPage`(含 `stats`);`success_response` 外殼不變。
  - **刪除** `by-usage-log/{usage_log_uid}` route 與其 import(`RerunListResponse`、`build_rerun_results`)。
  - 維持 `AdminDep`(非 admin → 403、未認證 → 401)、`/api/docs` 可查。
  - docstring 移除 challenger / GAN 黑話,改白話(原模型 / AI 推薦模型 / 對比裁決)。
- `app/api/v1/__init__.py`:router 仍為單一 router,**預期不需改動**(grep 確認註冊無殘留即可,不在 affected_files)。
- 測試 `tests/api/test_ai_eval_reruns.py` 重寫:
  - admin 取 `/reruns` → 200,`data.items` 為分組結構、含 `original_output_text` 與每組 `recommendations[].output_text`、含 `data.stats`。
  - 無資料 → `200 + items=[]`。
  - 非 admin → 403。
  - by-usage-log 端點 → 404(route 已移除)。

## Acceptance

- [ ] `uv run pytest backend/tests/api/test_ai_eval_reruns.py` 全綠
- [ ] `grep -n "by-usage-log" backend/app/api/v1/ai_eval_reruns.py` **零命中**
- [ ] `grep -nE "RerunListResponse|build_rerun_results" backend/app/api/v1/ai_eval_reruns.py` **零命中**(舊 by-usage-log 依賴已清)
- [ ] pytest 對 OpenAPI 斷言:`/api/v1/ai-eval/reruns` GET 存在;`/api/v1/ai-eval/reruns/by-usage-log/{usage_log_uid}` 不存在
- [ ] `uv run mypy app/` 與 `uv run ruff check .`(於 backend/)零錯誤零 warning

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/01-routing.md`
- `docs/Design-Base/03-backend/02-auth.md`
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/00-overview/04-api-docs.md`
- `docs/Design-Base/03-backend/90-project-backend.md`
