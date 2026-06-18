# DF-OpenRouter-Dispatch — 交接文件

> OpenRouter API 中控派發管理平台。集中管理使用者透過 OpenRouter（及內部 LLM）呼叫模型時的**金鑰、路由、白名單、用量稽核**。前端為管理 UI，後端為呼叫代理層；OpenRouter / SDK 金鑰僅存於後端（AES-256-GCM 加密）。
>
> 本檔為**交接用**：環境、啟動、部署、分支流程、維運須知一次看完。功能設計細節見 [docs/](docs/)。
>
> 目前版本進度：**v1.9.2 已上線**（已併入 `main` / `development`）。後續小微調走 `dev-v1.10`。

---

## 環境與網址

| 環境 | 前端 | 後端 / API（Swagger：`/api/docs`） |
| --- | --- | --- |
| 本機 dev | http://localhost:3300 | http://localhost:8800 |
| 測試 stage | https://df-it-openrouter-dispatch-stage.it.zerozero.tw | https://df-it-openrouter-dispatch-stage-api.it.zerozero.tw |
| 正式 prod | https://df-it-openrouter-dispatch.it.zerozero.tw | https://df-it-openrouter-dispatch-api.it.zerozero.tw |

> 開通通知信內的連結固定指向**正式站**（見 `services/email_render.py`）。

---

## 1. 技術棧

| 層 | 技術 |
| --- | --- |
| 前端 | Next.js（App Router）+ TypeScript，npm |
| 後端 | FastAPI（Python **3.14**，套件管理用 **uv**）、SQLAlchemy async + asyncpg、Alembic、httpx、pydantic-settings、Jinja2（Email 範本） |
| 資料庫 | PostgreSQL 17 |
| 認證 | JWT（HttpOnly cookie）+ **DF-SSO**（Azure AD） |
| 寄信 | Microsoft Graph（app-only，M365） |
| 日誌 | Seq（`SEQ_INGESTION_URL` 留空則只走 console） |
| 部署 | Coolify + `docker-compose-prod.yml` |
| 品質 | ruff（lint）、pytest（測試） |

---

## 2. 目錄結構

```
backend/                    FastAPI 後端
  app/
    api/v1/                 路由（auth/users/departments/projects/sdk_keys/
                            openrouter_keys/internal_keys/models/model_tiers/
                            allowed_models/usage_logs/stats/api_key_requests/
                            model_chat〔代理〕/user_tokens/health）
    clients/                外部呼叫（openrouter / sso / internal）
    core/                   config / database / security / crypto / audit / deps / logging
    models/ repositories/ schemas/ services/
    templates/email/        Jinja2 Email 範本（base.html + provision.html）
  alembic/versions/         migration 0001–0014
  tests/                    pytest（services / core）
frontend/                   Next.js（src/app/(main)/<各功能頁>）
docs/
  Design-Base/              不隨版本變動的基礎設計
  Tasks/v1.x/               各版 propose / tasks（實作契約）
docker-compose.dev.yml      本機開發
docker-compose-prod.yml     Coolify 部署（值由 Coolify 注入）
CLAUDE.md                   AI 協作規範
```

---

## 3. 環境設定（`.env`）

1. 從 [.env.example](.env.example) 複製為 `.env`，依各區段標示填值：
   - `[BOTH]` dev/test/prod 都要、`[LOCAL]` 僅本機、`[REMOTE]` 僅 test/prod、`[COOLIFY]` 正式由 Coolify 注入且**禁 commit**。
2. **必填祕密**：`JWT_SECRET`、`ENCRYPTION_KEY`（base64 32 bytes）、`INITIAL_ADMIN_*`、`DATABASE_URL` / `POSTGRES_*`。
3. **DF-SSO**（要 SSO 登入才需）：`SSO_URL` / `SSO_APP_ID` / `SSO_APP_SECRET` / `BACKEND_URL` / `FRONTEND_URL`。
4. **AI 自動開通**：`DEFAULT_OPENROUTER_KEY`（須為**有效** OpenRouter key，否則申請單 AI 驗證一律降級人工）。
5. **M365 寄信**（開通通知信）：`M365_TENANT_ID` / `M365_CLIENT_ID` / `M365_CLIENT_SECRET` / `M365_MAIL_SENDER`，**四者皆有值才啟用**，缺則優雅略過（不報錯、不阻斷開通）。

> ⚠️ **改 `.env` 後一定要重啟後端才生效**：settings 於程序啟動時讀入且 `get_settings()` 有 lru_cache，熱改檔案不會生效。

---

## 4. 本機開發

```bash
docker compose -f docker-compose.dev.yml --env-file .env up --build
```

對外 port（host → container）：

| 服務 | 本機網址 |
| --- | --- |
| Frontend | http://localhost:3300 |
| Backend API | http://localhost:8800 |
| **Swagger** | http://localhost:8800/api/docs |
| PostgreSQL | localhost:5533 |

首次啟動 Alembic 會自動 `upgrade head`，Backend Seed 建立初始 admin（帳號 `INITIAL_ADMIN_ACCOUNT` / 密碼 `INITIAL_ADMIN_PASSWORD`，掛於 `SYSTEM` 部門）。

不走 docker 時：backend `uv run uvicorn app.main:app --reload`；frontend `npm run dev`（見各自 `package.json`）。

---

## 5. 正式部署（Coolify）

- 以 [docker-compose-prod.yml](docker-compose-prod.yml) 部署；所有 `${VAR}` 值（含全部祕密、`M365_*`）由 **Coolify Environment Variables** 注入，**不寫進 repo**。
- **測試 stage** 與 **正式 prod** 站台網址見上方〈環境與網址〉。
- 含 Seq（日誌）、adminer（DB 後台）服務。
- **要寄開通通知信**：Coolify 必須設好四個 `M365_*`（含 `M365_MAIL_SENDER`），且該 Azure App 需授 `Mail.Send`（Application）+ admin consent、寄件人信箱可被代寄。

---

## 6. 資料庫 / Migration

```bash
cd backend
uv run alembic upgrade head      # 套用至最新（目前 0014）
uv run alembic revision -m "..." # 新增 migration
```

> Windows 直接跑 alembic CLI 若遇 `cp950` 解碼錯，加 `PYTHONUTF8=1`。

---

## 7. 測試 / Lint

```bash
cd backend
./.venv/Scripts/python.exe -m pytest -q      # 或 uv run pytest
./.venv/Scripts/python.exe -m ruff check app # lint

cd frontend
npm run type-check && npm run lint
```

---

## 8. Git 分支與推送流程

- 分支：`main`（正式）← `development`（整合）← `dev-v1.x`（功能）。下一個小微調分支：**`dev-v1.10`**。
- **雙遠端**：`origin`（Jiaye-DF）與 `df-it`（Dafon-IT）。**任何推送 origin 先、df-it 後，兩邊都要推。**
- Commit message 繁中、格式 `<類型>: <描述>`（`Add`/`Modify`/`Fix`/`Refactor`/`Docs`）；AI 產生加 `(AI)` 前綴。
- 禁未授權的破壞性操作（`--force` / `reset --hard` / `--no-verify`）。

---

## 9. 主要功能與 API（前綴 `/api/v1`）

| 分類 | 路徑 | 說明 |
| --- | --- | --- |
| 認證 | `/auth/*` | 登入 / Refresh / 登出 / 改密；DF-SSO callback |
| 使用者 | `/users/*`、`/user-tokens/*` | admin CRUD、User Token 產生 / 撤銷 |
| 組織 | `/departments/*`、`/projects/*` | 部門、專案（專案代碼即 `X-Project-Code`） |
| 金鑰 | `/openrouter-keys/*`、`/sdk-keys/*`、`/internal-keys/*` | OpenRouter / SDK / 內部 LLM 金鑰 |
| 模型 | `/models/*`、`/allowed/models`、`/model-tiers/*` | 模型主檔同步、白名單、分級 |
| 用量 | `/usage-logs/*`、`/stats/*` | 用量查詢、彙總 |
| **代理** | `/model/chat` | SDK 呼叫入口（依模型 provider 自動分流；舊 `/model/openrouter/chat` 已 deprecated） |
| 申請單 | `/api-key-requests/*` | API Key 申請生命週期（見下） |
| 健康 | `/health` | 健康檢查 |

**SDK 呼叫**需帶三個 Header：`X-SDK-Key` / `X-User-Token` / `X-Project-Code`（細節與範例見 [docs/INTEGRATION.md](docs/INTEGRATION.md)）。

### API Key 申請單（v1.9 系列重點）

使用者於前端 `/api-key-requests` 送申請 → 後端**同步**跑：

1. **規則路由**（確定性）：新部門→人工；舊部門+新專案→AI 驗證；舊+舊+舊→系統取消。`owner_email` 比對於查詢層**排除系統管理員**（`account='admin'`）。
2. **AI 欄位驗證**：信心分數 **≥ 90**（`AI_AUTO_PROVISION_THRESHOLD`）才自動開通，否則降級人工。
3. **自動開通**：建專案 → 沿用/建使用者 → 沿用/建 SDK Key → 發 User Token；一次性憑證領取後清空。
4. **開通通知信（v1.9.2）**：以 M365 Graph 寄信給**專案負責人 `owner_email`**，內含憑證明文、curl 基礎範例與使用手冊連結（連結固定指向正式站）。best-effort，失敗不回滾；admin 可於詳情「重送通知」。

---

## 10. 維運須知（交接重點）

- **改 `.env` 必重啟後端**（settings 啟動時讀 + lru_cache）。M365 / OpenRouter key 改了沒生效，先想到這點。
- **`DEFAULT_OPENROUTER_KEY` 失效**（OpenRouter 回 401）→ 申請單 AI 驗證全降級人工；換有效 key 即恢復。
- **開通通知信「未設定」**＝四個 `M365_*` 有空值或後端未重啟。寄信失敗但非「未設定」多為 Azure 端權限（`Mail.Send` / 寄件人授權）。
- Email 範本在 [backend/app/templates/email/](backend/app/templates/email/)，連結（平台 / API / 使用手冊）固定指向正式站，寫在 `services/email_render.py` 常數。
- 祕密一律走環境變數；`.env`、credentials 已於 `.gitignore` 排除，勿 commit。

---

## 11. 文件索引

- [CLAUDE.md](CLAUDE.md)：開發 / 協作規範（規範優先序、Git、敏感資訊）
- [docs/Design-Base/](docs/Design-Base/)：基礎設計（不隨版本變動）
- [docs/Tasks/v1.9/](docs/Tasks/v1.9/)：v1.9 系列 propose / tasks（實作契約）
- [docs/INTEGRATION.md](docs/INTEGRATION.md)：對外 SDK 串接說明（Header、端點、錯誤碼、範例）
