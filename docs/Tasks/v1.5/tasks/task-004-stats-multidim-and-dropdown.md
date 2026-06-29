---
id: task-004
title: 統計 API 三維篩選 + 依專案/依使用者彙總 + users dropdown
status: done
parallel: true
depends_on: [task-001]
affected_files:
  - backend/app/repositories/usage_log.py
  - backend/app/repositories/user.py
  - backend/app/schemas/stats.py
  - backend/app/schemas/user.py
  - backend/app/api/v1/stats.py
  - backend/app/api/v1/users.py
estimated_hours: 4
---

## 目標
把統計 API 由單一部門維度擴展為「部門 / 專案 / 使用者」三維篩選，新增依專案與依使用者彙總視圖，並提供 users dropdown 端點供前端篩選器使用。

## Acceptance
- [x] `app/repositories/usage_log.py:_apply_filters` 加 `project_uid` 參數；`overview` / `by_department` / `by_model` / `timeseries` 簽名加 `project_uid` / `user_uid`（預設 None，backward compatible）
- [x] 新增 `by_project()`（INNER JOIN projects，歷史 NULL 自然排除）與 `by_user()`（LEFT JOIN users，含未知顯示 null）
- [x] `app/schemas/stats.py` 新增 `ProjectStatItem` / `UserStatItem`；`app/schemas/user.py` 新增 `UserDropdownItem`（精簡欄位 user_uid/username/employee_id/department_uid）
- [x] `app/repositories/user.py` 新增 `list_for_dropdown(department_uid=None, limit=2000) -> list[User]`
- [x] `app/api/v1/stats.py`：`_resolve_dept` 改為 `_resolve_filters`（三維、non-admin 強鎖部門）；4 個既有 endpoint 加 `project_uid`/`user_uid` query params；新增 `GET /stats/by-project` 與 `GET /stats/by-user`
- [x] `app/api/v1/users.py` 新增 `GET /users/dropdown`（`UserDep`，non-admin 鎖自部門），註冊順序在 `GET /{user_uid}` 之前

## 必讀檔(Just-in-time)
- [`04-databases/10-statistics-log.md`](../../../Design-Base/04-databases/10-statistics-log.md) · [`04-databases/09-indexes-and-perf.md`](../../../Design-Base/04-databases/09-indexes-and-perf.md) · [`03-backend/01-routing.md`](../../../Design-Base/03-backend/01-routing.md) · [`03-backend/92-project-permission.md`](../../../Design-Base/03-backend/92-project-permission.md) · [`03-backend/08-performance.md`](../../../Design-Base/03-backend/08-performance.md) · [`00-overview/04-api-docs.md`](../../../Design-Base/00-overview/04-api-docs.md)
