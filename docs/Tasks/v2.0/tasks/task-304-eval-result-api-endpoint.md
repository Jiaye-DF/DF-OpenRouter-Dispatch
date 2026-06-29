---
id: task-304
title: 評審結果 API endpoint + router 註冊
status: pending
parallel: false
depends_on: [task-303]
affected_files:
  - backend/app/api/v1/ai_eval_results.py
  - backend/app/api/v1/__init__.py
  - backend/tests/api/test_ai_eval_results.py
estimated_hours: 2.5
---

## 目標

對外暴露唯讀評審結果端點,admin 限定,供前端明細頁取用(propose §4.1)。

## 範圍

- `backend/app/api/v1/ai_eval_results.py`(新檔):
  - `router = APIRouter(prefix="/ai-eval/evaluations", tags=[...])`。
  - `GET /by-usage-log/{usage_log_uid}`,依賴 `AdminDep`(對齊 usage-logs 明細,見 `usage_logs.py`)+ `DbDep`。
  - 呼叫 task-303 `build_evaluation_result`,以 `ApiResponse` 外殼回傳;**無評審 → `200` + `data.evaluation == null`**(非 404)。
  - 路徑前綴與既有 `ai_eval.py`(judge-settings,prefix `/ai-eval`)不衝突:本端點完整路徑 `/api/v1/ai-eval/evaluations/by-usage-log/{usage_log_uid}`。
- `backend/app/api/v1/__init__.py`(既有聚合器,第 23 行 `api_v1_router`):新增 `from . import ai_eval_results` + `api_v1_router.include_router(ai_eval_results.router)`(置於 `ai_eval.router` 之後)。

## Acceptance

- [ ] `cd backend && uv run pytest tests/api/test_ai_eval_results.py` 全綠(本 task 新增,真 DB + admin 認證,參考既有 `tests/api/test_ai_eval.py`)
- [ ] 測試:admin 取「已評審」log → `200`,`data.evaluation.summary` / `data.evaluation.candidates` 結構齊全
- [ ] 測試:admin 取「無評審」log → `200` 且 `data.evaluation == null`
- [ ] 測試:非 admin(一般 user)→ `403`
- [ ] route 已註冊:`cd backend && uv run python -c "from app.api.v1 import api_v1_router; assert any('/ai-eval/evaluations/by-usage-log' in getattr(r,'path','') for r in api_v1_router.routes); print('ok')"` 印出 `ok`
- [ ] response 殼為 `ApiResponse`(`03-backend/01-routing.md`)
- [ ] `cd backend && uv run ruff check app/api/v1/ai_eval_results.py app/api/v1/__init__.py` 無 warning;`uv run mypy app/api/v1/ai_eval_results.py` green

## 必讀檔(Just-in-time)

- `AGENTS.md`
- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/01-routing.md`
- `docs/Design-Base/03-backend/02-auth.md`
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/03-backend/90-project-backend.md`
- `docs/Design-Base/03-backend/92-project-permission.md`
