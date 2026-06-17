# Tasks v1.9.0

## 版本資訊

- 前置依賴:既有後台 CRUD / 權限(`UserDep` / `AdminDep`)、sidebar / RouteGuard、登入認證鏈路已完成。
- 本版本範圍:新增 **「API Key 申請表單」** 全端功能。member 與 admin 皆可進入頁面送出申請(6 欄全必填),申請寫入新資料表 `api_key_requests`;檢視分流:**admin 看全部、member 只看自己送出**。本版只做 **送出 + 檢視**,**審核流程移至 v1.9.1**。
- 對齊的 Design-Base 章節:
  - [80-permission.md § 後台存取規則](../../Design-Base/80-permission.md)
  - [90-task-spec.md § 4 / § 5](../../Design-Base/90-task-spec.md)
- 母本 propose:[`propose-v1.9.0.md`](./propose-v1.9.0.md)(包含設計推導與決議過程)

> 本 Tasks 為**實作契約**;設計理由與替代方案請參考母本 propose。內容若與 propose 衝突,以本檔為準。

## Definition of Done

### DB / Migration

- [x] 新增資料表 `api_key_requests`(欄位見「資料模型」),含 `TimestampMixin`。
- [x] 新增 migration `0012_api_key_requests`(`down_revision = "0011_usage_log_used_tools"`)。
- [x] migration 建 `updated_at` trigger(沿用 `set_updated_at()`)與 index:`applicant_user_uid`(member 過濾)、`created_at`(排序)。
- [ ] `alembic upgrade head` 成功,且 `alembic downgrade -1` 可還原(drop table / trigger / index)。**(待使用者於有 DB 的開發環境執行;本機無 DB 未套用)**

### 後端

- [x] Model `models/api_key_request.py`:`Base` + `TimestampMixin`;`request_uid` 為對外 UUID v7。
- [x] 於 `models/__init__.py` export `ApiKeyRequest`。
- [x] Schema `schemas/api_key_request.py`:`ApiKeyRequestCreateRequest`(6 欄全必填)、`ApiKeyRequestResponse`(`from_attributes=True`)。
- [x] `project_url` 後端驗證:scheme 為 http/https 且 host 屬 GitHub / Replit,否則 `422`(規則見「欄位驗證」)。
- [x] `owner_email` 以 email 格式驗證,否則 `422`。
- [x] Repository `repositories/api_key_request.py`:`add()` / `list(applicant_user_uid=None, page, size)`(回 `(items, total)`)/ `get_by_uid()`。
- [x] Router `api/v1/api_key_requests.py`:
  - [x] `POST /api/v1/api-key-requests`(`UserDep`):`applicant_user_uid` 由 `Actor` 注入(**前端不可指定**),`status="pending"`,寫入後 `write_audit(action="create_api_key_request")`,回 `ApiKeyRequestResponse`。
  - [x] `GET /api/v1/api-key-requests`(`UserDep`):admin → `list()`;member → `list(applicant_user_uid=actor.user_uid)`;分頁回 `Page[ApiKeyRequestResponse]`。
- [x] 於 `api/v1/__init__.py` 註冊 router(`prefix="/api-key-requests"`)。
- [x] Swagger 於 `/api/docs` 反映兩端點(Pydantic schema 自動產生)。
- [x] member 呼叫 `GET` 不論帶任何 query,皆**只**取得本人資料(後端強制過濾,不信任前端參數)。

### 前端

- [x] 新頁面 `app/(main)/api-key-requests/page.tsx`:上方 6 欄申請表單 + 下方歷程列表(分頁)。
- [x] Sidebar `Sidebar.tsx` 新增 nav item「API Key 申請表單」,**不設 `adminOnly`**。
- [x] RouteGuard `RouteGuard.tsx` 的 `MEMBER_ALLOWED_PREFIXES` 加入 `"/api-key-requests"`。
- [x] Endpoint `lib/api/endpoints.ts` 新增 `apiKeyRequests`。
- [x] Type `types/api.ts` 新增 `ApiKeyRequest` / `ApiKeyRequestCreate`。
- [x] 表單:6 欄全必填,`project_url` 與 `owner_email` 前端即時格式提示;送出成功 toast + reload,失敗 `showDialog(error, err.localizedDetail)`。
- [x] 列表:admin 與 member 共用同頁,前端不判 role 切換查詢(範圍由後端決定);顯示「待審核」狀態 badge 與申請時間,分頁「共 N 筆 · 第 X / Y 頁」。

### 文件

- [x] `/user-guide`(使用者使用說明)補一段「如何送出 API Key 申請」。

### 不做(v1.9.0 明確排除 → v1.9.1)

- 審核(核准 / 駁回 / 退回補件)、申請狀態流轉、通知(Email / 站內信)。
- member 編輯 / 刪除 / 撤回已送出申請。
- 重複送出去重(暫不限制,待後續決定;本版不因此改 schema)。
- 申請通過後自動發 Key / 建部門 / 建專案。

## 資料模型 `api_key_requests`

| 欄位 | 型別 | 約束 / 說明 |
| --- | --- | --- |
| `pid` | BigInteger | PK,autoincrement |
| `request_uid` | UUID | unique, not null(UUID v7,對外) |
| `applicant_user_uid` | UUID | not null;後端由 Actor 注入 |
| `department_name` | String(128) | not null |
| `department_code` | String(32) | not null(如 `T000`) |
| `project_name` | String(128) | not null |
| `project_url` | String(512) | not null;須為 GitHub / Replit(見「欄位驗證」) |
| `owner_name` | String(64) | not null |
| `owner_email` | String(255) | not null;email 格式 |
| `status` | String(16) | not null, server_default `pending`(本版不流轉) |
| `created_at` / `updated_at` | DateTime(tz) | `TimestampMixin`,server_default now() |
| `is_active` / `is_deleted` | Boolean | `TimestampMixin`,server_default true / false |

> 欄位長度為建議值,定稿時可依實際調整;`status` 預留供 v1.9.1。

## 欄位驗證

### `project_url`（GitHub / Replit 限定）

- scheme 必須為 `http` 或 `https`。
- host(去掉 port、小寫)須符合下列其一:
  - `github.com`、`www.github.com`
  - `replit.com`、任意 `*.replit.com` 子網域
  - `replit.dev`、任意 `*.replit.dev` 子網域
- 不符 → `422`(Pydantic 自訂 validator)。
- 實作落點:`schemas/api_key_request.py` 的 `ApiKeyRequestCreateRequest.project_url` field validator。

### 其他欄位

- 6 欄皆 `min_length>=1`(必填,空字串 → 422)。
- `owner_email`:email 格式(`EmailStr` 或等效 validator）。

## API 端點

| Method | Path | 權限 | Request | Response |
| --- | --- | --- | --- | --- |
| `POST` | `/api/v1/api-key-requests` | `UserDep` | `ApiKeyRequestCreateRequest`(6 欄) | `ApiResponse[ApiKeyRequestResponse]` |
| `GET` | `/api/v1/api-key-requests` | `UserDep` | query: `page`(>=1)、`size`(1..200) | `ApiResponse[Page[ApiKeyRequestResponse]]` |

- `POST` 由後端注入 `applicant_user_uid` 與 `status="pending"`;`request_uid = UUID(str(uuid7()))`。
- `GET` 範圍:`actor.is_admin` → 全部;否則 `applicant_user_uid == actor.user_uid`。
- 回應統一 `success_response(data=...model_dump(mode="json"), detail="success")`。

## 權限與稽核

| 操作 | 端點 | 角色 | 範圍 |
| --- | --- | --- | --- |
| 送出申請 | `POST` | admin / member | 皆可;申請人鎖定為自己 |
| 查看申請 | `GET` | admin | 全部 |
| 查看申請 | `GET` | member | 僅本人 |

- 三處權限須一致:sidebar(不設 adminOnly)+ RouteGuard(`/api-key-requests` 入白名單)+ 後端(`UserDep`)。
- 稽核:`POST` 後寫 `write_audit(action="create_api_key_request", target_type="api_key_request", target_uid=request_uid, ...)`;`GET` 為唯讀,不寫稽核。

## 錯誤處理對照表

| 情境 | 時機 | HTTP / 行為 | detail |
| --- | --- | --- | --- |
| 任一欄缺漏 / 空字串 | 驗證 | 422 | Pydantic validation |
| `project_url` 非 GitHub / Replit | 驗證 | 422 | `project_url` field validator |
| `owner_email` 格式錯 | 驗證 | 422 | email validation |
| 未登入 / token 失效 | 認證 | 401 | `unauthorized`(`UserDep`) |
| member 嘗試查他人(帶竄改 query) | 端點 | 200 但僅回本人 | 後端強制過濾,非報錯 |

## 交付物清單

- 後端:
  - 新增 [`backend/app/models/api_key_request.py`](../../../backend/app/models/api_key_request.py)
  - 修改 [`backend/app/models/__init__.py`](../../../backend/app/models/__init__.py)(export)
  - 新增 [`backend/app/schemas/api_key_request.py`](../../../backend/app/schemas/api_key_request.py)
  - 新增 [`backend/app/repositories/api_key_request.py`](../../../backend/app/repositories/api_key_request.py)
  - 新增 [`backend/app/api/v1/api_key_requests.py`](../../../backend/app/api/v1/api_key_requests.py)
  - 修改 [`backend/app/api/v1/__init__.py`](../../../backend/app/api/v1/__init__.py)(註冊 router)
  - 新增 `backend/alembic/versions/0012_api_key_requests.py`
- 前端:
  - 新增 [`frontend/src/app/(main)/api-key-requests/page.tsx`](../../../frontend/src/app/(main)/api-key-requests/page.tsx)
  - 修改 [`frontend/src/components/layout/Sidebar.tsx`](../../../frontend/src/components/layout/Sidebar.tsx)
  - 修改 [`frontend/src/components/layout/RouteGuard.tsx`](../../../frontend/src/components/layout/RouteGuard.tsx)
  - 修改 [`frontend/src/lib/api/endpoints.ts`](../../../frontend/src/lib/api/endpoints.ts)
  - 修改 [`frontend/src/types/api.ts`](../../../frontend/src/types/api.ts)
- Migration:`0012_api_key_requests`。
- 環境變數:無新增。
- 文件:更新 `/user-guide`。

## 測試重點

- 送出:6 欄正確 → 201/200 寫入,`applicant_user_uid` 為當前登入者、`status="pending"`。
- 驗證:缺任一欄 / `project_url` 非 GitHub|Replit / `owner_email` 格式錯 → 422。
- 範圍:admin `GET` 看到全部;member `GET` 只看到自己(即使帶 `applicant_user_uid` query 也無效)。
- 權限:未登入 `GET`/`POST` → 401;member 進 `/api-key-requests` 不被 RouteGuard 導走。
- 稽核:每次 `POST` 產生一筆 `create_api_key_request` audit log。
