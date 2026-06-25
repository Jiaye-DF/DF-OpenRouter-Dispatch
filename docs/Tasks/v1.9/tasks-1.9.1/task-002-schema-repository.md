---
id: task-002
title: 後端 Schema 與 Repository 查詢方法擴充
status: done
parallel: true
depends_on: []
affected_files:
  - backend/app/schemas/api_key_request.py
  - backend/app/repositories/user.py
  - backend/app/repositories/project.py
  - backend/app/repositories/sdk_api_key.py
  - backend/app/repositories/api_key_request.py
estimated_hours: 3
---

## 目標
擴充申請單 schema(新欄位、取消請求、詳情回應),並為路由/開通新增存在性查詢與欄位更新 repository 方法。

## Acceptance
- [x] `schemas/api_key_request.py`:`ApiKeyRequestResponse` 加生命週期新欄位;新增 `CancelRequest`(`reason` 必填)與 `ApiKeyRequestDetailResponse`(含 `agent_decision` 與一次性憑證)。
- [x] `repositories/user.py` 新增 `get_by_email(email) -> list[User]`(email 無唯一約束,回 list 判斷 0/1/多筆),查詢層排除 `account='admin'`。
- [x] `repositories/project.py` 新增 `get_active_by_department_and_name(department_uid, name) -> Project | None`(僅未軟刪除)。
- [x] `repositories/sdk_api_key.py` 新增 `get_active_by_department(department_uid) -> SdkApiKey | None`。
- [x] `repositories/api_key_request.py` 新增 `update_fields()` 供狀態流轉寫回。

## 必讀檔(Just-in-time)
- [`03-backend/00-overview.md`](../../../Design-Base/03-backend/00-overview.md) · 後端分層
- [`04-databases/02-soft-delete.md`](../../../Design-Base/04-databases/02-soft-delete.md) · active 查詢需排除軟刪除
- [`04-databases/09-indexes-and-perf.md`](../../../Design-Base/04-databases/09-indexes-and-perf.md) · 查詢索引
