---
id: task-003
title: 規則路由引擎(確定性決策樹 + 硬規則)
status: done
parallel: false
depends_on: [task-002]
affected_files:
  - backend/app/services/api_key_request_router.py
estimated_hours: 3
---

## 目標
實作 `api_key_request_router.py`,依「部門 / 專案 / 使用者」存在性與確定性硬規則,把申請路由到自動候選 / 人工 / 系統取消。

## Acceptance
- [x] `route(db, req) -> RouteResult` 實作決策樹:新部門→`manual_pending`;部門名稱與既有不符→`manual_pending`(硬規則);舊部門+新專案→AI 候選;email 命中多筆→`manual_pending`(硬規則);舊部門+舊專案+新使用者→`manual_pending`;舊部門+舊專案+舊使用者→`cancelled`(`cancel_source='system'`,reason「過去已存在相同 Key 資料」)。
- [x] 存在性判斷使用 `department.get_by_code`、`project.get_active_by_department_and_name`、`user.get_by_email`(排除 admin,命中唯一一筆才算舊)。
- [x] 硬規則(部門名稱不符、email 多筆)順序先於 AI 與其他分支。
- [x] `DEFAULT_OPENROUTER_KEY` 未設/為空時,AI 候選分支結果降級為 `manual_pending`(不報錯)。
- [x] `RouteResult` 帶回路由決定、命中部門、後續是否需 AI 驗證等資訊。

## 必讀檔(Just-in-time)
- [`03-backend/00-overview.md`](../../../Design-Base/03-backend/00-overview.md) · service 分層
- [`03-backend/92-project-permission.md`](../../../Design-Base/03-backend/92-project-permission.md) · admin 排除與權限語意
- [`90-third-party-service/50-openrouter.md`](../../../Design-Base/90-third-party-service/50-openrouter.md) · DEFAULT_OPENROUTER_KEY 降級條件
