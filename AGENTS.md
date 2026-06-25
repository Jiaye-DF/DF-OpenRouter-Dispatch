# AGENTS.md — DF-OpenRouter-Dispatch

跨工具(Claude Code / Codex / Cursor / Cline / Aider)agent 協議。**鎖定 Next.js 14 (App Router) + TypeScript + FastAPI + PostgreSQL,本地開發優先**。本檔為**跨工具事實層**;`CLAUDE.md` 僅補 Claude 特性,不重述。

> ⚠️ **localhost ≠ 部署環境**。本檔 `localhost:*` 範例僅供本地開發;部署規範見 `docs/Design-Base/06-Coolify-CD/`。
>
> 本專案 2026-06-25 起採 **Harness-Engineering** spec(巢狀 `docs/Design-Base/`);整合說明見 `docs/Design-Base/README.md` 與各 `00-overview/90-project-*.md`。

## Project Overview

OpenRouter / 多 provider 模型呼叫的**中控派發管理平台**:集中管理金鑰、配額、路由、白名單與用量稽核。前端為管理 UI,後端為模型代理 + 商業邏輯層;**OpenRouter 原生 API Key 僅存後端(AES-256-GCM 加密),禁下發前端**。代理端採 **SDK Key + User Token 雙因子**認證(部門一致);支援 OpenRouter(外網,多 Key failover)與 Internal(地端 OpenAI-compatible,排隊等待)兩 provider。詳見 `docs/Design-Base/90-third-party-service/50-openrouter.md`。

## Tech Stack

- **Frontend**:Next.js **14.2** (App Router) + TypeScript(`strict: true`)+ Redux Toolkit + RTK Query + Tailwind **v4** + next-themes + react-hook-form + zod + lucide-react + recharts
- **Backend**:Python **3.14** + FastAPI + SQLAlchemy 2 async + Pydantic 2 + Alembic + httpx + `pyjwt` + **`argon2-cffi`(argon2id)** + `cryptography`(AES-256-GCM) + `uuid-utils`(UUIDv7);log 走 **Seq**(`seqlog`)
- **Database**:PostgreSQL **17**(asyncpg;Alembic migration 用 `psycopg` sync driver)
- 版本鎖到 patch — 詳見 `docs/Design-Base/00-overview/01-versions.md`(已 re-baseline:**非** HE 模板的 React 19 / bcrypt;Tailwind 採 HE 的 v4,前端 v3.4→v4 程式碼遷移為獨立工作)

## Just-in-time Loading

依任務性質載入必要檔,**不預載**歷史報告(`fixed.md` / `Issue-Scan-Project-*` / `reflect-report-*`)。

> **完整任務 → 檔案 對照表**:`docs/Design-Base/README.md`。任何任務先讀本檔的「永遠載入」+ 該檔對照表,即知要載哪些規範,**不必**全資料夾掃描。

### 永遠載入(任何任務)

- 本檔(`AGENTS.md`)
- `docs/Design-Base/README.md`(索引)
- `docs/Design-Base/00-overview/00-overview.md`(規範優先序 + 輸出語言)

### 依子任務載入(節錄;完整見 `docs/Design-Base/README.md`)

| 子任務 | 永遠載入 + 必讀 |
| --- | --- |
| 前端風格 / 元件 | `02-frontend/00-overview.md`(+ `90-project-frontend.md` / `91-project-ui-ux.md` 本專案 UI) |
| 後端新 API endpoint | `03-backend/00-overview.md` + `01-routing.md`(+ `90-project-backend.md`) |
| 認證 / 權限 | `03-backend/02-auth.md` + `91-project-auth.md` + `92-project-permission.md` |
| 設計 DB 表 / migration | `04-databases/00-overview.md` + `01-identifiers.md` / `08-alembic.md`(+ `90-project-database.md` Snowflake/baseline) |
| 串模型代理 / OpenRouter / Internal | `90-third-party-service/00-overview.md` + `01-client-design.md` + `50-openrouter.md` |
| 寫 propose / tasks | `01-propose/*` + `90-project-task-spec.md` |
| 改 env / secret | `00-overview/02-secrets.md` + `03-env-layers.md` + `91-project-naming-env.md` |
| 部署 / compose / Dockerfile | `06-Coolify-CD/*` + `90-project-deployment.md` |
| 發 PR / 收口 | `99-code-review/03-pr-self-check.md` + 對應 checklist |

## Build / Test / Lint

```bash
# Frontend(frontend/)
npm ci && npm run lint && npm run type-check && npm run build

# Backend(backend/;uv 為套件管理)
uv sync && uv run ruff check . && uv run mypy . && uv run pytest && uv run alembic upgrade head
```

## Local Dev(僅 localhost)

```bash
# 前提:本機 PostgreSQL 已啟動,`.env` 已從 `.env.example` 複製並填值
cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000   # backend
cd frontend && npm run dev                                                       # frontend(另一 terminal,port 3000)
```

> 一鍵啟動見 `/dev-up`(`.claude/commands/dev-up.md`)。部署到 staging / production 見 `docs/Design-Base/06-Coolify-CD/`。

## Code Style

- **Output**:繁體中文(回應 / 註解 / 文件 / commit)
- **Comments**:不主動加;只在 *why* 非自明時加
- **TS**:`strict: true`、禁 `any`、props 用獨立 `interface`、函式必標型別
- **Python**:PEP 484/585 強制、禁 `Any` / `typing.List` / `typing.Dict`、用 `list[...]` / `dict[...]`、`AsyncSession` from `sqlalchemy.ext.asyncio`
- **Naming**:遵循各 area 的 `00-overview.md`

## Testing

- 後端整合測試**禁** mock SQL,須用真實測試 DB(testcontainers 或獨立 test DB)
- 第三方(OpenRouter / Internal):`respx` / `httpx.MockTransport`
- 前端單元:`vitest` 或 jest(視專案);e2e:Playwright(預設 disabled)

## 專案特有硬規則

- **速率 / 配額 / cooldown**:現行(v1.2)走單 worker(`UVICORN_WORKERS=1`)in-memory limiter + Postgres;**方向**為轉 harness 架構 + Celery/Redis(背景任務 broker,未來換 RabbitMQ)。改動相關區塊前先確認當前是哪一階段。
- **Snowflake worker id**:會產生 Snowflake ID 的 process 必配發不同 `SNOWFLAKE_WORKER_ID`(見 `04-databases/90-project-database.md § 7`)。
- **代理 / 管理端隔離**:代理端只接 `X-SDK-Key` / `X-User-Token`,管理端只接 Cookie / Access Token,**禁**混用。
- **敏感資訊**:OpenRouter Key / SDK Key 明文 / User Token 明文 / 密碼 hash **禁**入 Response / Log / Commit;log 必要時只留前後 4 字元。

## Git Workflow

- Commit:`(AI?) <類型>: <描述>`(繁中);類型 `Add` / `Modify` / `Fix` / `Refactor` / `Docs`,AI 產生**必**前綴 `(AI)`
- 主分支 `main`,功能分支從 `main` 切出
- `tasks-v*.md` checkbox 與頂部狀態必一致;bug / 規範違反 → 同步 `fixed.md`(`99-code-review/01-fixed-md.md`)
- 未經明示授權,**禁**破壞性操作(`--force` / `reset --hard` / `--no-verify`)

## 毀滅性操作禁止

- **禁**任何 DROP 類 DB 操作(`DROP DATABASE/SCHEMA/TABLE/COLUMN`)、刪 Docker volume(`down -v` / `--volumes`)、`rm -rf`。
- 任何可能造成資料遺失 / 不可逆清除 / volume 消失的指令,**必須**停下改用安全替代,或請人類確認 + 備份後處理。

## Security

- 機密**僅**透過 env var 注入;`.env` 必 gitignore;`git log --all -- .env` 須為空
- production 啟動 fail-fast(`Settings.model_validator`);機密**不可**入 log
- 偵測規則:`.claude/commands/scan-project.md`

## Rule Precedence

```
docs/Design-Base/* > docs/Arch/* > AGENTS.md / CLAUDE.md > docs/Tasks/*
```

衝突依此優先序機械式判定(**2026-06-25 起改採此 HE 序**,原「Tasks 最高」已廢止)。`AGENTS.md` 與 `CLAUDE.md` 同層,內容須一致;`CLAUDE.md` 僅補充 Claude 特性,不重述。
