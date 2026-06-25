---
id: task-001
title: 後端新增 owner-options 端點(平台 member 清單,排除 admin)
status: done
parallel: true
depends_on: []
affected_files:
  - app/repositories/user.py
  - app/schemas/user.py
  - app/api/v1/users.py
estimated_hours: 2
---

## 目標
新增 `GET /api/v1/users/owner-options`,回傳現有平台 member 的 `username` + `email`,作為申請表單「專案負責人」Combobox 的資料來源,從源頭確保名稱與 M365 一致。

## Acceptance
- [x] `repositories/user.py` 新增 `list_owner_options(limit=2000)`,撈未刪除、啟用、具 Email 的使用者,排除 `account='admin'`,依 `username` 排序。
- [x] `schemas/user.py` 新增 `UserOwnerOption`(欄位 `username` + `email`,`from_attributes=True`)。
- [x] `api/v1/users.py` 新增 `GET /api/v1/users/owner-options`(`UserDep`,任何登入者可用,回傳純陣列)。
- [x] 路由宣告於 `/{user_uid}` **之前**,不被路徑參數攔截;Swagger(`/api/docs`)自動同步 summary 與回應。
- [x] 後端 `py_compile` 通過(`users.py` / `schemas/user.py` / `repositories/user.py`)。

## 必讀檔(Just-in-time)
- [`03-backend/01-routing.md`](../../../Design-Base/03-backend/01-routing.md) · 路由宣告順序(靜態路徑先於 `/{param}`)
- [`03-backend/02-auth.md`](../../../Design-Base/03-backend/02-auth.md) · `UserDep` 一般登入者授權
- [`03-backend/92-project-permission.md`](../../../Design-Base/03-backend/92-project-permission.md) · 排除 `account='admin'` 一致性
- [`04-databases/02-soft-delete.md`](../../../Design-Base/04-databases/02-soft-delete.md) · 撈未刪除使用者
