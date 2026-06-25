---
id: task-002
title: 代理鏈認證解析 X-Project-Code 並驗證專案歸屬
status: done
parallel: false
depends_on: [task-001]
affected_files:
  - backend/app/schemas/actor.py
  - backend/app/core/deps.py
  - backend/app/core/sdk_auth.py
  - backend/app/repositories/project.py
estimated_hours: 3
---

## 目標
讓 SDK 代理鏈解析 `X-Project-Code` header，並在既有 SDK Key + User Token + 部門一致性檢查之後追加專案歸屬驗證，把 `project_uid` 帶入 `SdkCallerContext`。

## Acceptance
- [x] `app/schemas/actor.py:SdkCallerContext` 新增 `project_uid: UUID` 與 `project_code: str` 欄位
- [x] `app/core/deps.py:require_sdk_caller` 解析 project header；缺漏 → `AppError("project_code_required", 400)`
- [x] `app/repositories/project.py` 新增 `get_active_by_uid_and_dept(project_uid, department_uid) -> Project | None`（`is_active=TRUE` 且 `is_deleted=FALSE`）
- [x] `app/core/sdk_auth.py:resolve_sdk_caller` 在部門/user 驗證後驗證專案歸屬，失敗（不存在 / 不屬同部門 / 已停用）→ `AppError("project_invalid", 400)`
- [x] 驗證通過時把 `project_uid` / `project_code` 寫入回傳的 `SdkCallerContext`

## 必讀檔(Just-in-time)
- [`03-backend/02-auth.md`](../../../Design-Base/03-backend/02-auth.md) · [`03-backend/92-project-permission.md`](../../../Design-Base/03-backend/92-project-permission.md) · [`03-backend/05-exceptions-and-logging.md`](../../../Design-Base/03-backend/05-exceptions-and-logging.md) · [`03-backend/01-routing.md`](../../../Design-Base/03-backend/01-routing.md) · [`90-third-party-service/50-openrouter.md`](../../../Design-Base/90-third-party-service/50-openrouter.md)
