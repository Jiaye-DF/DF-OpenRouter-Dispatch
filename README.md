# DF-OpenRouter-Dispatch

OpenRouter API 中控派發管理平台（MVP v1.0）

集中管理 User 透過 OpenRouter API 呼叫模型時的金鑰、路由與稽核。前端提供管理 UI，後端作為 OpenRouter API 的代理層；OpenRouter API Key 僅存於後端（AES-256-GCM 加密）。

## 快速開始

1. 從 `.env.example` 複製出 `.env` 並填入敏感資訊（`JWT_SECRET`、`ENCRYPTION_KEY`、`INITIAL_ADMIN_PASSWORD` 等）。
2. 本機開發：

   ```bash
   docker compose -f docker-compose.dev.yml --env-file .env up --build
   ```

3. 服務：
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - Swagger: http://localhost:8000/api/docs

## 預設帳號

首次啟動時 Alembic + Backend Seed 會建立初始 admin（帳號 `INITIAL_ADMIN_ACCOUNT`、密碼 `INITIAL_ADMIN_PASSWORD`），掛於 `SYSTEM` 部門。

## 文件

- [CLAUDE.md](CLAUDE.md)：AI 協作規範
- [docs/Design-Base/](docs/Design-Base/)：不隨版本異動的基礎設計
- [docs/Tasks/v1.0/propose-v1.0.0.md](docs/Tasks/v1.0/propose-v1.0.0.md)：本版本功能設計

## 主要 API（v1）

| 分類 | 路徑前綴 | 說明 |
| --- | --- | --- |
| 認證 | `/api/v1/auth/*` | 登入、Refresh、登出、改密 |
| 使用者 | `/api/v1/users/*` | admin CRUD + Token 產生 / 撤銷 |
| 組織 | `/api/v1/departments/*`、`/api/v1/projects/*` | 部門、專案 |
| OpenRouter Key | `/api/v1/openrouter-keys/*` | 部門層級 Key 管理 |
| SDK Key | `/api/v1/sdk-keys/*` | SDK 金鑰管理 |
| 用量 | `/api/v1/usage-logs/*`、`/api/v1/stats/*` | 用量查詢、彙總 |
| 代理 | `/api/v1/model/openrouter/chat` | SDK 呼叫 OpenRouter |
