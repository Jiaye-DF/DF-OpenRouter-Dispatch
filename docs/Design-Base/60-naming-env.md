# 60 · 命名、環境變數與 Git 流程

本文件定義跨前後端共用的命名慣例、環境變數管理流程與 Git 操作規範。

## 1. 命名慣例

| 類型 | 規範 | 範例 |
| --- | --- | --- |
| 前端元件 | PascalCase | `MessageDialog.tsx` |
| 前端 hook | `use` 前綴 camelCase | `useCurrentUser.ts` |
| 前端檔案 | kebab-case 或 PascalCase（元件） | `api-client.ts`、`Card.tsx` |
| 後端 Python 檔 | snake_case | `api_key_service.py` |
| 後端類別 | PascalCase | `ApiKeyService` |
| 後端函式 / 變數 | snake_case | `get_current_user` |
| DB 資料表 | snake_case **複數** | `api_keys`、`usage_logs`、`users` |
| DB 欄位 | snake_case（實體單數） | `is_active`、`api_key_uid`、`user_uid` |
| API path | kebab-case 複數 | `/api-keys`、`/usage-logs` |
| 環境變數 | SCREAMING_SNAKE_CASE | `OPENROUTER_API_KEY` |

## 2. 環境變數管理

- 所有環境變數**必須**同步登記於 `.env.example`（空值）與本機 `.env`（實際值）。
- `.env` 由 `.gitignore` 排除，**禁止** commit。
- 新增變數流程：
  1. 先在 `.env.example` 加上 key（含分區註解）。
  2. 在 `.env` 填入本機值。
  3. 程式碼透過 `pydantic-settings` 讀取（後端）或 `NEXT_PUBLIC_*`（前端）。
  4. 若涉及部署，通知使用者在 Coolify 後台 Environment Variables 同步加入。
- 敏感資訊（Token、密碼、連線字串、API Key）**必須**透過環境變數注入；**禁止**寫死於程式碼或 Compose。
- 若發現疑似敏感資訊出現於程式碼或 commit，**必須**立即提醒使用者處理。

### 2.1 本專案環境變數分區

`.env.example` **應**以下列分區註解組織，便於快速檢視：

```dotenv
# --- App ---
APP_ENV=
LOG_LEVEL=

# --- Backend / Uvicorn ---
UVICORN_WORKERS=

# --- Database ---
POSTGRES_DB=
POSTGRES_USER=
POSTGRES_PASSWORD=
DATABASE_URL=

# --- Flyway ---
FLYWAY_URL=
FLYWAY_USER=
FLYWAY_PASSWORD=
FLYWAY_LOCATIONS=

# --- Auth / Security ---
JWT_SECRET=
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRES_MINUTES=15
REFRESH_TOKEN_EXPIRES_DAYS=7
ACCESS_COOKIE_NAME=access_token
REFRESH_COOKIE_NAME=refresh_token
ENCRYPTION_KEY=
CORS_ORIGINS=

# --- Auth / Admin Bootstrap ---
INITIAL_ADMIN_ACCOUNT=
INITIAL_ADMIN_USERNAME=
INITIAL_ADMIN_PASSWORD=

# --- OpenRouter ---
OPENROUTER_API_BASE_URL=
OPENROUTER_API_TIMEOUT=
OPENROUTER_STREAM_TIMEOUT=

# --- Frontend ---
NEXT_PUBLIC_API_BASE_URL=
```

## 3. Git 工作流程

- 主分支為 `main`，新功能**必須**從 `main` 切出 feature branch 開發。
- Commit Message 使用**繁體中文**，格式 `<類型>: <描述>`。
  - 類型：`Add` / `Modify` / `Fix` / `Refactor` / `Docs`
- AI 產生的 commit 一律加 `(AI)` 前綴，例：`(AI) Add: 新增本地金鑰管理功能`。
- **未經使用者允許**，**禁止**破壞性操作：`--force`、`reset --hard`、`--no-verify`、`push --force`、`branch -D` 等。
- **禁止**將 `.env`、credentials、OpenRouter Key 等敏感檔案 commit 進版控。

## 4. 自訂指令

專案的 Claude Code 自訂指令集中於 `.claude/commands/`：

| 指令 | 說明 |
| --- | --- |
| `/commit-all` | 一鍵提交並推送當前分支所有變更 |
| `/merge-main` | 合併當前分支至 `main` |
| `/scan-project` | 掃描專案結構並分析潛在問題 |
| `/dev-up` | 一鍵啟動本機開發環境 |
