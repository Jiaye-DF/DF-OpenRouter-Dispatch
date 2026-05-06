# 40 · 部署與 Docker Compose 規範

本文件定義本機開發與 Coolify 正式環境的部署策略、Docker Compose 規範與環境變數注入方式。

## 1. 執行模型

- **本機 / 開發**：整個專案（`frontend` / `backend` / `postgres` / `flyway`）全部以 `docker compose` 啟動，**禁止**在主機直接跑 Node / Python。
- **正式環境**：開發測試完成後，將 `docker-compose.yml` 部署至 **Coolify**。
- Coolify 負責反向代理、TLS、域名綁定、環境變數注入與 Log 收集。
- 環境分為 `dev` / `staging` / `prod`，各自使用獨立的 `.env` 與 Compose override 檔。

## 2. Coolify Docker Compose 六條核心規則

本章節規則**僅適用於 Coolify 實際部署的 `docker-compose.yml`**。本機開發用的 `docker-compose.dev.yml` 可放寬部分規則（例如允許 `${VAR:-default}` 與 `ports:`、`env_file:`），但 volume **仍必須**顯式命名，且**禁止** commit 敏感資訊。

Coolify 部署檔 `docker-compose.yml` **必須**遵守 [AI-Spec / Coolify-Deploy / Docker-Compose-Spec-v1.2](https://github.com/Jiaye-DF/AI-Spec/blob/main/Coolify-Deploy/Docker-Compose-Spec-v1.2.md)：

1. **檔名**：使用 `docker-compose.yml`（副檔名 **`.yml`**，**禁用** `.yaml`）。本機開發另以 `docker-compose.dev.yml` 區分。
2. **網路**：**禁止**定義 `networks:` 區塊，由 Coolify 自動管理服務間網路。
3. **變數位置**：所有變數放在 `environment:`，**禁止**在 `command:` 中使用 `${VAR}`。
4. **變數語法**：僅使用 `${VAR}`，**禁止**使用 `${VAR:?error}` 等條件語法。
5. **Volume 命名**：所有 volume **必須**顯式命名（加 `name:`），避免重新部署時遺失資料。
6. **敏感資訊**：一律填入 **Coolify 後台 Environment Variables**，**禁止**寫死於 Compose 或 Dockerfile。

## 3. SERVICE_URL 約定

- 格式：`SERVICE_URL_{SERVICE_NAME}_{PORT}`，SERVICE_NAME **必須**與 Compose service 名稱完全一致。
- **僅適用於 HTTP/HTTPS 服務**（frontend、backend 等）。
- 冒號後**必須**保留空白，由 Coolify 自動填入值：

```yaml
environment:
  - SERVICE_URL_BACKEND_8000:                       # ✅ 正確
  - SERVICE_URL_BACKEND_8000=http://backend:8000    # ❌ 錯誤
```

- PostgreSQL、Redis 等 **TCP 服務禁用** SERVICE_URL，改以 `DATABASE_URL`、`REDIS_URL` 等變數，直接透過 Compose service 名稱互連。

## 4. `docker-compose.yml` 範本

```yaml
services:
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    environment:
      - SERVICE_URL_FRONTEND_3000:
      - NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
    expose:
      - "3000"
    depends_on:
      - backend

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      - SERVICE_URL_BACKEND_8000:
      - APP_ENV=${APP_ENV}
      - LOG_LEVEL=${LOG_LEVEL}
      - UVICORN_WORKERS=${UVICORN_WORKERS}
      - DATABASE_URL=${DATABASE_URL}
      - JWT_SECRET=${JWT_SECRET}
      - JWT_ALGORITHM=${JWT_ALGORITHM}
      - ACCESS_TOKEN_EXPIRES_MINUTES=${ACCESS_TOKEN_EXPIRES_MINUTES}
      - REFRESH_TOKEN_EXPIRES_DAYS=${REFRESH_TOKEN_EXPIRES_DAYS}
      - ACCESS_COOKIE_NAME=${ACCESS_COOKIE_NAME}
      - REFRESH_COOKIE_NAME=${REFRESH_COOKIE_NAME}
      - CORS_ORIGINS=${CORS_ORIGINS}
      - ENCRYPTION_KEY=${ENCRYPTION_KEY}
      - INITIAL_ADMIN_ACCOUNT=${INITIAL_ADMIN_ACCOUNT}
      - INITIAL_ADMIN_USERNAME=${INITIAL_ADMIN_USERNAME}
      - INITIAL_ADMIN_PASSWORD=${INITIAL_ADMIN_PASSWORD}
      - OPENROUTER_API_BASE_URL=${OPENROUTER_API_BASE_URL}
      - OPENROUTER_API_TIMEOUT=${OPENROUTER_API_TIMEOUT}
    expose:
      - "8000"
    depends_on:
      - postgres
      - flyway

  postgres:
    image: postgres:17-alpine
    environment:
      - POSTGRES_DB=${POSTGRES_DB}
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    expose:
      - "5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data

  flyway:
    image: flyway/flyway:10-alpine
    command: -connectRetries=60 migrate
    environment:
      - FLYWAY_URL=${FLYWAY_URL}
      - FLYWAY_USER=${FLYWAY_USER}
      - FLYWAY_PASSWORD=${FLYWAY_PASSWORD}
      - FLYWAY_LOCATIONS=${FLYWAY_LOCATIONS}
    volumes:
      - ./migrations:/flyway/sql
    depends_on:
      - postgres

volumes:
  postgres-data:
    name: ${COMPOSE_PROJECT_NAME}-postgres-data
```

> `flyway` service 的 `command:` 為 Flyway CLI 參數（非 shell 變數），不違反「`command` 禁用 `${VAR}`」規則。所有連線資訊皆透過 `environment:` 注入。

## 5. 環境變數注入策略

| 階段 | 變數來源 |
| --- | --- |
| 本機開發 | 專案根目錄 `.env`（由 `.env.example` 複製填寫） |
| Coolify 部署 | **Coolify 後台 Environment Variables**；`.env` **禁止**上傳至正式環境 |

- 敏感資訊（`JWT_SECRET`、`ENCRYPTION_KEY`、`INITIAL_ADMIN_PASSWORD`、`POSTGRES_PASSWORD`）一律於 Coolify 後台填寫。OpenRouter 原生 API Key **不**以環境變數注入，改由 admin 於後台建立部門層級 Key（AES-256-GCM 加密存 DB）。
- `SERVICE_URL_*` 變數無需手動填值，Coolify 於部署時自動注入對應公開網址。
- 環境變數新增流程詳見 [60-naming-env.md](./60-naming-env.md)。

## 6. 部署流程

1. 本機以 `docker compose up --build` 驗證所有服務可正常啟動、Migration 成功執行、Swagger (`/api/docs`) 可存取。
2. Push 至 Git（`main` 或部署分支）。
3. Coolify 偵測變更 → 拉取 → Build → 部署。
4. 監控 Coolify 的**部署 Log** 與**應用程式 Log**，確認：
   - Flyway Migration 無錯誤
   - Backend 啟動後 Swagger 可存取
   - Frontend 可呼叫 Backend `/api/v1/...`
   - OpenRouter Proxy 試打一次低成本模型確認通路
5. 若部署失敗，對照 [Docker-Compose-Spec-v1.2](https://github.com/Jiaye-DF/AI-Spec/blob/main/Coolify-Deploy/Docker-Compose-Spec-v1.2.md) 的 Troubleshooting 表排查。

## 7. 常見陷阱對照

| 問題 | 原因 | 處理 |
| --- | --- | --- |
| 服務間無法互連 | 定義了 `networks:` | 移除，交由 Coolify 管理 |
| 變數為空 | 使用 `${VAR:?error}` | 改用 `${VAR}` |
| SERVICE_URL 無值 | 冒號後寫了內容 | 保持冒號後為空白 |
| DB 連不上 | 對 TCP 服務套用 SERVICE_URL | 改用 `DATABASE_URL` / service 名稱 |
| 重新部署後資料消失 | Volume 未命名 | Volume 加 `name:` |
| 外部無法存取 | 缺少 `expose:` | 於 service 加 `expose:` |
