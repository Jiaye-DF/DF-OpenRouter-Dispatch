# 00 · 專案總覽與規範索引

本文件是 Design-Base 的入口，定義專案目標、技術棧、Monorepo 結構、規範索引與優先順序。所有 AI 協作與 Task 產出前，應先閱讀本檔，再依需求切入其他章節。

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
├── docker-compose.yml         # 服務編排
├── .env.example               # 環境變數範本
└── README.md                  # 專案說明與 API 端點總覽
```

## 服務組成

| 服務 | 角色 | 對外 Port |
| --- | --- | --- |
| `frontend` | Next.js Web UI，呼叫 `backend` | 3000 |
| `backend` | FastAPI（由 Uvicorn 驅動），代理 OpenRouter API、處理商業邏輯與稽核 | 8000 |
| `postgres` | PostgreSQL 17，儲存金鑰、配額、用量、稽核 Log | 5432（內網） |

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

| 文件 | 涵蓋範圍 |
| --- | --- |
| [00-overview.md](./00-overview.md) | 本檔：目標、技術棧、Monorepo、規範索引、優先順序 |
| [10-frontend.md](./10-frontend.md) | 前端基本設計（技術棧細節、Layout、Dialog、Loading/Empty、a11y） |
| [20-backend.md](./20-backend.md) | 後端基本設計（Response 格式、錯誤訊息、分層、路由命名、Logging、CORS、測試） |
| [30-database.md](./30-database.md) | 資料表規範（pid / UID、軟刪除、Migration、Trigger） |
| [40-deployment.md](./40-deployment.md) | Docker Compose 部署規範（檔名、SERVICE_URL、變數注入） |
| [50-openrouter.md](./50-openrouter.md) | OpenRouter 整合（Client、代理流程、串流、重試、用量） |
| [60-naming-env.md](./60-naming-env.md) | 命名慣例、環境變數、Git 流程 |
| [70-auth.md](./70-auth.md) | 認證設計（本地登入、JWT、失效清單、密碼規則） |
| [80-permission.md](./80-permission.md) | 權限設計（管理端 / 代理端分離、角色、配額、稽核） |
| [90-task-spec.md](./90-task-spec.md) | Task 產出規範（描述格式、對齊章節、DoD、前置檢查） |

## 關鍵字語義

文件中的關鍵字代表的強制程度：

| 關鍵字 | 語義 |
| --- | --- |
| **必須 / 禁止** | 硬規定，違反即退回 |
| **應** | 強烈建議，除非有正當理由 |
| **可** | 允許的做法，不強制 |

## 規範優先順序

衝突時以下列順序決定：

**`docs/Tasks/v*-p*/Task-v*-p*.md`（版本功能設計）** > **`docs/Design-Base/*`（基礎設計）** > **[CLAUDE.md](../../CLAUDE.md)（AI 協作規範）** > 其他。
