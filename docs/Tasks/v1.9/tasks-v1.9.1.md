# Tasks v1.9.1

## 版本資訊

- 前置依賴:**v1.9.0**(`api_key_requests` 表、送出/檢視端點、前端 `/api-key-requests` 頁)已完成;既有部門/專案/使用者建立 service、SDK Key / User Token 服務、OpenRouter client(`chat_completion`)、`DEFAULT_OPENROUTER_KEY` 設定。
- 本版本範圍:申請單**完整生命週期 + 自動開通**。採**規則路由 + AI 欄位驗證**:存在性路由(確定性)決定 自動候選 / 人工 / 系統取消;自動候選由 **AI(`anthropic/claude-sonnet-4.6`,用 `DEFAULT_OPENROUTER_KEY`)** 驗證欄位,回**單一信心分數**,**`confidence >= 90` 才自動開通**(建立 專案→使用者→SDK Key→User Token),否則降級人工。門檻於 v1.9.x 由 95 調整為 **90**(評分 rubric 同步調整,避免因「無法驗證實際存在」而系統性扣分)。
- 對齊的 Design-Base 章節:
  - [80-permission.md § 後台存取規則](../../Design-Base/80-permission.md)
  - [50-openrouter.md § 4 呼叫流程](../../Design-Base/50-openrouter.md)
  - [90-task-spec.md § 4 / § 5](../../Design-Base/90-task-spec.md)
- 母本 propose:[`propose-v1.9.1.md`](./propose-v1.9.1.md)(含設計推導與決議)

> 本 Tasks 為**實作契約**;設計理由請參考母本。內容衝突以本檔為準。

## 本版固定決定(propose 兩項待確認採建議值)

- **不做 URL 真實連線檢查**:AI 僅判斷「看似有效/相符」,不實際 HTTP 連線。
- **同步處理**:送出請求內同步跑 路由 → AI 驗證 → 開通(數秒 loading);不引入背景佇列、無過渡狀態。

## Definition of Done

### DB / Migration

- [x] migration `0013_api_key_requests_lifecycle`(`down_revision = "0012_api_key_requests"`),`ALTER TABLE api_key_requests` 新增欄位(見「資料模型」)。
- [x] 既有資料 `status='pending'` → 一律 `UPDATE` 為 `'manual_pending'`。
- [x] `downgrade` 移除新增欄位(並把 `manual_pending` 還原為 `pending`,其餘狀態略過)。

### 後端 — Schema / Repository

- [x] `schemas/api_key_request.py` 擴充:`ApiKeyRequestResponse` 加新欄位;新增 `CancelRequest`(`reason` 必填)、`ApiKeyRequestDetailResponse`(含 `agent_decision` / 一次性憑證)。
- [x] `repositories/user.py`:新增 `get_by_email(email) -> list[User]`(email 無唯一約束,回 list 以判斷 0/1/多筆)。
- [x] `repositories/project.py`:新增 `get_active_by_department_and_name(department_uid, name) -> Project | None`。
- [x] `repositories/sdk_api_key.py`(或既有):新增 `get_active_by_department(department_uid) -> SdkApiKey | None`(取可沿用的部門 Key)。
- [x] `repositories/api_key_request.py`:新增 `update_fields()`(狀態流轉用)。

### 後端 — 規則路由 / AI / 開通

- [x] `services/api_key_request_router.py`:`route(db, req) -> RouteResult`,實作 § 規則路由 的決策樹 + 確定性硬規則。
- [x] `services/api_key_request_agent.py`:`validate_fields(req, matched_department) -> AgentDecision`,以 `DEFAULT_OPENROUTER_KEY` 呼 `chat_completion`,模型 `settings.API_KEY_AGENT_MODEL`,要求 JSON `{confidence:int, reason:str}`;呼叫失敗/逾時/JSON 不可解析 → 回 `confidence=0` + error。
- [x] `services/api_key_request_provision.py`:`provision(db, req, route) -> ProvisionResult`,單一 transaction 內 沿用部門 → 建專案 → 沿用/建使用者 → 沿用/建 SDK Key → 發 User Token;失敗 rollback。
- [x] 開通各步 `write_audit`(`create_project`/`create_user`/`create_sdk_key`)+ 一筆 `auto_provision_api_key_request`。

### 後端 — 端點

- [x] `POST /api-key-requests`(擴充):送出後同步 `route → (AI) → provision`;終態與一次性憑證寫回並於回應帶回。
- [x] `POST /api-key-requests/{uid}/cancel`(本人):限 `manual_pending`;寫 `cancel_reason`、`cancel_source='user'`、`status='cancelled'`。
- [x] `POST /api-key-requests/{uid}/revoke`(本人/admin):限 `manual_pending`;否則 `409`。
- [x] `POST /api-key-requests/{uid}/process`(admin):確定性開通 → `done`、`handled_by_user_uid`。
- [x] `GET /api-key-requests/{uid}`(本人/admin):詳情(本人僅能看自己)。
- [x] `POST /api-key-requests/{uid}/claim-secrets`(本人):回 `provisioned_secrets` 後以 `NULL` 覆寫。
- [x] 所有寫入動作寫對應 `write_audit`。

### 後端 — 設定

- [x] `core/config.py` 新增 `API_KEY_AGENT_MODEL: str = "anthropic/claude-sonnet-4.6"`。
- [x] `.env.example` 新增 `API_KEY_AGENT_MODEL`(並確認 `DEFAULT_OPENROUTER_KEY` 已列)。
- [x] `DEFAULT_OPENROUTER_KEY` 未設/為空時:自動候選一律降級 `manual_pending`(不報錯)。

### 前端

- [x] `types/api.ts`:`ApiKeyRequest` 加新欄位;新增 `ApiKeyRequestDetail`、`ProvisionedSecrets`、`AgentDecision`。
- [x] `lib/api/endpoints.ts`:新增 `apiKeyRequestById` / `cancelApiKeyRequest` / `revokeApiKeyRequest` / `processApiKeyRequest` / `claimApiKeyRequestSecrets`。
- [x] `app/(main)/api-key-requests/page.tsx`:
  - [x] 列表狀態 badge(待人工處理=warning、Agent 已處理/已處理=success、已撤銷/已取消=secondary)。
  - [x] 送出採 loading(同步含 AI 呼叫);成功若 `agent_done` → 彈一次性憑證視窗。
  - [x] 列操作:本人可 取消(填原因)/ 撤銷(限 `manual_pending`,二次確認);詳情可領取一次性憑證。
  - [x] admin:`manual_pending` 可開「人工處理」(顯示 `agent_decision` 信心分數/理由 → 一鍵開通)。
- [x] 取消 / 撤銷 / 領取憑證的 Dialog 與錯誤處理(`showDialog` + `err.localizedDetail`)。

### 文件

- [x] `/user-guide`:補「申請後的狀態與領取憑證」說明(申請人視角)。
- [x] `/admin-guide`:補「待人工處理的審核與新部門開通(含 OpenRouter 後台建 Key)」。

### 不做(v1.9.1 明確排除)

- AI 直接 tool-calling 執行建立;AI 介入路由 / 模糊比對部門。
- 背景 job queue / 重試;URL 真實連線檢查;通知(Email / 站內信)。
- 新部門自動開通(一律人工);撤銷後連動停用資源(已處理禁止撤銷,故無此情境)。

## 狀態模型

| `status` | 顯示 | 性質 | 進入條件 |
| --- | --- | --- | --- |
| `manual_pending` | 待人工處理 | 待辦 | 新部門 / AI 信心<90 / AI 失敗 / 舊專案下新使用者 / 硬規則命中 |
| `agent_done` | Agent 已處理 | 終態成功 | AI 信心≥90 + 自動開通成功 |
| `done` | 已處理 | 終態成功 | admin 人工處理完成 |
| `revoked` | 已撤銷 | 終態取消 | `manual_pending` 時本人/admin 撤銷 |
| `cancelled` | 已取消 | 終態取消 | 本人取消(附原因)或系統判定重複 |

- **撤銷限制**:`agent_done` / `done` → 撤銷回 `409`;撤銷僅限 `manual_pending`。

## 規則路由(確定性,落點 `api_key_request_router.py`)

存在性判斷:部門 `get_by_code`;專案 `get_active_by_department_and_name`;使用者 `list_by_email`(命中唯一一筆才算「舊」)。

> **系統管理員排除**(v1.9.x):`list_by_email` 於**查詢層**即排除 `account='admin'`,故 admin 永遠不會出現在比對結果——不會被當成既有負責人沿用,owner 自然走「新建使用者」流程(新建者帶部門,可正常發 User Token)。

```
if 部門不存在:                 → manual_pending（reason: 新部門需後台建 Key）
elif 部門名稱與既有不符:       → manual_pending（硬規則:防代號誤填）
elif 專案不存在(同部門同名):  → AI 驗證 → confidence>=90 ? 自動開通→agent_done : manual_pending
elif 使用者 email 命中多筆:    → manual_pending（硬規則:歧義）
elif 使用者不存在(新使用者):  → manual_pending
else:                          → cancelled（cancel_source='system', reason='過去已存在相同 Key 資料'）
```

> 注意順序:「部門名稱不符」「email 多筆」屬硬規則,先於 AI / 其他分支擋下。
> (使用者比對所稱「命中 / 不存在」均指**排除 admin 後**的結果。)

## AI 欄位驗證(落點 `api_key_request_agent.py`)

- 觸發:僅「舊部門 + 新專案」分支。
- 呼叫:`get_openrouter_client().chat_completion(payload, api_key=settings.DEFAULT_OPENROUTER_KEY)`,`payload.model = settings.API_KEY_AGENT_MODEL`,要求 JSON 結構化輸出。
- 輸入:申請 6 欄 + 命中部門摘要(name/code)。
- 輸出:`{ "confidence": 0-100, "reason": "簡短中文" }`;存入 `agent_decision`。
- 門檻:`confidence >= 90` → 開通;否則 `manual_pending`(v1.9.x 由 95 調整為 90)。
- 失敗(逾時 / 非 2xx / JSON 不可解析 / 金鑰未設):`confidence=0`、`error_message` 記錄 → `manual_pending`。
- **不**寫 usage_logs、**不**過白名單、**不**需 SDK 身分。

## 自動開通(落點 `api_key_request_provision.py`,單一 transaction)

| 步驟 | 動作 | 沿用 / 新建 |
| --- | --- | --- |
| 1 部門 | 沿用既有(by `department_code`) | 必沿用 |
| 2 專案 | 建立 `project_name`(`code` 走 Snowflake)綁部門 | 新建 |
| 3 使用者 | email 命中 → 沿用;否則建立(`role=user`/`username=owner_name`/綁部門) | 視情況 |
| 4 SDK Key | 部門有可用 Key → 沿用(取 `key_values`);否則新建 | 視情況 |
| 5 User Token | 為使用者發 token(重發撤舊) | — |

- 寫入 `created_project_uid` / `created_user_uid` / `created_sdk_key_uid` / `matched_department_uid` / `processed_at`。
- `provisioned_secrets` = `{ sdk_key, user_token, project_code }`(沿用既有 Key 但無留存明文 → `sdk_key` 留 null + 提示)。
- 任一步失敗 → rollback → `manual_pending` + `error_message`。

## 資料模型異動(`api_key_requests`,migration `0013`)

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| `cancel_reason` | Text, null | 取消原因 |
| `cancel_source` | String(8), null | `user` / `system` |
| `handled_by_user_uid` | UUID, null | 人工處理 admin |
| `agent_decision` | JSONB, null | `{confidence, reason}` |
| `error_message` | Text, null | AI / 開通失敗原因 |
| `created_project_uid` | UUID, null | 建立的專案 |
| `created_user_uid` | UUID, null | 建立/沿用使用者 |
| `created_sdk_key_uid` | UUID, null | 建立/沿用 SDK Key |
| `matched_department_uid` | UUID, null | 沿用的既有部門 |
| `provisioned_secrets` | JSONB, null | 一次性憑證,領取後清空 |
| `processed_at` | DateTime(tz), null | 進入終態時間 |

> `status` 沿用既有 String(16) 欄位,僅擴充允許值;不改型別。

## API 端點

| Method | Path | 權限 | Request | 行為 |
| --- | --- | --- | --- | --- |
| `POST` | `/api-key-requests` | 本人 | 6 欄(同 v1.9.0) | 同步 route→AI→provision;回 detail(agent_done 帶 secrets) |
| `POST` | `/api-key-requests/{uid}/cancel` | 本人 | `{reason}` | 限 `manual_pending` → `cancelled` |
| `POST` | `/api-key-requests/{uid}/revoke` | 本人/admin | — | 限 `manual_pending`;否則 `409` |
| `POST` | `/api-key-requests/{uid}/process` | admin | — | 確定性開通 → `done` |
| `GET` | `/api-key-requests/{uid}` | 本人/admin | — | 詳情(本人僅自己) |
| `POST` | `/api-key-requests/{uid}/claim-secrets` | 本人 | — | 回 secrets 後清空 |

## 錯誤處理對照

| 情境 | HTTP / 行為 |
| --- | --- |
| 取消缺 `reason` | 422 |
| 取消/撤銷非本人(且非 admin) | 403 |
| 撤銷已處理(`agent_done`/`done`) | 409 |
| cancel 於非 `manual_pending` 狀態 | 409 |
| 非本人查他人詳情 | 403 |
| AI 呼叫失敗 / 金鑰未設 | 不報錯,降級 `manual_pending`(記 `error_message`) |
| 自動開通中途失敗 | rollback → `manual_pending` |

## 權限與稽核

- 取消 / 領取憑證:僅本人。撤銷:本人或 admin(限 `manual_pending`)。人工處理:僅 admin。
- 列表 `GET` 範圍不變(admin 全部 / member 本人);詳情亦受本人限制。
- 稽核 action 新增:`cancel_api_key_request` / `revoke_api_key_request` / `process_api_key_request` / `auto_provision_api_key_request`;子資源沿用既有 `create_*`。

## 交付物清單

- 後端新增:`services/api_key_request_router.py`、`services/api_key_request_agent.py`、`services/api_key_request_provision.py`、`alembic/versions/0013_api_key_requests_lifecycle.py`。
- 後端修改:`schemas/api_key_request.py`、`repositories/{user,project,sdk_api_key,api_key_request}.py`、`api/v1/api_key_requests.py`、`core/config.py`、`.env.example`。
- 前端修改:`types/api.ts`、`lib/api/endpoints.ts`、`app/(main)/api-key-requests/page.tsx`(及必要的 Dialog 元件)。
- 文件:`/user-guide`、`/admin-guide`。
- 環境變數:新增 `API_KEY_AGENT_MODEL`。

## 測試重點

- 路由:5 種組合各自落到正確終態(新部門→人工、舊+新專案→AI、舊+舊+新使用者→人工、舊+舊+舊→系統取消)。
- 硬規則:部門名稱不符 / email 多筆 → 人工(不呼叫 AI)。
- AI 門檻:mock `confidence=90/89` 分別 → 自動 / 人工;AI 失敗 / 金鑰空 → 人工。
- 開通:agent_done 後三資源正確建立/沿用,`provisioned_secrets` 內容正確;中途失敗 rollback。
- 狀態流轉:cancel 限 `manual_pending`、revoke 已處理回 409;claim-secrets 後欄位清空。
- 權限:非本人 cancel/claim/詳情 → 403;member 列表只見自己。
