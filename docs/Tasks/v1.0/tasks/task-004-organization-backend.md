---
id: task-004
title: 組織結構後端(departments / projects CRUD + V2 migration + user 掛部門)
status: done
parallel: true
depends_on: [task-001]
affected_files:
  - migrations/V2__organization.sql
  - backend/app/api/v1/departments.py
  - backend/app/api/v1/projects.py
  - backend/app/services/department/
  - backend/app/services/project/
  - backend/app/repositories/department.py
  - backend/app/repositories/project.py
  - backend/app/schemas/department.py
  - backend/app/schemas/project.py
  - backend/tests/api/test_departments.py
  - backend/tests/api/test_projects.py
estimated_hours: 3
---

## 目標

依 propose § 2 實作部門 / 專案兩層組織:V2 migration 建 `departments` + `projects`,ALTER `users` 加 `department_uid` / `employee_id` / `email` 與 `SYSTEM` 部門 Seed;CRUD 端點 + 軟刪除前置檢查(部門需無啟用 Key / project / user);一般 `user` 僅可讀自身部門資源(service 層以 `actor.department_uid` 比對)。

## Acceptance

- [x] `uv run pytest tests/api/test_departments.py tests/api/test_projects.py` 全綠
- [x] V2 套用後 `departments` / `projects` 含必備欄位 + 唯一索引(`uq_departments_code` / `uq_projects_dept_code`,WHERE `is_deleted=FALSE`)
- [x] 代碼重複 → 409 `code_conflict`;非 admin 寫入 → 403 `forbidden`;user 讀他部門 → 403 `forbidden`(測試斷言)
- [x] 部門尚有啟用 Key / project / user 時刪除被擋(測試斷言)

## 必讀檔(Just-in-time)

- [`03-backend/00-overview.md`](../../../Design-Base/03-backend/00-overview.md) · [`01-routing.md`](../../../Design-Base/03-backend/01-routing.md)
- [`04-databases/00-overview.md`](../../../Design-Base/04-databases/00-overview.md) · [`01-identifiers.md`](../../../Design-Base/04-databases/01-identifiers.md) · [`02-soft-delete.md`](../../../Design-Base/04-databases/02-soft-delete.md)
- [`03-backend/92-project-permission.md`](../../../Design-Base/03-backend/92-project-permission.md)
