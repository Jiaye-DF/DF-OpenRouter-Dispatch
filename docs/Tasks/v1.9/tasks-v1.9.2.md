# Tasks v1.9.2

## 版本資訊

- 前置依賴:**v1.9.1**(申請單生命週期 + 規則路由 + AI 欄位驗證自動開通)已完成;`api_key_requests` 表含 `provisioned_secrets`、兩個開通終態(`agent_done` / `done`)、`/process` 與 `/claim-secrets` 端點。
- 本版本範圍:**開通完成 Email 通知**。開通成功(`agent_done` / `done`)後,以 **Microsoft Graph(app-only client credentials)** 寄信給專案負責人(`owner_email`),信中直接夾帶憑證明文;**best-effort**,失敗不回滾開通。信件 HTML 改採 **Jinja2 範本檔集中管理**。
- 母本 propose:[`propose-v1.9.2.md`](./propose-v1.9.2.md)(含設計推導與安全取捨)

> 本 Tasks 為**實作契約**;設計理由請參考母本。內容衝突以本檔為準。

## 本版固定決定(propose §11 三項待確認採建議值)

- **加 admin 重送端點** `POST /api-key-requests/{uid}/resend-notify`(供寄信失敗 / 使用者沒收到時補寄)。
- **沿用既有 SDK Key 無明文時照常寄**:信中 `X-SDK-Key` 欄顯示「請向管理員索取」,其餘憑證照寄。
- **token 先每次取**:client-credentials token 快取列為後續優化,本版不做。
- **不設 Application Access Policy**:改應用層固定只用 `M365_MAIL_SENDER` 寄信(取捨與殘留風險見 propose §3.1)。

## Definition of Done

### DB / Migration

- [ ] migration `0014_api_key_requests_notify`(`down_revision = "0013_api_key_requests_lifecycle"`),`ALTER TABLE api_key_requests` 新增 `notified_at` / `notify_error`(見「資料模型」)。
- [ ] `downgrade` 移除上述兩欄;無資料轉換。

### 後端 — Email 範本 / Render 層

- [ ] `app/templates/email/base.html`、`app/templates/email/provision.html`(**已於 propose 階段建立**);本版只需接上 render 層。
- [ ] `services/email_render.py`:`render_email(template_name, **ctx) -> str`,以 `jinja2.Environment` + `FileSystemLoader("app/templates/email")`、`autoescape=True` 載入;自動補基底 context `brand_name` / `platform_url`(取 `FRONTEND_URL`)/ `current_year`。Environment 以 `lru_cache` 單例化。
- [ ] provision.html 三個 Header 區塊須輸出 **`X-SDK-Key` / `X-User-Token` / `X-Project-Code`**(大小寫對齊 [`INTEGRATION.md`](../../INTEGRATION.md)),並直接帶入該收件人的憑證值(`sdk_key` 空 → 顯示「請向管理員索取」)。

### 後端 — Graph 寄信 service

- [ ] `services/email_graph.py`:
  - [ ] `async def send_provision_email(*, to_email, owner_name, project_name, secrets: dict) -> EmailResult`,回 `EmailResult(ok: bool, error: str | None)`。
  - [ ] 取 token:`POST https://login.microsoftonline.com/{M365_TENANT_ID}/oauth2/v2.0/token`(`grant_type=client_credentials`、`scope=https://graph.microsoft.com/.default`)。
  - [ ] 寄信:`POST https://graph.microsoft.com/v1.0/users/{M365_MAIL_SENDER}/sendMail`,body `message.body.contentType=HTML`、`content=render_email("provision.html", ...)`、`saveToSentItems=false`。
  - [ ] **降級**:`settings.m365_mail_enabled` 為 False(四個 env 任一為空)→ 直接回 `EmailResult(ok=False, error="m365_not_configured")`,呼叫端不視為錯誤。
  - [ ] 失敗(取 token 非 2xx / sendMail 非 2xx / 連線錯誤)→ `logger.warning`(**不含憑證明文**,僅記 request_uid / 收件網域 / 結果)+ 回 `ok=False`。
  - [ ] httpx 用法與逾時對齊既有 `clients/sso.py`(獨立 `AsyncClient` + `httpx.Timeout`)。

### 後端 — 觸發點接線

- [ ] `POST /api-key-requests` 自動開通成功(`agent_done`)、**`db.commit()` 之後**寄信。
- [ ] `POST /api-key-requests/{uid}/process` admin 人工開通成功(`done`)、`commit` 之後寄信。
- [ ] 寄送對象固定 `req.owner_email`;寄送後**另起一次 `update + commit`**寫回 `notified_at`(成功)或 `notify_error`(失敗),失敗不影響已開通結果。
- [ ] `POST /api-key-requests/{uid}/resend-notify`(admin):重讀該單 → 以 `provisioned_secrets`(若已清空則回 `409 secrets_already_claimed`)重寄 → 更新 `notified_at` / `notify_error`。

### 後端 — Schema

- [ ] `schemas/api_key_request.py`:`ApiKeyRequestResponse` / `ApiKeyRequestDetailResponse` 加 `notified_at: datetime | None`、`notify_error: str | None`;補欄位 `description` 與範例(見「API 文件範例」)。

### 後端 — 設定

- [ ] `core/config.py` 新增 `M365_TENANT_ID` / `M365_CLIENT_ID` / `M365_CLIENT_SECRET` / `M365_MAIL_SENDER`(預設皆 `""`)+ `m365_mail_enabled` property(四者皆非空才 True)。
- [ ] `.env.example` 已新增四鍵(**已完成**);`M365_CLIENT_SECRET` 標 `[COOLIFY]` 注入。
- [ ] `docker-compose-prod.yml` backend 已加四個 `M365_*`(**已完成**);dev 走 `env_file` 自動帶入。
- [ ] 新增依賴 `Jinja2`(`uv add jinja2`,寫入 `pyproject.toml`)。

### 前端

- [ ] `types/api.ts`:`ApiKeyRequest` / `ApiKeyRequestDetail` 加 `notifiedAt` / `notifyError`。
- [ ] `lib/api/endpoints.ts`:新增 `resendApiKeyRequestNotify`(admin)。
- [ ] `app/(main)/api-key-requests/page.tsx`:詳情顯示「通知狀態」(已通知時間 / 失敗原因);admin 於失敗時可「重送通知」(二次確認 + 錯誤處理)。

### 文件

- [ ] `/user-guide`:補「開通後會以 Email 寄送憑證給專案負責人」說明。
- [ ] `/admin-guide`:補「通知失敗時可重送」與 M365 設定前置(Azure App / `Mail.Send` / 寄件人)。
- [ ] Swagger(`/api/docs`):新端點 `resend-notify` 與回應新欄位的 Schema / 範例同步。

### 不做(v1.9.2 明確排除)

- SMTP 寄信路徑(只走 Graph);「通知 + 登入領取連結」式安全寄送(本版直接夾帶明文)。
- 其他狀態通知(人工待處理 / 取消 / 撤銷 不寄信)。
- 寄信重試佇列 / 排程補寄(僅手動 `resend-notify`);信件多語;token 快取。
- Application Access Policy(改應用層約束,見 propose §3.1)。

## 資料模型異動(`api_key_requests`,migration `0014`)

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| `notified_at` | DateTime(tz), null | Email 寄送成功時間 |
| `notify_error` | Text, null | 寄送失敗原因(**不含憑證**) |

## 觸發點與流程

| 觸發端點 | 終態 | 寄送來源 | 時機 |
| --- | --- | --- | --- |
| `POST /api-key-requests` | `agent_done` | `provisioned_secrets` | `commit` 後 |
| `POST /api-key-requests/{uid}/process` | `done` | `provisioned_secrets` | `commit` 後 |
| `POST /api-key-requests/{uid}/resend-notify` | (不變) | `provisioned_secrets` | admin 觸發 |

## 信件範本(Jinja2,`app/templates/email/`)

- 共用基底 `base.html`:table + inline style;block `heading` / `preheader` / `content` / `footer_extra` + 品牌頁尾。**今後所有信件 `extends base.html`**。
- `provision.html`(`extends base.html`):
  - 主旨(由 service 設定):`您的 API Key 已開通`。
  - context:`owner_name`、`project_name`、`project_code`、`sdk_key`、`user_token`。
  - 憑證區塊(等寬):`Project Code` / `SDK Key` / `User Token`。
  - **Header 使用說明區塊**,輸出三個 Header 並帶入實值:
    ```
    X-SDK-Key: <該收件人 sdk_key,空則「請向管理員索取」>
    X-User-Token: <該收件人 user_token>
    X-Project-Code: <該收件人 project_code>
    ```
  - 機密提醒:「此為機密憑證,請妥善保管」。

## API 文件範例

> 以下為 Swagger(`/api/docs`)同步維護的 Request / Response 範例。

### 1. 開通成功回應(`POST /api-key-requests`,`agent_done`)新增欄位

新增 `notified_at` / `notify_error` 兩欄(其餘沿用 v1.9.1)。寄信為 best-effort,故回應**可能在 `notified_at` 尚未寫回前先回傳**(同步寄信完成才回),實作以「寄信→更新→回應」順序,範例為已通知:

```jsonc
// Response 200
{
  "uid": "9b1f...c3",
  "status": "agent_done",
  "owner_name": "王小明",
  "owner_email": "ming.wang@df-recycle.com.tw",
  "project_name": "智慧客服",
  "provisioned_secrets": {
    "sdk_key": "ordsk_3f9a2b7c8d1e_9KqL...",
    "user_token": "eyJhbGciOiJI...",
    "project_code": "53299897503322112"
  },
  "notified_at": "2026-06-18T07:42:11+00:00",  // 寄送成功;失敗則為 null
  "notify_error": null                          // 失敗時為原因字串,如 "m365_sendmail_502"
}
```

### 2. 重送通知(`POST /api-key-requests/{uid}/resend-notify`)

| 項目 | 內容 |
| --- | --- |
| 權限 | admin |
| Request body | 無 |
| 行為 | 以該單現有 `provisioned_secrets` 重寄;更新 `notified_at` / `notify_error` |

```jsonc
// Request:無 body
// Response 200(重送成功)
{
  "uid": "9b1f...c3",
  "notified_at": "2026-06-18T08:05:30+00:00",
  "notify_error": null
}
```

```jsonc
// Response 409(憑證已被領取清空,無可寄內容)
{ "detail": "secrets_already_claimed" }
```

```jsonc
// Response 200(Graph 未設定,優雅略過 — 不視為錯誤)
{
  "uid": "9b1f...c3",
  "notified_at": null,
  "notify_error": "m365_not_configured"
}
```

### 3. Graph sendMail 呼叫範例(內部,對 Microsoft Graph)

```jsonc
// POST https://graph.microsoft.com/v1.0/users/{M365_MAIL_SENDER}/sendMail
{
  "message": {
    "subject": "您的 API Key 已開通",
    "body": { "contentType": "HTML", "content": "<!-- render_email('provision.html', ...) 產生的 HTML -->" },
    "toRecipients": [{ "emailAddress": { "address": "ming.wang@df-recycle.com.tw" } }]
  },
  "saveToSentItems": false
}
```

## 參數範例

### Graph 設定(env)

| env | 範例值 | 必填 | 說明 |
| --- | --- | --- | --- |
| `M365_TENANT_ID` | `619dfe56-7cb7-4ff8-b015-1bf1e7632258` | ✓ | Azure tenant id |
| `M365_CLIENT_ID` | `5ca28f24-d7a1-4fb9-a320-5abe3594b260` | ✓ | App(client) id |
| `M365_CLIENT_SECRET` | `(機密,Coolify 注入)` | ✓ | App client secret(`Mail.Send`) |
| `M365_MAIL_SENDER` | `noreply@df-recycle.com.tw` | ✓ | 寄件人信箱(Graph `/users/{sender}/sendMail`) |

> 四者任一為空 → `m365_mail_enabled = False` → 不寄信、不報錯、不阻斷開通。

### `render_email` 呼叫範例

```python
html = render_email(
    "provision.html",
    owner_name="王小明",
    project_name="智慧客服",
    project_code="53299897503322112",
    sdk_key="ordsk_3f9a2b7c8d1e_9KqL...",   # 沿用既有 Key 無明文時傳 ""
    user_token="eyJhbGciOiJI...",
)
# base context(brand_name / platform_url / current_year)由 render 層自動注入
```

### `send_provision_email` 回傳

```python
EmailResult(ok=True,  error=None)              # 寄送成功
EmailResult(ok=False, error="m365_not_configured")  # 降級(未設定)
EmailResult(ok=False, error="m365_sendmail_502")    # Graph 回非 2xx
EmailResult(ok=False, error="m365_token_error")     # 取 token 失敗
```

## 權限與稽核

- 寄信由系統觸發(開通流程內);`resend-notify` 限 admin。
- 稽核 action 新增 `notify_api_key_request`(記 result + 收件網域,**不記憑證**);`resend-notify` 另記 `resend_notify_api_key_request`。

## 交付物清單

- 後端新增:`services/email_graph.py`、`services/email_render.py`、`app/templates/email/{base,provision}.html`(**已建立**)、`alembic/versions/0014_api_key_requests_notify.py`。
- 後端修改:`core/config.py`、`schemas/api_key_request.py`、`api/v1/api_key_requests.py`(兩觸發點 + `resend-notify`)、`core/audit.py`(若 action 集中管理)。
- 前端修改:`types/api.ts`、`lib/api/endpoints.ts`、`app/(main)/api-key-requests/page.tsx`。
- 文件:`/user-guide`、`/admin-guide`、Swagger Schema。
- 環境變數:`M365_TENANT_ID` / `M365_CLIENT_ID` / `M365_CLIENT_SECRET` / `M365_MAIL_SENDER`(**已加**);新增依賴 `Jinja2`。

## 測試重點

- 降級:四個 env 缺任一 → 不寄、不報錯、開通仍成功、`notify_error="m365_not_configured"`。
- 寄信 service:mock httpx,token 成功/失敗、sendMail 2xx/非 2xx 各路徑;確認**憑證不入 log**、`saveToSentItems=false`。
- 範本:`render_email("provision.html", ...)` 含 `X-SDK-Key` / `X-User-Token` / `X-Project-Code` 三 Header 與實值;`sdk_key=""` → 顯示「請向管理員索取」且其餘照常;HTML 跳脫正確(autoescape)。
- 觸發:`agent_done` / `done` 後各寄一封給 `owner_email`;`notified_at` / `notify_error` 正確寫回;寄信失敗不影響終態與 `provisioned_secrets`。
- 重送:`resend-notify` admin 成功更新 `notified_at`;憑證已清空回 `409 secrets_already_claimed`;非 admin 回 `403`。
