# 90 · 專案總覽(DF-OpenRouter-Dispatch)

> **本檔為本專案特有的「專案總覽」**(原扁平 `docs/Design-Base/00-overview.md`,2026-06-25 遷入 HE 巢狀結構)。
> **規範優先序、輸出語言、版本鎖定、按需載入**以 HE 通用層為準:`00-overview/00-overview.md`、`01-versions.md`、`docs/Design-Base/README.md`。本檔只保留**專案目標 / 技術棧 / Monorepo / 服務組成 / 資料流**等專案事實。

本文件定義專案目標、技術棧、Monorepo 結構與服務組成。任何 Task 產出前,先讀 HE 入口(`00-overview/00-overview.md` + `docs/Design-Base/README.md` 的「任務→檔案」對照表),再依需求切入。

## 目標

- 建立 **OpenRouter API 中控派發管理平台**：集中管理 User 透過 OpenRouter API 呼叫模型時的金鑰、配額、路由與稽核。
- 前端負責管理 UI 與互動，後端作為 OpenRouter API 的代理與商業邏輯層，OpenRouter API Key 僅存於後端，**禁止**下發至前端。
- 提供可稽核的模型呼叫紀錄與用量統計，便於成本控管與異常追蹤。

## 語言與文件規範

- 文件、UI 文案、註解一律使用**繁體中文**（`zh-TW`）。
- Commit Message 使用中文，遵循 `類型: 描述` 格式（`Add` / `Modify` / `Fix` / `Refactor` / `Docs`），AI 協作產生的 commit 一律加上 `(AI)` 前綴。

## 技術棧

| 分類 | 技術 | 版本 |
| --- | --- | --- |
| 後端框架 | FastAPI | 最新穩定版 |
| 後端語言 | Python | 3.14+ |
| ASGI Server | Uvicorn | 最新穩定版 |
| 資料驗證 | Pydantic | v2 |
| ORM | SQLAlchemy | 2.x |
| 資料庫 | PostgreSQL | 17 |
| 前端框架 | Next.js（App Router） | 最新 LTS |
| 前端語言 | TypeScript | 5.x |
| 狀態管理 | Redux Toolkit | 2.x |
| CSS 框架 | Tailwind CSS | 最新穩定版 |
| HTTP Client（後端） | httpx | — |

> 版本以 `.env.example` 與各子專案 `pyproject.toml` / `package.json` 為準；本表為最低要求。

## Monorepo 目錄結構

```
DF-OpenRouter-Dispatch/
├── .claude/
│   └── commands/              # Claude Code 自訂指令
├── docs/
│   ├── Design-Base/           # 不隨版本異動的基礎設計規範（本目錄）
│   └── Tasks/                 # 各版本 Task 文件（v=version, p=process step）
├── backend/                   # FastAPI 後端
│   ├── app/
│   │   ├── api/v1/            # RESTful 路由（依資源分檔）
│   │   ├── services/          # 商業邏輯層
│   │   ├── clients/openrouter/# OpenRouter API Client（統一出口）
│   │   ├── schemas/           # Pydantic Request / Response 模型
│   │   ├── models/            # SQLAlchemy ORM Model
│   │   ├── repositories/      # 資料存取層
│   │   ├── utils/             # 共用工具
│   │   ├── core/              # 設定、例外、Response helper、依賴注入
│   │   └── main.py            # FastAPI 入口（指定 docs_url="/api/docs"）
│   ├── tests/                 # pytest 測試
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/                  # Next.js 前端
│   ├── src/
│   │   ├── app/               # Next.js App Router
│   │   ├── components/        # 共用元件
│   │   ├── store/             # Redux Toolkit Store
│   │   ├── lib/               # 工具函式、API Client
│   │   └── styles/            # Tailwind 全域樣式
│   ├── package.json
│   └── Dockerfile
├── migrations/                # 資料庫 Migration
├── docker-compose-prod.yml    # Coolify 正式部署編排
├── docker-compose.dev.yml     # 本機開發服務編排
├── .env.example               # 環境變數範本
└── README.md                  # 專案說明與 API 端點總覽
```

## 服務組成

| 服務 | 角色 | 對外 Port |
| --- | --- | --- |
| `frontend` | Next.js Web UI，呼叫 `backend` | 3000 |
| `backend` | FastAPI（由 Uvicorn 驅動），代理 OpenRouter API、處理商業邏輯與稽核 | 8000 |
| `postgres` | PostgreSQL 17，儲存金鑰、配額、用量、稽核 Log | 5432（內網） |
| `adminer` | 資料庫管理 Web UI（正式環境須加存取限制） | 8080 |
| `seq` | Seq 集中式 Log 收集與查詢（標準監控服務） | 80 |

## 請求與資料流

```
使用者 / 呼叫端
  │
  ▼
[frontend] Next.js 管理介面
  │  呼叫 /api/v1/...
  ▼
[backend] FastAPI
  │  1. 身分驗證與權限檢查
  │  2. 配額 / 白名單 / 路由策略（services）
  │  3. OpenRouter API Client (clients/openrouter)
  │  4. 寫入用量與稽核 Log
  ├──────────────▶ [OpenRouter] 外部服務
  │                （API Key 由後端統一管理）
  ▼
[postgres] 本地狀態（使用者、金鑰、配額、用量、稽核）
```

- 前端**禁止**直接呼叫 OpenRouter API。
- OpenRouter API Key 僅存在於後端，透過環境變數或加密 DB 欄位管理，**禁止**寫入前端程式碼或回傳至瀏覽器。
- 所有對 OpenRouter 的呼叫必須經由 `backend/app/clients/openrouter/` 統一出口，便於集中稽核與重試策略。

## 前後端分離

- 前端與後端分別為獨立子目錄（`frontend/`、`backend/`），各自獨立 Dockerfile 與依賴管理。
- 前端透過 `NEXT_PUBLIC_API_BASE_URL` 指向後端，**禁止**硬編碼。
- 後端 API 文件統一發佈於 **`/api/docs`**（FastAPI 初始化時明確指定 `docs_url="/api/docs"`）。

## 規範索引

> 完整「任務 → 必讀檔」對照見 [`docs/Design-Base/README.md`](../README.md)。下表為**舊扁平檔 → 新巢狀位置**對照(舊扁平檔已移除,內容見新位置)。

| 舊扁平檔(已移除) | 新位置(本專案內容) | HE 通用對應 |
| --- | --- | --- |
| `00-overview.md` | `00-overview/90-project-overview.md`(本檔) | `00-overview/00-overview.md` |
| `10-frontend.md` | `02-frontend/90-project-frontend.md` | `02-frontend/00-overview.md` |
| `11-ui-ux.md` | `02-frontend/91-project-ui-ux.md` | `02-frontend/05-components.md` |
| `20-backend.md` | `03-backend/90-project-backend.md` | `03-backend/00-overview.md` |
| `30-database.md` | `04-databases/90-project-database.md` | `04-databases/*` |
| `40-deployment.md` | `06-Coolify-CD/90-project-deployment.md` | `06-Coolify-CD/*` |
| `50-openrouter.md` | `90-third-party-service/50-openrouter.md` | `90-third-party-service/01-client-design.md` |
| `60-naming-env.md` | `00-overview/91-project-naming-env.md` | `00-overview/02-secrets.md` / `03-env-layers.md` |
| `70-auth.md` | `03-backend/91-project-auth.md` | `03-backend/02-auth.md` |
| `80-permission.md` | `03-backend/92-project-permission.md` | (HE 無;本專案特有) |
| `90-task-spec.md` | `01-propose/90-project-task-spec.md` | `01-propose/*` |

## 關鍵字語義

文件中的關鍵字代表的強制程度：

| 關鍵字 | 語義 |
| --- | --- |
| **必須 / 禁止** | 硬規定，違反即退回 |
| **應** | 強烈建議，除非有正當理由 |
| **可** | 允許的做法，不強制 |

## 規範優先順序(已對齊 HE)

> **2026-06-25 起改採 HE 序**(原「Tasks 最高」已廢止):
>
> ```
> docs/Design-Base/* > docs/Arch/* > AGENTS.md / CLAUDE.md > docs/Tasks/*
> ```
>
> 基礎規範(Design-Base)為**不可違反的地板**,版本 `propose/tasks` **不可**凌駕;要改規則**先改 Design-Base 再開 Task**。完整說明見 `00-overview/00-overview.md`。
