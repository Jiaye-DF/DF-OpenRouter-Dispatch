---
id: task-002
title: 判別模型設定 CRUD API（GET / PUT judge-settings）
status: done
parallel: false
depends_on: [task-001]
affected_files:
  - backend/app/repositories/ai_eval_judge_setting.py
  - backend/app/schemas/ai_eval.py
  - backend/app/api/v1/ai_eval.py
  - backend/app/api/v1/__init__.py
estimated_hours: 3
---

## 目標

依 propose §5 提供判別模型設定的讀取與整批設定 API:`GET` 回目前 3 個判別模型、`PUT` 整批設定 3 個(從 `models` 既有 active 模型挑)。

## 範圍

- `GET /api/v1/ai-eval/judge-settings`(admin):回目前判別模型(含 `model_uid` + 模型顯示資訊 + `ai_judge_slot`)。
- `PUT /api/v1/ai-eval/judge-settings`(admin):body 為 `model_uid` 陣列;整批覆寫 3 個槽位。
- **驗證**:陣列長度恰 3、每個 `model_uid` 須存在於 `models` 且 `is_active` / 未軟刪除、不可重複;違反回 `422`。
- Repository 走軟刪除命名慣例(`04-databases/02-soft-delete.md`)。

## Acceptance

- [ ] `GET /api/v1/ai-eval/judge-settings` 回 ApiResponse 外殼 `{success, code, data, detail}`（`03-backend/90-project-backend.md § 1`）
- [ ] `PUT` 傳 3 個合法 active `model_uid` → 200;隨後 `GET` 回相同 3 個（pytest）
- [ ] `PUT` 傳「非 3 個 / 重複 / 不存在 / 已停用或軟刪除」`model_uid` → `422`（pytest 各一 case）
- [ ] 端點 admin-only：無管理 Cookie / 非 admin → `401` / `403`（對齊 `03-backend/02-auth.md`、`92-project-permission.md`）
- [ ] `PUT` 寫稽核 log（管理端異動,對齊 `92-project-permission.md § 9`）
- [ ] Response Schema 以 Pydantic 明確定義,對外用 `model_uid`（UUID),**禁** dict / 內部 pid
- [ ] Swagger `/api/docs` 可見 `ai-eval` 群組兩端點
- [ ] `uv run pytest tests/api/test_ai_eval.py` 全綠;`uv run ruff check` 無 warning;`uv run mypy app` green

## 必讀檔(Just-in-time)

- `AGENTS.md`
- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/00-overview/04-api-docs.md`
- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/01-routing.md`
- `docs/Design-Base/03-backend/02-auth.md`
- `docs/Design-Base/03-backend/90-project-backend.md`
- `docs/Design-Base/03-backend/92-project-permission.md`
- `docs/Design-Base/04-databases/00-overview.md`
- `docs/Design-Base/04-databases/02-soft-delete.md`
