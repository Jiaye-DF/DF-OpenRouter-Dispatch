# Tasks v1.5.0

## 版本資訊

- 前置依賴:v1.4.0(部署與 UX 維護修正集);v1.3.0 SSO 整合
- 本版本範圍:`X-Project-Code` 串入代理鏈、`usage_logs.project_uid` 寫入、儀表板部門/專案/使用者三層篩選 + 依專案 / 依使用者彙總
- 對齊的 Design-Base 章節:
  - [20-backend.md § 1 統一 Response 格式](../../Design-Base/20-backend.md#1-統一-response-格式)
  - [30-database.md § 5 Migration](../../Design-Base/30-database.md#5-migration)
  - [50-openrouter.md § 10 用量紀錄](../../Design-Base/50-openrouter.md#10-用量紀錄usage-log)
  - [80-permission.md § 5 代理端Proxy存取規則](../../Design-Base/80-permission.md#5-代理端proxy存取規則)
- 母本 propose:[`propose-v1.5.0.md`](./propose-v1.5.0.md)(包含設計推導與決議過程)

> 本 Tasks 為**實作契約**;設計理由與替代方案請參考母本 propose。內容若與 propose 衝突,以本檔為準。

## Definition of Done

### Migration

- [x] Alembic revision `0005_usage_logs_project_uid` 完成:
  - `usage_logs` 加 `project_uid UUID NULL`
  - FK 到 `projects(project_uid)`,`ON DELETE SET NULL`
  - `CREATE INDEX idx_usage_logs_project_uid_time ON usage_logs (project_uid, created_at) WHERE is_deleted = FALSE`

### Backend

#### Schema 同步

- [x] `app/models/usage_log.py`:`project_uid: Mapped[UUID | None]`
- [x] `app/schemas/actor.py`:`SdkCallerContext` 加 `project_uid: UUID` / `project_code: str`
- [x] `app/schemas/stats.py`:新增 `ProjectStatItem` / `UserStatItem`
- [x] `app/schemas/user.py`:新增 `UserDropdownItem`(精簡欄位供下拉)

#### Repository

- [x] `app/repositories/project.py` 新增 `get_active_by_uid_and_dept(project_uid, department_uid) -> Project | None`
- [x] `app/repositories/user.py` 新增 `list_for_dropdown(department_uid=None, limit=2000) -> list[User]`
- [x] `app/repositories/usage_log.py`:
  - `_apply_filters` 加 `project_uid` 參數
  - `overview` / `by_department` / `by_model` / `timeseries` 簽名加 `project_uid` / `user_uid`(預設 None,backward compatible)
  - 新增 `by_project()`(INNER JOIN projects → 歷史 NULL 自然排除)
  - 新增 `by_user()`(LEFT JOIN users → 含未知)

#### Auth(代理鏈)

- [x] `app/core/deps.py:require_sdk_caller` 解析 `x-project-id` header:
  - 缺 → `AppError("project_code_required", 400)`
- [x] `app/core/sdk_auth.py:resolve_sdk_caller` 新增 `project_code: str` 參數;
  - 在既有部門 / user 驗證後,呼叫 `ProjectRepository.get_active_by_code_and_dept(project_code, sdk_row.department_uid)`,失敗(不存在 / 不屬同部門 / 已停用) → `AppError("project_invalid", 400)`
  - 將 `project.project_uid` / `project.code` 寫入回傳的 `SdkCallerContext`(SdkCallerContext 仍以 UUID 為內部識別,供 usage_log 寫入)

#### Service(代理)

- [x] `app/services/proxy.py`:
  - `schedule_usage_log` 簽名加 `project_uid: UUID | None`;`UsageLog(...)` row 寫入 `project_uid=project_uid`
  - `run_chat` 簽名加 `project_uid: UUID`
  - `_run_chat_openrouter` / `_run_chat_internal` / `_try_internal_call` 簽名加 `project_uid: UUID`
  - 所有 `schedule_usage_log(...)` 呼叫點(共 7 處:OR 4 處、Internal 3 處)都帶 `project_uid=project_uid`

#### API

- [x] `app/api/v1/model_chat.py:_chat_handler` 傳 `project_uid=caller.project_uid` 到 `run_chat`
- [x] `app/api/v1/stats.py`:
  - 把 `_resolve_dept(actor, dept_uid)` 改為 `_resolve_filters(actor, dept, project, user)`;non-admin 強鎖部門
  - 4 個既有 endpoint 加 `project_uid` / `user_uid` query params
  - 新增 `GET /stats/by-project`(`ProjectStatItem[]`)
  - 新增 `GET /stats/by-user`(`UserStatItem[]`)
- [x] `app/api/v1/users.py`:
  - 新增 `GET /users/dropdown`(`UserDep`;non-admin 鎖自部門);註冊順序在 `GET /{user_uid}` 之前(避免 path 衝突)
  - 回傳 `UserDropdownItem[]`

#### 文件

- [x] `docs/INTEGRATION.md`:§ 2 加 X-Project-Code 列;§ 4 範例加 header + 錯誤碼說明;§ 7 curl/Python 範例加 header;§ 8 加 `project_code_required` / `project_invalid` 兩列

### Frontend

#### Types / Endpoints

- [x] `frontend/src/types/api.ts`:
  - 新增 `StatsByProject` / `StatsByUser` / `UserDropdownItem`
  - `UsageLog` 加 `project_uid: string | null`
  - `StatsByDepartment` 加 `department_code: string | null`
  - `StatsByModel` 加 `total_requests` / `prompt_tokens` / `completion_tokens`(可選)
- [x] `frontend/src/lib/api/endpoints.ts` 加 `usersDropdown` / `statsByProject` / `statsByUser`
- [x] `frontend/src/lib/api/error-map.ts` 加 `project_code_required` / `project_invalid` 中文化

#### 元件

- [x] `frontend/src/components/feature/stats/ByProjectBar.tsx`(抄 DeptTokensBar,改 dataKey/title)
- [x] `frontend/src/components/feature/stats/ByUserBar.tsx`(同上)
- [x] `frontend/src/components/feature/stats/DashboardFilters.tsx`:
  - 3 個 select(部門 / 專案 / 使用者),每個都有「全部」選項
  - admin:可任選;non-admin:部門固定為自己,顯示 badge
  - 切部門時自動把 project / user 重設,並重新拉對應下拉清單

#### Dashboard 頁

- [x] `frontend/src/app/(main)/dashboard/page.tsx`:
  - state:`{ department_uid, project_uid, user_uid }`
  - 6 個 stats 呼叫(原 4 個 + 新 by-project / by-user)都帶 filters
  - layout:filters → KPI → (DeptBar / ModelStacked) → (ByProjectBar / ByUserBar) → Timeseries

#### 文件頁

- [x] `frontend/src/app/(main)/user-guide/page.tsx`:
  - PageTitle description 改為「SDK Key + User Token + Project ID」
  - 概述 / 憑證 section:三組憑證描述
  - 憑證 grid 從 2-column 改 3-column,加 X-Project-Code 卡片
  - HTTP 端點 CodeBlock 加 X-Project-Code 行;說明列表更新為「三個 Header 必填」與對應錯誤碼
  - CURL / Python 範例加 X-Project-Code header / PROJECT_CODE 變數
  - `ERRORS` 陣列加 `project_code_required` / `project_invalid` 兩條

### 補齊歷史文件

- [x] `docs/Tasks/v1.3/propose-v1.3.0.md`:依 git log(`5923d89` + `4c3cd15`)追溯撰寫 DF-SSO 整合
- [x] `docs/Tasks/v1.4/propose-v1.4.0.md`:依 git log(5 個維護 commit)追溯撰寫修正集

### 驗證

- [ ] `cd backend && alembic upgrade head` 成功;`usage_logs` 表有 `project_uid` 欄位 + index + FK
- [ ] `cd backend && pytest` 全綠(若 SDK auth / stats 測試需更新,本版一併修)
- [ ] `cd frontend && npm run build` 通過(TypeScript 編譯無 error)
- [ ] E2E:
  - admin 建立部門 A → 部門 A 下建專案 P1, P2 → 建使用者 U1(屬 A)→ 建 SDK Key K1 → 產生 U1 的 User Token T1
  - curl 帶 3 個 header(K1 + T1 + P1.uuid)POST `/api/v1/model/chat` → 預期 200;`usage_logs` 該筆 `project_uid = P1`
  - curl 不帶 `X-Project-Code` → 預期 400 `project_code_required`
  - curl 帶 P1.uuid 但 SDK Key 屬於部門 B → 預期 400 `project_invalid`
- [ ] Dashboard(admin):三個篩選下拉皆可用,選了部門後 project/user 下拉限縮
- [ ] Dashboard(non-admin):部門固定為 badge,project/user 下拉只見自己部門
- [ ] 「依專案彙總」chart 不顯示歷史 NULL project 紀錄
