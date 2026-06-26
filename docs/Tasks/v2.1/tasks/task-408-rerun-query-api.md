---
id: task-408
title: 查詢 API endpoint + router 註冊
status: pending
parallel: false
depends_on: [task-407]
affected_files:
  - backend/app/api/v1/ai_eval_reruns.py
  - backend/app/api/v1/__init__.py
  - backend/tests/api/test_ai_eval_reruns.py
estimated_hours: 2
---

## 目標

開唯讀查詢 API:依 `usage_log_uid` 取該筆所有 challenger 重跑 + 對比,admin 限定;落新檔對齊 v2.0.3 `ai_eval_results.py`(propose §5.4、對外承諾)。

## 範圍(propose 對外承諾 / §5.4)

- 新檔 `api/v1/ai_eval_reruns.py`:`router = APIRouter(prefix="/ai-eval", tags=["ai-eval"])`。
  - `GET /reruns/by-usage-log/{usage_log_uid}`(`AdminDep`):呼叫 task-407 `build_rerun_results` → `RerunListResponse` → `success_response`(ApiResponse 外殼)。
  - 無資料 → `200 + data.reruns=[]`(非 404,對齊 propose 對外承諾)。
- `api/v1/__init__.py`:`from app.api.v1 import (... ai_eval_reruns ...)` + `api_v1_router.include_router(ai_eval_reruns.router)`(置於 `ai_eval_results` 後)。
- **純讀**:不寫 audit、不開 transaction(對齊 `ai_eval_results.py` 職責邊界)。

## 實作要點

- 權限以 `AdminDep` 保護(非 admin → 403、未認證 → 401,由既有 deps 自然產生)。
- OpenAPI summary 中文,確保 `/api/docs` 可查(對齊 `00-overview/04-api-docs.md`)。
- 測試對齊 `tests/api/test_ai_eval_results.py`:admin 取得、非 admin 403、無資料 200+空陣列。

## Acceptance

- [ ] `cd backend && uv run pytest tests/api/test_ai_eval_reruns.py` 全綠
- [ ] 測試涵蓋:(a) admin `GET /api/v1/ai-eval/reruns/by-usage-log/{uid}` → 200 + `data.reruns` 為陣列;(b) 非 admin → 403;(c) 無重跑 → `200 + data.reruns == []`
- [ ] `cd backend && uv run python -c "from app.main import app; assert any('/ai-eval/reruns/by-usage-log' in r.path for r in app.routes); print('ok')"` 印 `ok`(端點已註冊、`/api/docs` 可查)
- [ ] `cd backend && uv run ruff check app/api/v1/ai_eval_reruns.py app/api/v1/__init__.py && uv run mypy app/api/v1/ai_eval_reruns.py` 全綠

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/01-routing.md`
- `docs/Design-Base/03-backend/02-auth.md`
- `docs/Design-Base/03-backend/90-project-backend.md`
- `docs/Design-Base/03-backend/92-project-permission.md`
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/00-overview/04-api-docs.md`
</content>
