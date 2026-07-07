---
id: task-420
title: 後端 stats/by-project-model 端點 + ProjectModelStatItem + repo by_project_model + 抽共用 _resolve_filters
status: done
parallel: true
depends_on: []
affected_files:
  - backend/app/api/v1/stats.py
  - backend/app/api/v1/_scope_filters.py
  - backend/app/schemas/stats.py
  - backend/app/repositories/usage_log.py
  - backend/tests/api/test_stats.py
  - backend/tests/repositories/test_usage_log_stats.py
estimated_hours: 3
---

## 目標

新增唯讀彙總端點 `GET /api/v1/stats/by-project-model`(依「專案 × 模型」雙維度彙總請求數/tokens/成本),供功能一 Excel 專案×模型明細使用;同時把 `stats.py` 的 `_resolve_filters` 抽為共用工具供 task-421 沿用(對齊 propose §B.1 / §B.2)。

## 範圍與要點

- **抽共用**:新建 `backend/app/api/v1/_scope_filters.py`,將 `stats.py` 現有 `_resolve_filters(actor, department_uid, project_uid, user_uid)` 原封移入(行為不變:admin 不鎖、非-admin 強制部門、跨部門顯式傳參 → `AppError("forbidden", 403)`);`stats.py` 改為 `from app.api.v1._scope_filters import resolve_filters` 引用(去掉底線前綴改公開名 `resolve_filters`)。
- **schema**:`backend/app/schemas/stats.py` 新增
  ```python
  class ProjectModelStatItem(BaseModel):
      project_uid: UUID
      project_code: str
      project_name: str
      model: str
      total_requests: int
      total_tokens: int
      total_cost_usd: Decimal
  ```
- **repository**:`backend/app/repositories/usage_log.py` 新增 `by_project_model()`:`SELECT project_uid, Project.code, Project.name, model, count(pid), coalesce(sum(total_tokens),0), coalesce(sum(cost_usd),0)`;**INNER JOIN** `Project`(與既有 `by_project` 一致,NULL 專案不入);`group_by(project_uid, Project.code, Project.name, model)`;套用既有 `_apply_filters`;排序 `Project.code, sum(cost_usd) DESC`。回傳型別對齊既有 tuple 慣例。
- **endpoint**:`stats.py` 新增 `by_project_model_endpoint`(緊鄰 `by_project_endpoint`):`UserDep` + `resolve_filters`;`success_response(data=[item.model_dump(mode="json") ...])`;summary 標「依專案×模型彙總」。**不新增索引 / env / migration**。

## Acceptance

- [ ] `uv run pytest backend/tests/api/test_stats.py backend/tests/repositories/test_usage_log_stats.py` 全綠
- [ ] pytest 對 OpenAPI 斷言:`/api/v1/stats/by-project-model` GET 存在
- [ ] 測試涵蓋:admin 取全部;非-admin 傳他部門 `department_uid` → 403;非-admin 不傳 → 自動鎖 `actor.department_uid`;無資料 → `200 + data=[]`;歷史 `project_uid IS NULL` 的 log 不出現在結果
- [ ] 交叉驗證:某專案各模型 `total_cost_usd` 加總 == 既有 `by_project` 該專案 `total_cost_usd`
- [ ] `grep -n "resolve_filters" backend/app/api/v1/usage_logs.py` 此時**零命中**(尚未被 421 引用),但 `backend/app/api/v1/_scope_filters.py` 存在且 `stats.py` 由此 import
- [ ] `cd backend && uv run mypy app/ && uv run ruff check .` 零錯誤零 warning
- [ ] response 殼為 ApiResponse(`03-backend/01-routing.md`)

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/01-routing.md`
- `docs/Design-Base/03-backend/02-auth.md`
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/03-backend/92-project-permission.md`
- `docs/Design-Base/03-backend/90-project-backend.md`
- `docs/Design-Base/04-databases/05-precision.md`
- `docs/Design-Base/04-databases/09-indexes-and-perf.md`
- `docs/Design-Base/00-overview/04-api-docs.md`
- `docs/Design-Base/90-third-party-service/50-openrouter.md`
