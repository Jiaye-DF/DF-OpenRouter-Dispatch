# DF-OpenRouter-Dispatch — 交接文件

> OpenRouter API 中控派發管理平台。集中管理使用者透過 OpenRouter（及內部 LLM）呼叫模型時的**金鑰、路由、白名單、用量稽核**。前端為管理 UI，後端為呼叫代理層；OpenRouter / SDK 金鑰僅存於後端（AES-256-GCM 加密）。
>
> 本檔為**交接用**：環境、啟動、部署、分支流程、維運須知一次看完。功能設計細節見 [docs/](docs/)。
>
> 目前版本進度：**v2.1.1 已上線**（已併入 `main` / `development`）。當前開發分支 `dev-v2.1`。
>
> v2.0–v2.1 主軸：**AI 模型適配評審 + 真實重跑 + 對比裁決**（taskiq + Redis 背景管線），詳見 §12。v2.1.1 另補：**下載 Excel 全維度鏡射儀表板（含專案×模型花費）** 與 **用量紀錄下放部門（顯示所屬專案 + 專案篩選）**。完整系統說明與架構/流程圖見 [docs/DF-OpenRouter-派工系統-專案說明文件.html](docs/DF-OpenRouter-派工系統-專案說明文件.html)。

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
| 背景任務 | **taskiq + Redis**（broker / result，未來可換 RabbitMQ）；`taskiq-worker` 執行、`taskiq-scheduler` 週期派發（v2.0 起：AI 模型評審 / 真實重跑 / 對比裁決） |
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
                            model_chat〔代理〕/user_tokens/health/
                            ai_eval〔判別模型設定〕/ai_eval_results/ai_eval_reruns〔v2.0–2.1〕）
    clients/                外部呼叫（openrouter / sso / internal）
    core/                   config / database / security / crypto / audit / deps / logging
    tasks/                  taskiq broker / scheduler / ai_model_eval〔評審+重跑 task/dispatcher〕
    models/ repositories/ schemas/ services/  （含 ai_model_eval* / ai_eval_judge_setting / llm_json）
    templates/email/        Jinja2 Email 範本（base.html + provision.html）
  alembic/versions/         migration 0001–0027
  tests/                    pytest（services / core / repositories / tasks / api）
frontend/                   Next.js（src/app/(main)/<各功能頁>；含 ai-analysis/judge-settings、ai-analysis/verdicts）
docs/
  Design-Base/              不隨版本變動的基礎設計
  Tasks/v1.x/ v2.x/         各版 propose / tasks（實作契約）+ fixed.md（根因紀錄）
  DF-OpenRouter-…-專案說明文件.html  單頁式系統說明（含架構圖 / 流程圖）
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
6. **AI 模型評審 / 重跑（v2.0–v2.1）**：
   - `TASKIQ_BROKER_URL` / `TASKIQ_RESULT_BACKEND_URL` / `REDIS_URL`（Redis 連線；compose 內主機名為 `redis`）。
   - `AI_EVAL_ENABLED`（評審總開關）、`AI_EVAL_BEAT_INTERVAL_SECONDS`（beat 間隔）、`AI_EVAL_DISPATCH_BATCH_SIZE`（每輪派發筆數）、`AI_EVAL_TASK_MAX_RETRIES`。
   - `AI_EVAL_START_AT`（**起始時間門檻**：只分析 `created_at >=` 此時間的資料，空=不設限；格式 `YYYY-MM-DD`，視為 Asia/Taipei 00:00:00。用於避免回溯大量歷史資料成本暴增）。
   - `AI_RERUN_ENABLED`（真實重跑總開關）、`AI_RERUN_DISCRIMINATOR_ENABLED`（對比裁決子開關；重跑沿用評審的 beat / batch，不另設）。
   - 判別模型於後台「AI 分析 → 判別模型設定」設定（恰 3 個、不可重複、不得選 free）。

> ⚠️ **改 `.env` 後一定要重啟後端才生效**：settings 於程序啟動時讀入且 `get_settings()` 有 lru_cache，熱改檔案不會生效。**改 AI_EVAL_* / AI_RERUN_* 後須重啟 `taskiq-worker` 與 `taskiq-scheduler`。**

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

compose 另含 **redis**（taskiq broker）、**taskiq-worker**（執行評審 / 重跑）、**taskiq-scheduler**（週期派發）等服務；AI 評審需 `AI_EVAL_ENABLED=true` 才會動作。

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
uv run alembic upgrade head      # 套用至最新（目前 0027）
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

- 分支：`main`（正式）← `development`（整合）← `dev-vX.Y`（功能）。當前功能分支：**`dev-v2.1`**。
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
| 用量 | `/usage-logs/*`、`/stats/*`（含 `/stats/by-project-model`） | 用量查詢、彙總（依部門 / 模型 / 專案 / 使用者 / 時序 / **專案×模型**）。admin 看全部;一般使用者鎖**自身部門**（v2.1.1）。`/usage-logs` 回應帶所屬專案、列表支援專案篩選 |
| **代理** | `/model/chat`、`/model/chat/stream` | SDK 呼叫入口（依模型 provider 自動分流；舊 `/model/openrouter/chat` 已 deprecated）。v2.1.2 起支援 `messages` 多輪對話（與單輪 `text`/`images`/`files` 互斥）與 `temperature` / `max_tokens` / `response_format` 生成參數（未帶走模型預設），契約詳見 [docs/INTEGRATION.md](docs/INTEGRATION.md) |
| 申請單 | `/api-key-requests/*` | API Key 申請生命週期（見下） |
| **AI 分析** | `/ai-eval/judge-settings`、`/ai-eval/evaluations/by-usage-log/{uid}`、`/ai-eval/reruns` | 判別模型設定；依用量紀錄取評審結果；跨 log AI 判決總覽（分組分頁 + 編號排序/搜尋）。admin only（v2.0–2.1，見 §12） |
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
- [docs/Tasks/v1.9/](docs/Tasks/v1.9/)、[docs/Tasks/v2.0/](docs/Tasks/v2.0/)、[docs/Tasks/v2.1/](docs/Tasks/v2.1/)：各版 propose / tasks（實作契約）+ `fixed.md`（根因紀錄）
- [docs/DF-OpenRouter-派工系統-專案說明文件.html](docs/DF-OpenRouter-派工系統-專案說明文件.html)：單頁式系統說明（含架構圖 / 流程圖 / 版本演進 / 維運手冊）
- [docs/INTEGRATION.md](docs/INTEGRATION.md)：對外 SDK 串接說明（Header、端點、錯誤碼、範例）

---

## 12. AI 模型適配評審（v2.0–v2.1）

背景非同步（**taskiq + Redis**）評估「使用者原模型是否適配、是否有更合適者」，並對推薦模型**真實重跑**後做盲化**對比裁決**，集中呈現於後台「AI 分析 → AI 判決總覽」。**不影響使用者即時呼叫**。

**管線**（兩段，皆由 `taskiq-scheduler` 週期觸發、`taskiq-worker` 執行）：

1. **評審**（`AI_EVAL_ENABLED`）：撈未評審 `usage_logs`（`created_at >= AI_EVAL_START_AT`、FIFO）→ 由 **3 個判別模型**交叉評審打分、推薦更適合模型（**排除 free 模型**）→ 寫評審父表 + 候選。
2. **真實重跑 + 對比裁決**（`AI_RERUN_ENABLED`）：對推薦模型（≠ 原模型、≠ free）逐一**真實重跑**取客觀指標 → `AI_RERUN_DISCRIMINATOR_ENABLED` 時由推薦該模型的評審本人當裁判，**盲化**比「推薦輸出 vs 原輸出」→ 得「建議維持 / 改用 / 平手」+ 成本Δ。

**重點設計**：

- **成本控制**：`AI_EVAL_START_AT` 設起始門檻，舊資料不回溯分析；兩道開關可獨立關閉達零成本。
- **品質**：推薦/重跑一律**排除 free 模型**（限流、易下架）；裁決**盲化**降低偏好偏差；判別模型回覆採**強健 JSON 解析**（容忍圍欄 / 夾帶文字 / `Extra data`）。
- **判別模型設定**：後台恰選 3 個、不可重複；`ai_judge_slot` 採 **partial unique**（排除軟刪），設定後可正常修改。

對應 propose / tasks 見 [docs/Tasks/v2.0/](docs/Tasks/v2.0/)、[docs/Tasks/v2.1/](docs/Tasks/v2.1/)；流程圖 / 架構圖見專案說明文件 §5 圖 3、§6 圖 4。
