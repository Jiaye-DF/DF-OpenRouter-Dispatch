# 40 · 部署與 Docker Compose 規範

本文件定義本機開發與 Coolify 正式環境的部署策略、Docker Compose 規範與環境變數注入方式。

## 1. 執行模型

- **本機 / 開發**：整個專案（`frontend` / `backend` / `postgres` / `alembic`）全部以 `docker compose` 啟動,**禁止**在主機直接跑 Node / Python。`alembic` 為 one-shot service,啟動時跑 `alembic upgrade head` 後結束;`backend` 透過 `depends_on: condition: service_completed_successfully` 等待 migration 完成。
- **正式環境**：開發測試完成後，將 `docker-compose-prod.yml` 部署至 **Coolify**。
- Coolify 負責反向代理、TLS、域名綁定、環境變數注入與 Log 收集。
- 環境分為 `dev` / `staging` / `prod`，各自使用獨立的 `.env` 與 Compose override 檔。

## 2. Coolify Docker Compose 七條核心規則

本章節規則**僅適用於 Coolify 實際部署的 `docker-compose-prod.yml`**。本機開發用的 `docker-compose.dev.yml` 可放寬部分規則（例如允許 `${VAR:-default}` 與 `ports:`、`env_file:`），但 volume **仍必須**顯式命名，且**禁止** commit 敏感資訊。

Coolify 部署檔 `docker-compose-prod.yml` **必須**遵守 [AI-Spec / Coolify-Deploy / Docker-Compose-Spec-v1.3](https://github.com/Jiaye-DF/AI-Spec/blob/main/Coolify-Deploy/Docker-Compose-Spec-v1.3.md)：

1. **檔名**：Coolify 部署檔用 `docker-compose-prod.yml`、本機開發用 `docker-compose.dev.yml`（副檔名一律 **`.yml`**，**禁用** `.yaml`）。本專案以後綴明確區分環境，AI-Spec 預設檔名為 `docker-compose.yml`，故部署時須於 Coolify 後台指定 compose 檔路徑為 `docker-compose-prod.yml`。
2. **網路**：**禁止**定義 `networks:` 區塊，由 Coolify 自動管理服務間網路。
3. **變數位置**：所有變數放在 `environment:`，**禁止**在 `command:` 中使用 `${VAR}`。
4. **變數語法**：僅使用 `${VAR}`，**禁止**使用 `${VAR:?error}` 等條件語法。
5. **Volume 命名**：所有 volume **必須**顯式命名（加 `name:`），避免重新部署時遺失資料。
6. **敏感資訊**：一律填入 **Coolify 後台 Environment Variables**，**禁止**寫死於 Compose 或 Dockerfile。
7. **`environment` 語法**：一律使用 `key: value` map 語法，**禁止**使用 `- KEY=value` list 語法（同一 service 不可混用兩種語法）。

## 3. SERVICE_URL 約定

- 格式：`SERVICE_URL_{SERVICE_NAME}_{PORT}`，SERVICE_NAME **必須**與 Compose service 名稱完全一致。
- **僅適用於 HTTP/HTTPS 服務**（frontend、backend 等）。
- 冒號後**必須**保留空白，由 Coolify 自動填入值：

```yaml
environment:
  SERVICE_URL_BACKEND_8000:                         # ✅ 正確（冒號後留空）
  SERVICE_URL_BACKEND_8000: http://backend:8000     # ❌ 錯誤（不可自行填值）
```

- PostgreSQL、Redis 等 **TCP 服務禁用** SERVICE_URL，改以 `DATABASE_URL`、`REDIS_URL` 等變數，直接透過 Compose service 名稱互連。

## 4. `docker-compose-prod.yml` 範本

```yaml
services:
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    environment:
      SERVICE_URL_FRONTEND_3000:
      NEXT_PUBLIC_API_BASE_URL: ${NEXT_PUBLIC_API_BASE_URL}
    expose:
      - "3000"
    depends_on:
      - backend

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      SERVICE_URL_BACKEND_8000:
      APP_ENV: ${APP_ENV}
      APP_NAME: backend
      LOG_LEVEL: ${LOG_LEVEL}
      UVICORN_WORKERS: ${UVICORN_WORKERS}
      DATABASE_URL: ${DATABASE_URL}
      JWT_SECRET: ${JWT_SECRET}
      JWT_ALGORITHM: ${JWT_ALGORITHM}
      ACCESS_TOKEN_EXPIRES_MINUTES: ${ACCESS_TOKEN_EXPIRES_MINUTES}
      REFRESH_TOKEN_EXPIRES_DAYS: ${REFRESH_TOKEN_EXPIRES_DAYS}
      ACCESS_COOKIE_NAME: ${ACCESS_COOKIE_NAME}
      REFRESH_COOKIE_NAME: ${REFRESH_COOKIE_NAME}
      CORS_ORIGINS: ${CORS_ORIGINS}
      ENCRYPTION_KEY: ${ENCRYPTION_KEY}
      INITIAL_ADMIN_ACCOUNT: ${INITIAL_ADMIN_ACCOUNT}
      INITIAL_ADMIN_USERNAME: ${INITIAL_ADMIN_USERNAME}
      INITIAL_ADMIN_PASSWORD: ${INITIAL_ADMIN_PASSWORD}
      OPENROUTER_API_BASE_URL: ${OPENROUTER_API_BASE_URL}
      OPENROUTER_API_TIMEOUT: ${OPENROUTER_API_TIMEOUT}
      DEFAULT_OPENROUTER_KEY: ${DEFAULT_OPENROUTER_KEY}
      SEQ_INGESTION_URL: http://seq
      SEQ_API_KEY: ${SEQ_API_KEY}
    expose:
      - "8000"
    depends_on:
      postgres:
        condition: service_healthy
      alembic:
        condition: service_completed_successfully
      seq:
        condition: service_started

  postgres:
    image: postgres:17-alpine
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    expose:
      - "5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
      interval: 3s
      timeout: 3s
      retries: 20

  alembic:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: ${DATABASE_URL}
    command: ["alembic", "upgrade", "head"]
    depends_on:
      postgres:
        condition: service_healthy

  seq:
    image: datalust/seq:latest
    restart: unless-stopped
    environment:
      ACCEPT_EULA: "Y"
      SERVICE_URL_SEQ_80:
      SEQ_FIRSTRUN_ADMINUSERNAME: admin
      # 冒號後留空:由後端於部署時產生隨機密碼寫入 Coolify Env Vars 注入
      SEQ_FIRSTRUN_ADMINPASSWORD:
    expose:
      - "80"
    volumes:
      - seq-data:/data

volumes:
  postgres-data:
    name: ${COMPOSE_PROJECT_NAME}-postgres-data
  seq-data:
    name: ${COMPOSE_PROJECT_NAME}-seq-data
```

> `alembic` service 的 `command:` 為陣列形式的 CLI 參數(非 shell 變數),不違反「`command` 禁用 `${VAR}`」規則。Alembic 透過 `DATABASE_URL` 連線,並在 `backend/alembic/env.py` 內自動把 `+asyncpg` 改為 `+psycopg` 走 sync driver(plpgsql `$$` block 與 multi-statement SQL 需要 sync 連線才能正確執行)。

> `seq` 為標準集中式 Log 服務:`SEQ_FIRSTRUN_ADMINPASSWORD:` 冒號後留空,由後端於部署時產生隨機密碼寫入 Coolify Environment Variables 注入;**不**對 `seq` 設 healthcheck(`datalust/seq` 鏡像未必有 `curl` / `wget`,易卡死),改以 `depends_on` 串聯。應用程式透過 `SEQ_INGESTION_URL`(compose 內走 `http://seq`)以 SDK 推送 CLEF log;未設此變數時 logger 應 fallback 至 console。詳見 [Docker-Compose-Spec-v1.3](https://github.com/Jiaye-DF/AI-Spec/blob/main/Coolify-Deploy/Docker-Compose-Spec-v1.3.md)。

## 5. 環境變數注入策略

| 階段 | 變數來源 |
| --- | --- |
| 本機開發 | 專案根目錄 `.env`（由 `.env.example` 複製填寫） |
| Coolify 部署 | **Coolify 後台 Environment Variables**；`.env` **禁止**上傳至正式環境 |

- 敏感資訊（`JWT_SECRET`、`ENCRYPTION_KEY`、`INITIAL_ADMIN_PASSWORD`、`POSTGRES_PASSWORD`）一律於 Coolify 後台填寫。OpenRouter 原生 API Key **不**以環境變數注入，改由 admin 於後台建立部門層級 Key（AES-256-GCM 加密存 DB）。
- `SERVICE_URL_*` 變數無需手動填值，Coolify 於部署時自動注入對應公開網址。
- 環境變數新增流程詳見 [60-naming-env.md](./60-naming-env.md)。

## 6. 部署流程

1. 本機以 `docker compose -f docker-compose.dev.yml up --build` 驗證所有服務可正常啟動、Migration 成功執行、Swagger (`/api/docs`) 可存取。
2. Push 至 Git（`main` 或部署分支）。
3. Coolify 偵測變更 → 拉取 → Build → 部署。
4. 監控 Coolify 的**部署 Log** 與**應用程式 Log**，確認：
   - Alembic Migration 無錯誤(`alembic` service exit code = 0)
   - Backend 啟動後 Swagger 可存取
   - Frontend 可呼叫 Backend `/api/v1/...`
   - OpenRouter Proxy 試打一次低成本模型確認通路
5. 若部署失敗，對照 [Docker-Compose-Spec-v1.3](https://github.com/Jiaye-DF/AI-Spec/blob/main/Coolify-Deploy/Docker-Compose-Spec-v1.3.md) 的 Troubleshooting 表排查。

## 7. 常見陷阱對照

| 問題 | 原因 | 處理 |
| --- | --- | --- |
| 服務間無法互連 | 定義了 `networks:` | 移除，交由 Coolify 管理 |
| 變數為空 | 使用 `${VAR:?error}` | 改用 `${VAR}` |
| SERVICE_URL 無值 | 冒號後寫了內容 | 保持冒號後為空白 |
| DB 連不上 | 對 TCP 服務套用 SERVICE_URL | 改用 `DATABASE_URL` / service 名稱 |
| 重新部署後資料消失 | Volume 未命名 | Volume 加 `name:` |
| 外部無法存取 | 缺少 `expose:` | 於 service 加 `expose:` |
