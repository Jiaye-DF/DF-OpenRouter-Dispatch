[//]: # (此檔為 v1.9 任務提案,實作前先由使用者確認範圍與設計取捨。)

# Propose v1.9.0 · API Key 申請表單(送出 + 檢視)

> 此為 **proposal**(規劃草案),確認後即轉為正式 `tasks-v1.9.0.md`。
>
> 對應母本:[v1.8 檔案上傳(PDF 等)支援](../v1.8/propose-v1.8.0.md)。

## 1. 目標

在後台新增一個 **「API Key 申請表單」** 頁面(sidebar 入口,**admin 與 member 皆可進入**),讓使用者填寫必要資訊送出申請,系統將每筆申請寫入 DB。檢視權限分流:

- **admin**:看到**全部**申請單。
- **member**:只看到**自己送出**的歷程紀錄。

本版只做 **送出 + 檢視**(全端打通:DB 表 → 後端 CRUD → 前端頁面 + sidebar)。**審核(核准 / 駁回)流程屬 v1.9.1**,本版不做。

必填欄位(申請人填寫):

| 欄位 | 範例 | 說明 |
| --- | --- | --- |
| 部門名稱 | 資訊部 | 自由文字 |
| 部門代號 | `T000` | 自由文字(申請人自填,非綁定既有 `departments`,見 § 5.1) |
| 專案名稱 | 客服機器人 | 自由文字 |
| 專案連結 | `https://github.com/df/cs-bot` | **必須**為 GitHub 或 Replit 連結(格式驗證,見 § 5.5) |
| 專案負責人名稱 | 王小明 | 自由文字 |
| 專案負責人信箱 | ming@df-recycle.com.tw | Email 格式驗證 |

## 2. 動機

- 目前申請 API Key 走線下(口頭 / 通訊軟體),無正式紀錄,管理者難以追蹤「誰、為了哪個專案、申請了什麼」。
- 既有後台已有完整的 CRUD / 權限 / sidebar / 表單 / 列表慣例(`departments`、`users` 等頁),新增一個申請表頁面為既有模式的標準複製,改動面可控。
- member 在後台目前僅能看儀錶板與使用說明(對齊 [80-permission](../../Design-Base/80-permission.md));本版讓 member 第一次有「可主動送出資料」的頁面,並只看自己的歷程,為 v1.9.1 的審核流程鋪路。

## 3. 範圍

### In Scope

**DB**:

- 新增資料表 `api_key_requests`(欄位見 § 6),含 `TimestampMixin`(`is_active` / `is_deleted` / `created_at` / `updated_at`)。
- 新增 Alembic migration `0012_api_key_requests`(接於現有最新 `0011_usage_log_used_tools` 之後)。

**後端**:

- Model [`models/api_key_request.py`](../../../backend/app/models/api_key_request.py)(`Base` + `TimestampMixin`,`request_uid` 為對外 UUID v7)。
- Schema [`schemas/api_key_request.py`](../../../backend/app/schemas/api_key_request.py):`ApiKeyRequestCreateRequest`(6 必填欄)、`ApiKeyRequestResponse`。
- Repository [`repositories/api_key_request.py`](../../../backend/app/repositories/api_key_request.py):`add()` / `list(applicant_user_uid=None, page, size)` / `get_by_uid()`。
- Router [`api/v1/api_key_requests.py`](../../../backend/app/api/v1/api_key_requests.py):
  - `POST /api/v1/api-key-requests`(`UserDep` — 登入即可,admin/member 皆能送出)。
  - `GET /api/v1/api-key-requests`(`UserDep` — admin 回全部,member 自動過濾為本人,見 § 5.2)。
- 於 [`api/v1/__init__.py`](../../../backend/app/api/v1/__init__.py) 註冊新 router。
- 於 [`models/__init__.py`](../../../backend/app/models/__init__.py) export 新 Model。
- 寫入操作(POST 建立)依既有慣例呼叫 `write_audit`(`action="create_api_key_request"`)。

**前端**:

- 新頁面 [`app/(main)/api-key-requests/page.tsx`](../../../frontend/src/app/(main)/api-key-requests/page.tsx):上方申請表單(6 欄)+ 下方歷程列表(分頁)。
- Sidebar [`Sidebar.tsx`](../../../frontend/src/components/layout/Sidebar.tsx) 新增 nav item「API Key 申請表單」,**不設 `adminOnly`**(admin/member 皆顯示)。
- RouteGuard [`RouteGuard.tsx`](../../../frontend/src/components/layout/RouteGuard.tsx) 的 `MEMBER_ALLOWED_PREFIXES` 加入 `"/api-key-requests"`(否則 member 進頁會被導回 /dashboard)。
- Endpoint [`endpoints.ts`](../../../frontend/src/lib/api/endpoints.ts) 新增 `apiKeyRequests`。
- Type [`types/api.ts`](../../../frontend/src/types/api.ts) 新增 `ApiKeyRequest` / `ApiKeyRequestCreate`。

**文件**:

- 本檔(propose)→ 確認後產出 `docs/Tasks/v1.9/tasks-v1.9.0.md`。
- 使用者使用說明(`/user-guide`)補一段「如何送出 API Key 申請」(member 可見頁面,屬對使用者公開的操作)。

### Out of Scope

- **審核流程(核准 / 駁回 / 退回補件)**:屬 **v1.9.1**。本版 `status` 欄固定為 `pending`,**不提供** approve/reject 端點與按鈕。
- **申請通過後自動發 Key / 建立部門 / 建立專案**:不做。本版只記錄申請意向,不觸發任何 Key/部門/專案的實際建立。
- **欄位綁定既有 `departments` / `projects`**:本版 6 欄皆為自由文字快照,**不**做下拉選既有部門 / 不做 FK 關聯(理由見 § 5.1)。
- **通知(Email / 站內信)**:送出後不發任何通知。
- **編輯 / 刪除既有申請單**:member 與 admin 皆不可改 / 刪已送出的申請(本版只 create + read)。
- **附件上傳**:申請表不帶檔案。

## 4. 流程概要

```
[member / admin] 後台 → sidebar「API Key 申請表單」→ /api-key-requests
  │
  ├─ 送出區:填 6 必填欄 → POST /api/v1/api-key-requests (UserDep)
  │     1. 驗登入(access_token cookie → Actor)
  │     2. Pydantic 驗 6 欄(全部必填;信箱驗 email、專案連結驗 GitHub/Replit)
  │     3. 寫入 api_key_requests(applicant_user_uid = Actor.user_uid,status="pending")
  │     4. write_audit(create_api_key_request)
  │     5. 回 ApiKeyRequestResponse → 前端 toast 成功 + reload 列表
  │
  └─ 歷程區:GET /api/v1/api-key-requests?page&size (UserDep)
        · admin  → repo.list()                          (全部)
        · member → repo.list(applicant_user_uid=Actor.user_uid)  (僅本人)
```

## 5. 設計重點

### 5.1 6 欄為何用自由文字快照,而非綁既有 `departments` / `projects`

- 系統雖已有 `departments`(含 code 如 `T000`)與 `projects` 表,但**申請當下,該部門 / 專案可能尚未在系統建立**——申請本身就是「請幫我開通」的前置動作。
- 若強制下拉選既有部門,會卡住「新部門 / 新專案」的申請情境;故 6 欄一律存為**送出當下的文字快照**,不做 FK。
- 後續 v1.9.1 審核時,管理者再人工對應 / 建立實際部門與專案即可。
- 唯一與登入身分關聯的是 `applicant_user_uid`(由後端從 Actor 取得,**前端不可指定**),用於「member 只看自己」的過濾與稽核。

### 5.2 單一 GET 端點、依角色決定範圍(不開兩個端點)

- `GET /api/v1/api-key-requests` 對 admin 與 member 是**同一個端點**;範圍由後端依 `Actor.is_admin` 決定:
  - admin:`repo.list(applicant_user_uid=None)` → 全部。
  - member:`repo.list(applicant_user_uid=actor.user_uid)` → 僅本人。
- **過濾在後端強制**,前端不傳 `applicant_user_uid`;避免 member 竄改參數越權查看他人申請(對齊「真正權限由後端把關」的既有設計)。

### 5.3 sidebar 入口對 member 可見(本版第一個 member 可進的功能頁)

- 既有 member 在 sidebar 只看得到「儀錶板」「使用者使用說明」;此頁 nav item **不設 `adminOnly`**,故 admin/member 皆顯示。
- 但 `RouteGuard` 預設「非 member 白名單路徑一律視為 admin 專用」,故**必須**同步把 `/api-key-requests` 加進 `MEMBER_ALLOWED_PREFIXES`,否則 member 點進去會被導回 /dashboard。此為本版易漏的一步。

### 5.4 status 欄先存在、但本版不流轉

- `status` 預設 `"pending"`,本版**永遠**是 `pending`(無審核動作)。
- 先放欄位是為 v1.9.1 審核流程預留,避免屆時再加欄 + migration;前端列表可先顯示「待審核」狀態 badge。

### 5.5 專案連結限定 GitHub / Replit

- `project_url` 為必填,且**必須**指向 GitHub 或 Replit;後端以 Pydantic 驗證器擋下其他網域,不通過回 `422`。
- 驗證規則(建議):host 屬於 `github.com`(含 `www.github.com`)或 `replit.com`(含 `*.replit.com`、`replit.dev`),且 scheme 為 `http`/`https`。實際允許網域清單於 `tasks` 定稿,避免過嚴擋掉合法子網域。
- 前端送出前先做同規則的即時提示(體驗),但**真正把關在後端**(前端可被繞過)。

## 6. 資料模型 `api_key_requests`

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| `pid` | BigInteger PK | 自增主鍵(排序用) |
| `request_uid` | UUID unique | 對外邏輯 PK(UUID v7) |
| `applicant_user_uid` | UUID | 申請人(後端由 Actor 注入,非前端指定) |
| `department_name` | String | 部門名稱(必填) |
| `department_code` | String | 部門代號,如 `T000`(必填) |
| `project_name` | String | 專案名稱(必填) |
| `project_url` | String | 專案連結(必填,須為 GitHub / Replit,見 § 5.5) |
| `owner_name` | String | 專案負責人名稱(必填) |
| `owner_email` | String | 專案負責人信箱(必填,email 格式) |
| `status` | String | 申請狀態,預設 `pending`(本版不流轉) |
| `created_at` / `updated_at` | DateTime(tz) | `TimestampMixin`,`server_default=now()` |
| `is_active` / `is_deleted` | Boolean | `TimestampMixin`(軟刪除慣例) |

- Table 命名 `api_key_requests`(複數 snake_case,對齊既有 `users` / `departments`)。
- migration 一併建 `updated_at` trigger(沿用既有 `set_updated_at()`)與必要 index(如 `applicant_user_uid` 供 member 過濾、`created_at` 供排序)。

## 7. API 端點

| Method | Path | 權限 | 說明 |
| --- | --- | --- | --- |
| `POST` | `/api/v1/api-key-requests` | `UserDep`(登入即可) | 送出申請;`applicant_user_uid` 由後端注入;回 `ApiKeyRequestResponse` |
| `GET` | `/api/v1/api-key-requests` | `UserDep`(登入即可) | 列表分頁;admin 全部 / member 僅本人(`page`/`size` query) |

- 回應統一走 `success_response(data=Page[...].model_dump(mode="json"))`(對齊既有 CRUD)。
- Swagger 於 `/api/docs` 自動反映(Pydantic schema 產生)。

## 8. 前端設計

- 頁面 `/api-key-requests`,沿用 `departments/page.tsx` 的版面慣例:`<PageTitle>` + `<Card>` + `<Table>` + 分頁。
- **送出區**:6 欄表單(`<Label>` + `<Input>`),信箱欄前端先做基本格式提示,送出失敗以 `showDialog(error, err.localizedDetail)` 呈現,成功以 toast + reload 列表。
- **歷程列表**:欄位含 部門名稱 / 代號 / 專案名稱 / 負責人 / 信箱 / 狀態(badge)/ 申請時間;分頁顯示「共 N 筆 · 第 X / Y 頁」。
- 列表資料即 `GET` 回傳;admin 與 member 共用同一頁,差異只在後端回的資料範圍(前端不需判 role 切換查詢)。
- API 呼叫走 `apiClient.get/post` + `API_ENDPOINTS.apiKeyRequests`;型別用 `types/api.ts` 新增的 `ApiKeyRequest`。

## 9. 權限與相容

- 對齊 [80-permission.md § 後台存取規則](../../Design-Base/80-permission.md):新增的是「member 也能進」的頁,需同步 sidebar(不設 adminOnly)+ RouteGuard(白名單)+ 後端端點(`UserDep` 而非 `AdminDep`)三處,缺一則行為不一致。
- 既有功能完全不受影響;本版為純新增(新表、新端點、新頁),無既有 schema / API 異動。
- 新增環境變數:無。

## 10. 設計取捨 / 決議

> **決議(2026-06-17,使用者確認)**:
> 1. **審核相關功能(核准 / 駁回 / 退回 / 通知)全部移至 v1.9.1**;v1.9.0 只做「送出表單 + 檢視」,`status` 恆為 `pending`。
> 2. **6 欄全部由使用者自行輸入,不依賴既有部門 / 專案等系統資料**(自由文字快照,不綁 FK)。
> 3. **member 僅 create + read**;不可編輯 / 刪除 / 撤回自己已送出的申請(撤回若需要,列入 v1.9.1)。
> 4. **重複送出限制:本版暫不限制(可重複送)**,使用者保留再思考;若後續決定要去重,於 v1.9.1 或後續版本補規則,本版資料表不因此改 schema。
>
> 其餘隨之確立(無異議):**單一 GET 端點依角色分流**(§ 5.2)、**送出後不發通知**(通知屬審核流程,隨 #1 移至 v1.9.1)。

### 待後續決定(不影響 v1.9.0 開工)

- **重複送出去重規則**(決議 #4):是否、以及以何鍵去重(例如同 `department_code` + `project_name` 不可同時存在 pending),待使用者確認後於後續版本實作。
