---
id: task-003
title: 後端 Router(POST/GET 依角色分流 + 稽核)與註冊
status: done
parallel: false
depends_on: [task-002]
affected_files:
  - backend/app/api/v1/api_key_requests.py
  - backend/app/api/v1/__init__.py
estimated_hours: 3
---

## 目標
建立 `api-key-requests` router(`POST` 送出、`GET` 列表分頁),`POST` 由 Actor 注入 `applicant_user_uid` 並寫稽核,`GET` 依 `actor.is_admin` 後端強制分流範圍,並於 `__init__.py` 註冊。

## Acceptance
- [x] `POST /api/v1/api-key-requests`(`UserDep`):`applicant_user_uid` 由 `Actor` 注入(前端不可指定)、`status="pending"`,寫入後 `write_audit(action="create_api_key_request", target_type="api_key_request", target_uid=request_uid)`,回 `ApiKeyRequestResponse`。
- [x] `GET /api/v1/api-key-requests`(`UserDep`):admin → `list()` 全部;member → `list(applicant_user_uid=actor.user_uid)`,回 `Page[ApiKeyRequestResponse]`;`page>=1`、`size 1..200`。
- [x] member 帶任何 `applicant_user_uid` query 皆無效,後端強制只回本人資料(200 非報錯)。
- [x] 於 `api/v1/__init__.py` 以 `prefix="/api-key-requests"` 註冊 router;`/api/docs` Swagger 反映兩端點;回應統一 `success_response(data=...model_dump(mode="json"), detail="success")`。

## 必讀檔(Just-in-time)
- [`03-backend/01-routing.md`](../../../Design-Base/03-backend/01-routing.md) · router 註冊 / 統一回應
- [`03-backend/02-auth.md`](../../../Design-Base/03-backend/02-auth.md) · UserDep / Actor 注入
- [`03-backend/92-project-permission.md`](../../../Design-Base/03-backend/92-project-permission.md) · 後端強制權限分流
- [`03-backend/05-exceptions-and-logging.md`](../../../Design-Base/03-backend/05-exceptions-and-logging.md) · 401 / 稽核 write_audit
- [`00-overview/04-api-docs.md`](../../../Design-Base/00-overview/04-api-docs.md) · Swagger / API 文件
