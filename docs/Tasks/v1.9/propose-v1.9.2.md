[//]: # (此檔為 v1.9.2 任務提案,實作前先由使用者確認範圍與設計取捨。)

# Propose v1.9.2 · 開通完成 Email 通知(Microsoft Graph 寄信給專案負責人)

> 此為 **proposal**(規劃草案),確認後即轉為正式 `tasks-v1.9.2.md`。
>
> 對應母本:[v1.9.1 申請單生命週期 + 規則路由 + AI 欄位驗證自動開通](./propose-v1.9.1.md)。

## 1. 目標

補上 v1.9.1 刻意延後的「通知」缺口:申請單**開通成功後,自動寄 Email 給專案負責人(`owner_email`)**,讓使用者不必回平台 UI 也能直接取得並使用憑證。

採 **Microsoft Graph API(app-only client credentials)** 寄信,對齊公司 Microsoft / Outlook + DF-SSO(Azure)環境。

> **使用者已確認的方向(2026-06-17)**:
> 1. **寄信管道**:Microsoft Graph API(非 SMTP)。
> 2. **收件人**:申請單的 **`owner_email`(專案負責人)**。
> 3. **信件內容**:**直接夾帶完整憑證明文**(SDK Key / User Token / Project Code)。
> 4. 寄信為 **best-effort**:失敗不回滾開通,UI 一次性領取仍保留為備援。

## 2. 動機

- v1.9.1 開通後憑證僅存於 `provisioned_secrets`,須由**登入的申請人**回 UI 一次性領取。
- 但 `owner_email`(真正要用 Key 的人)**未必是申請人**(代他人申請的情境),導致負責人收不到憑證、無法使用 —— 這是目前最會卡住落地的缺口。
- 公司為 Microsoft / Outlook 環境且已接 DF-SSO(Azure AD),以 Graph API 寄信最為相容,可由一個具 `Mail.Send` 應用程式權限的 Azure App 後端直送。

## 3. 安全取捨(已記錄使用者決定)

- 本版**依使用者決定,於信件正文直接夾帶 SDK Key / User Token 明文**。
- 已知風險(明確記錄,供日後檢視):Email 明文憑證會**長期留存於收件匣 / 封存 / 備份**,等同延長憑證可外洩的時間窗,且與「金鑰只顯示一次」的原始設計相左。
- 對應的**最小防護措施**(本版納入):
  - 憑證明文**絕不寫入任何 log**(log 僅記 request_uid / 收件網域 / 寄送結果)。
  - Graph `sendMail` 帶 `saveToSentItems=false`,避免於寄件匣再留一份。
  - UI 一次性領取(`/claim-secrets`)仍保留為備援,不因 Email 而移除。
- **後續可選強化**(本版不做,留待後續):改為「通知 + 登入領取連結」、或寄送後設定憑證短時效 TTL。

### 3.1 寄件人權限取捨(已記錄使用者決定)

- `Mail.Send`(Application 權限)預設能以**租戶內任一信箱**名義寄信;標準收斂作法是於 Exchange 端設 **Application Access Policy**,限制此 App 只能用指定信箱寄。
- **本版依使用者決定不設 Application Access Policy**(設定成本高),改於**應用層自我約束**:程式固定只用 `M365_MAIL_SENDER` 寄信,不接受呼叫端指定寄件人。
- **殘留風險(明確記錄)**:應用層限制只擋「程式寄錯人」,**擋不住 `M365_CLIENT_SECRET` 外洩後被冒用**——攻擊者持 secret 可直接打 Graph 冒充租戶內任何信箱寄信,繞過應用層限制。
- **對應補償控制(本版納入 / 維運要求)**:
  - `M365_CLIENT_SECRET` **僅 Coolify 注入**,不進 git、不進 log。
  - 寄件人建議用**專用共用信箱**(無互動登入),縮小爆炸半徑。
  - secret **定期輪替**(建議於 Azure 設到期)。
  - 該 App **僅授 `Mail.Send`**,不多授其他 Graph 權限(最小權限)。

## 4. 範圍

### In Scope

- **Graph 寄信 service**(§ 6):新增 `services/email_graph.py`,以 client credentials 取 token → 呼叫 Graph `sendMail`。
- **觸發點接線**(§ 7):於兩個「開通成功」終態後寄信:
  1. `POST /api-key-requests` 自動開通成功(`agent_done`)。
  2. `POST /api-key-requests/{uid}/process` admin 人工開通成功(`done`)。
- **優雅降級**:Graph 設定未齊(缺任一 env)→ 不寄信、不報錯、不阻斷開通(比照 `DEFAULT_OPENROUTER_KEY`)。
- **寄送結果留痕**(§ 8):`api_key_requests` 加 `notified_at` / `notify_error`,migration `0014`。
- **設定**(§ 9):新增 Graph 四個 env + `.env.example` 同步。
- **Email 範本(檔案化管理)**(§ 10):導入 Jinja2,於 `app/templates/email/` 建立共用 `base.html` + 本版 `provision.html`;新增 render 層統一注入品牌 context。**今後所有系統信件一律 extends `base.html`**。
- **文件**:`/user-guide`、`/admin-guide` 補「開通後會以 Email 通知負責人」說明。

### Out of Scope

- SMTP 寄信路徑(本版只走 Graph)。
- 「通知 + 登入領取連結」式安全寄送(本版直接夾帶明文,連結式留待後續)。
- 其他狀態的通知(人工待處理 / 取消 / 撤銷 不寄信)。
- 寄信重試佇列 / 排程補寄(本版同步 best-effort,失敗僅留 `notify_error`,可由 admin 重送 —— 重送端點列為 §11 待確認)。
- 信件多語(本版單一繁中範本;`base.html` 已預留可擴充,多語留待後續)。

## 5. 前置依賴(外部,需 IT / 使用者提供)

寄信前必須備妥 Azure 端資源(否則本版功能優雅略過):

- 一個 **Azure App 註冊**,授予 **`Mail.Send`(Application 權限)**並完成 **admin consent**。
  - 可新建專用 App,亦可沿用既有但須另授 `Mail.Send`(DF-SSO 登入用的 App 通常未授,建議獨立)。
- 一個可寄信的**寄件人信箱**(具授權的使用者信箱或共用信箱),作為 `GRAPH_MAIL_SENDER`。
- 取得:`tenant_id`、`client_id`、`client_secret`、寄件人位址。

## 6. Graph 寄信 service(`services/email_graph.py`)

- **取 token(client credentials)**:
  `POST https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token`
  body:`grant_type=client_credentials`、`scope=https://graph.microsoft.com/.default`、`client_id`、`client_secret`。
  - token 可於 process 內快取至 `expires_in` 前(減少請求);本版可先每次取,快取列為優化選項。
- **寄信**:
  `POST https://graph.microsoft.com/v1.0/users/{GRAPH_MAIL_SENDER}/sendMail`
  body:
  ```json
  {
    "message": {
      "subject": "Agent 代發: OpenRouter API Key 平台申請已開通",
      "body": { "contentType": "HTML", "content": "<...憑證與使用說明...>" },
      "toRecipients": [{ "emailAddress": { "address": "<owner_email>" } }]
    },
    "saveToSentItems": false
  }
  ```
- 介面:`async def send_provision_email(*, to_email, owner_name, project_name, secrets: dict) -> EmailResult`,
  回 `EmailResult(ok: bool, error: str | None)`。
- **信件 HTML 由 render 層產生**(§ 10):service 不自行拼字串,改呼叫 `render_email("provision.html", **ctx)` 取得 HTML 後丟給 Graph `sendMail`。
- **降級**:`settings.graph_mail_enabled`(四個 env 皆有值)為 False → 直接回 `EmailResult(ok=False, error="graph_not_configured")`,呼叫端不視為錯誤。
- 失敗(取 token 非 2xx / sendMail 非 2xx / 連線錯誤)→ `logger.warning`(**不含憑證明文**)+ 回 `ok=False`。
- httpx 用法與逾時對齊既有 `clients/sso.py`(獨立 `AsyncClient` + `httpx.Timeout`)。

## 7. 觸發點與流程

開通成功並 **`db.commit()` 之後**才寄信(避免先寄信後回滾造成憑證已外流但 DB 未建立):

| 觸發端點 | 終態 | 寄送來源 |
| --- | --- | --- |
| `POST /api-key-requests` | `agent_done` | provision 回傳的 `provisioned_secrets` |
| `POST /api-key-requests/{uid}/process` | `done` | provision 回傳的 `provisioned_secrets` |

- 寄送對象固定為 `req.owner_email`。
- 寄送後寫回 `notified_at`(成功)或 `notify_error`(失敗);此寫回**另起一次 `update + commit`**,失敗不影響已開通結果。
- **沿用既有 SDK Key 但無留存明文**(`sdk_key=None`)時:信中該欄顯示「請向管理員索取」,仍照常寄出其餘憑證。

## 8. 資料模型異動(`api_key_requests`,migration `0014`)

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| `notified_at` | DateTime(tz), null | Email 寄送成功時間 |
| `notify_error` | Text, null | 寄送失敗原因(不含憑證) |

> `downgrade` 移除上述兩欄。無資料轉換需求。

## 9. 設定(`core/config.py` + `.env.example`)

> **命名以實際 `.env` 為準**:採 `M365_*` 前綴(非原草案的 `GRAPH_*`),對齊使用者已寫入的本機 `.env`。

| env | 預設 | 說明 |
| --- | --- | --- |
| `M365_TENANT_ID` | `""` | Azure tenant id |
| `M365_CLIENT_ID` | `""` | App(client) id |
| `M365_CLIENT_SECRET` | `""` | App client secret([機密],由 Coolify 注入,禁 commit) |
| `M365_MAIL_SENDER` | `""` | 寄件人信箱位址 — **目前 `.env` 尚未填,需補** |

- `Settings.m365_mail_enabled` property:四者皆非空才為 True。
- **待填(非缺鍵)**:Graph `sendMail` 端點為 `/users/{sender}/sendMail`,**寄件人信箱(`M365_MAIL_SENDER`)為必要**。四個鍵已就位於 `.env` / `.env.example` / prod compose,但 `M365_MAIL_SENDER` **目前留空**;確定共用信箱後於 `.env`(本機)與 Coolify(prod)填入即可啟用寄信(留空則優雅略過)。
- `.env.example` 於既有區段已新增四鍵(secret 標 `[COOLIFY]` 注入)。
- `docker-compose-prod.yml` backend 已加入四個 `M365_*` 變數(值由 Coolify 注入);`docker-compose.dev.yml` 因 `env_file: .env` 自動帶入,無需改動。

## 10. 信件範本(Jinja2 檔案化管理)

**方針**:信件 HTML 不再內嵌於 service,改以 **Jinja2 範本檔**集中於 `app/templates/email/`,並以共用基底版型統一所有系統信件外觀。**今後新增任何信件,一律新建 `xxx.html` 並 `{% extends "base.html" %}`**。

### 檔案結構

| 檔案 | 角色 |
| --- | --- |
| `app/templates/email/base.html` | 共用基底版型(table 排版 + inline style,email client 相容);提供 `heading` / `preheader` / `content` / `footer_extra` block 與品牌頁尾。 |
| `app/templates/email/provision.html` | 本版開通通知信,`extends base.html`,填入憑證與使用說明。 |

> 兩檔已先行建立(本次提案附帶交付),tasks 化時只需接上 render 層與 service。

### Render 層(新增,統一注入品牌 context)

- 新增 `app/services/email_render.py`(或 `core/email_template.py`):以 `jinja2.Environment` + `FileSystemLoader("app/templates/email")` 載入,`autoescape=True`(防憑證內含特殊字元破版/注入)。
- `render_email(template_name, **ctx) -> str`:自動補上基底 context — `brand_name`(暫用 `APP_NAME` 或固定「DF OpenRouter 平台」)、`platform_url`(取 `FRONTEND_URL`,可為空)、`current_year`。
- Environment 建議以 `lru_cache` 單例化,避免每次寄信重建。

### provision.html 內容要點

- 主旨:`Agent 代發: OpenRouter API Key 平台申請已開通`(由 service 設定,非範本)。
- context:`owner_name`、`project_name`、`project_code`、`sdk_key`、`user_token`。
- 呈現:**Project Code / SDK Key / User Token**(明文,等寬區塊)、三個 Header(`X-Sdk-Key` / `X-User-Token` / `X-Project-Code`)帶入 SDK 的最小說明、平台連結、「此為機密憑證,請妥善保管」提醒。
- `sdk_key` 為空(沿用既有 Key 無明文)→ 該欄顯示「請向管理員索取」,其餘照常。

### 新增依賴

- `Jinja2`(加入 backend `pyproject.toml` / requirements)。

## 11. 權限與稽核 / 待確認

### 權限與稽核

- 寄信由系統觸發(非使用者動作);稽核 action 新增 `notify_api_key_request`(記 result + 收件網域,不記憑證)。

### 待使用者確認

1. **是否需要 admin「重送通知」端點**(`POST /{uid}/resend-notify`):供寄信失敗或使用者沒收到時補寄。
   (建議:本版加一個 admin-only 重送端點,成本低、實用。)
2. **沿用既有 SDK Key 無明文** 時,信中是否仍寄(只缺 sdk_key)還是整封改走人工?(建議:照常寄,缺的欄位提示向 admin 索取。)
3. **token 快取**:是否本版即做 client-credentials token 快取(減少 login 請求)?(建議:可後續優化,先每次取。)

## 12. 交付物清單(轉 tasks 後)

- 後端新增:`services/email_graph.py`、`services/email_render.py`(Jinja2 render 層)、`templates/email/base.html` + `templates/email/provision.html`(**本次提案已先建立**)、`alembic/versions/0014_api_key_requests_notify.py`。
- 新增依賴:`Jinja2`(`pyproject.toml`)。
- 後端修改:`core/config.py`、`.env.example`、`models/api_key_request.py`、`schemas/api_key_request.py`(詳情回 `notified_at`/`notify_error`)、`repositories/api_key_request.py`(若需)、`api/v1/api_key_requests.py`(兩個觸發點 + 可選重送端點)。
- 前端修改:`/user-guide`、`/admin-guide`(說明開通後 Email 通知);列表/詳情可選顯示「已通知」狀態。
- 環境變數:新增 `GRAPH_TENANT_ID` / `GRAPH_CLIENT_ID` / `GRAPH_CLIENT_SECRET` / `GRAPH_MAIL_SENDER`。

## 13. 測試重點(轉 tasks 後)

- 降級:Graph 設定缺任一 → 不寄、不報錯、開通仍成功。
- 寄信 service:mock httpx,token 取得成功/失敗、sendMail 2xx/非 2xx 各路徑;確認**憑證不入 log**。
- 觸發:`agent_done` / `done` 後各寄一封給 `owner_email`;`notified_at` / `notify_error` 正確寫回。
- 寄信失敗不影響已開通的終態與 `provisioned_secrets`。
