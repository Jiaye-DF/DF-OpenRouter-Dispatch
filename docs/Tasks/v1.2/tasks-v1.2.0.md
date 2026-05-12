# Tasks v1.2.0

## 版本資訊

- 前置依賴:v1.1.0(Models 管理 — DB 驅動白名單、模型分級、OR 餘額同步、AppError data 結構化)
- 本版本範圍:本地模型(OpenAI-compatible)支援 + Key 級速率限制(RPM + 最小間隔) + 代理 endpoint 收斂(`/api/v1/model/chat`)
- 對齊的 Design-Base 章節:
  - [20-backend.md § 1 統一 Response 格式](../../Design-Base/20-backend.md#1-統一-response-格式)
  - [20-backend.md § 3 路由與 API 命名](../../Design-Base/20-backend.md)
  - [30-database.md § 5 Migration](../../Design-Base/30-database.md#5-migration)
  - [50-openrouter.md § 6 請求改寫與欄位過濾](../../Design-Base/50-openrouter.md#6-請求改寫與欄位過濾)
  - [50-openrouter.md § 9 錯誤對應](../../Design-Base/50-openrouter.md#9-錯誤對應)
  - [50-openrouter.md § 10 用量紀錄](../../Design-Base/50-openrouter.md#10-用量紀錄usage-log)
  - [60-naming-env.md § 2 環境變數管理](../../Design-Base/60-naming-env.md#2-環境變數管理)
  - [80-permission.md § 5 代理端Proxy存取規則](../../Design-Base/80-permission.md#5-代理端proxy存取規則)
  - [90-task-spec.md § 4.2 API 路徑](../../Design-Base/90-task-spec.md)
- 母本 propose:[`propose-v1.2.0.md`](./propose-v1.2.0.md)(包含設計推導與決議過程)

> 本 Tasks 為**實作契約**;設計理由與替代方案請參考母本 propose。內容若與 propose 衝突,以本檔為準。

## Definition of Done

### Migration

- [ ] Alembic revision `0002_*` 一次完成下列 DDL:
  - `models` 加 `provider VARCHAR(32) NOT NULL DEFAULT 'openrouter'`
  - `models` rename column `openrouter_model_id` → `model_key`(同步 rename unique index)
  - `models` 加 `CREATE INDEX idx_models_provider ON models (provider) WHERE is_deleted = FALSE`
  - `openrouter_keys` 加 `rpm_limit INT NOT NULL DEFAULT 0`
  - `openrouter_keys` 加 `min_request_interval_ms INT NOT NULL DEFAULT 0`
  - `openrouter_keys` 加 `CHECK (rpm_limit >= 0)` 與 `CHECK (min_request_interval_ms >= 0)`

### Backend

#### Schema 同步
- [ ] `app/models/model.py`:`provider` 屬性、`openrouter_model_id` 改名 `model_key`(SQLAlchemy)
- [ ] `app/models/openrouter_key.py`:`rpm_limit` / `min_request_interval_ms` 屬性
- [ ] `app/schemas/model.py`:
  - `ModelRead` 加 `provider` / `model_key`(取代 `openrouter_model_id`)
  - 新增 `ModelCreateRequest`(provider 限 `internal`)
  - `ModelPatch` 依 provider 條件性開放欄位驗證(同步 `app/api/v1/models.py` PATCH 端點)
- [ ] `app/schemas/openrouter_key.py`:`OpenRouterKeyResponse` / `OpenRouterKeyCreateRequest` / `OpenRouterKeyUpdateRequest` 加 RPM/interval
- [ ] `app/repositories/model.py`:`find_by_openrouter_model_id` → `find_by_key`
- [ ] `app/services/sync.py`:upsert 加 `WHERE provider='openrouter'`,internal 列不動

#### 新模組
- [ ] `app/clients/internal/__init__.py` + `client.py`:OpenAI-compatible client(`chat_completion()` + `httpx.HTTPError` 包裝為 `InternalError`)
- [ ] `app/clients/factory.py`:`get_chat_client(provider)` 依 provider 回 OR/internal client
- [ ] `app/services/rate_limit.py`:
  - `RateLimitExceeded(Exception)` 含 `retry_after_seconds`
  - `KeyRateLimiter`(`acquire(wait_timeout)` 行為見 [propose § 6.2](./propose-v1.2.0.md#62-演算法in-memoryasyncio))
  - module-level registry `get(key, rpm_limit, min_interval_ms)` → 取或建 limiter
- [ ] `app/services/proxy.py` `run_chat` refactor:
  - 依 `model_row.provider` 分流
  - `internal`:`rate_limiter.get(INTERNAL_KEY, env_rpm, env_min_interval).acquire(wait_timeout=env_RATE_WAIT)`;捕 `RateLimitExceeded` → raise `AppError("internal_busy", 429, data={"retry_after_seconds": ...})`
  - `openrouter`:迴圈內 `acquire(wait_timeout=0)`,捕到就換下一把 Key;全撞牆 → raise `AppError("rate_limited", 429)`
  - usage_log 對 internal:`openrouter_key_uid=None`、`cost_usd=0`

#### 設定
- [ ] `app/core/config.py` 加 6 個 `INTERNAL_LLM_*` 設定欄位
- [ ] `.env.example` 新增 `# --- Internal LLM ---` 區塊與 6 個 key

#### API
- [ ] `app/api/v1/model_openrouter.py` rename `model_chat.py`,prefix 改 `/model`,路徑 `/chat`(canonical)
- [ ] 同檔保留 deprecated alias router:`prefix="/model/openrouter"`,內部 forward 到同一 handler;Swagger 加 `deprecated=True`
- [ ] `app/api/v1/models.py` 新 `POST /api/v1/models`(僅 admin;body provider 必為 `internal`,否則 `provider_not_allowed`)
- [ ] `app/api/v1/models.py` `PATCH` 依 provider 動態驗證可改欄位(internal:`name`/`description`/`context_length`/`tier_key`/`is_active`;openrouter 沿用 v1.1 只准 `tier_key`/`is_active`)
- [ ] `app/api/v1/openrouter_keys.py` `PATCH` 接受 `rpm_limit` / `min_request_interval_ms`
- [ ] 所有新端點 response 走 `success_response()` / `failure_response()`

### Frontend

- [ ] `frontend/src/types/api.ts`:
  - `Model` 加 `provider: "openrouter" | "internal"`、`model_key`(取代 `openrouter_model_id`)
  - `OpenRouterKey` 加 `rpm_limit` / `min_request_interval_ms`
- [ ] `frontend/src/lib/api/endpoints.ts` 加 `models` POST、調整 chat endpoint 為 `/api/v1/model/chat`(若 SDK 端有用到)
- [ ] `frontend/src/lib/api/error-map.ts` 加 `internal_busy` / `internal_unavailable` / `provider_misconfigured` / `provider_not_allowed` 中文化
- [ ] `/admin/models` 頁面:
  - 列表加 `provider` 徽章欄(openrouter 藍 / internal 紫)
  - 工具列新增「**手動新增本地模型**」按鈕 + Dialog(`model_key` / `name` / `description` / `context_length` / `tier_key` / `modality`)
  - 編輯 Drawer 依 provider 切換可編輯欄位
- [ ] `/admin/openrouter-keys` 頁面:
  - 列表加 `RPM` / `最小間隔` 欄(`0` 顯示「不限」)
  - 新增 / 編輯 Dialog 加對應 2 個 number 欄位(placeholder「0 = 不限」+ tooltip 解釋疊加)
- [ ] `/user-guide` 頁面:
  - endpoint 範例改為 `POST /api/v1/model/chat`
  - 加「本地模型」段落(同 header,僅 `model` 字串不同)
  - 錯誤對照表加 `internal_busy` / `rate_limited`(指數退避建議)

### Design-Base 文件同步

- [ ] [20-backend.md § 3](../../Design-Base/20-backend.md):新增「**代理端 path 收斂**」段落,允許 `/api/v1/model/<action>` 形式(deprecated alias 政策)
- [ ] [50-openrouter.md](../../Design-Base/50-openrouter.md):範圍擴大為「Model Provider」(或新增 51-internal.md);新增「速率限制」與「Internal Provider」小節
- [ ] [50-openrouter.md § 9](../../Design-Base/50-openrouter.md#9-錯誤對應):加 `internal_busy` / `internal_unavailable` / `provider_misconfigured` / `provider_not_allowed`
- [ ] [80-permission.md § 5](../../Design-Base/80-permission.md#5-代理端proxy存取規則):path 從 `/model/openrouter/chat` 改為 `/model/chat`(舊路徑說明 deprecated alias)
- [ ] [90-task-spec.md § 4.2](../../Design-Base/90-task-spec.md):API 路徑規則放寬,代理端允許 `/api/v1/model/<action>`(不再強制 `model/openrouter/`)
- [ ] [60-naming-env.md § 2.1](../../Design-Base/60-naming-env.md):分區註解範例加 `# --- Internal LLM ---`

### 測試

- [ ] **單元測試** `tests/services/test_rate_limit.py`:
  - 連續 N+1 次 acquire(N=rpm_limit),第 N+1 次需等待至視窗釋出
  - `min_request_interval_ms=200` 時連續兩次間隔不少於 200ms
  - 等待 > `wait_timeout` → `RateLimitExceeded` + 正確 `retry_after_seconds`
  - 60 秒視窗滑動正確(超過 60s 舊時間戳被清除)
- [ ] **整合測試**:
  - OpenRouter 模型呼叫不受影響(回歸 v1.1)
  - Internal 模型成功呼叫一次(mock `INTERNAL_LLM_BASE_URL`)
  - OR Key `rpm_limit=2`,連 3 次第 3 次自動切下一把
  - OR 所有 Key 撞牆 → 429 `rate_limited`
  - Internal `RPM_LIMIT=2`,連 3 次第 3 次延遲執行成功
  - Internal 等待 > `RATE_WAIT_TIMEOUT` → 429 `internal_busy` + `retry_after_seconds`
  - Internal server 5xx → 502 `internal_unavailable`
  - Env 未設 `INTERNAL_LLM_BASE_URL` 但有 internal model 被呼叫 → 500 `provider_misconfigured`
  - 同步流程不動 internal 模型(`provider='internal'` 的 row `last_synced_at` 不變)
- [ ] Swagger `/api/docs`:兩條 chat path 皆可見(`/model/openrouter/chat` 標 deprecated)

## 功能設計

### 功能 A:`models.provider` 與 `model_key` 改名
- Schema 與既有資料 backfill:[propose § 5.1](./propose-v1.2.0.md#51-models-表--加-provider--改名)
- internal 必須走 `POST /api/v1/models` 手動建立(openrouter 不可手動建)

### 功能 B:`openrouter_keys` 速率欄位
- Schema 與典型設定範例:[propose § 5.2](./propose-v1.2.0.md#52-openrouter_keys-表--加-rpm--最小間隔)
- 預設 `0 = 不限`(向後相容,既有 Key 行為不變)

### 功能 C:`KeyRateLimiter` 速率限制器
- 演算法骨架:[propose § 6.2](./propose-v1.2.0.md#62-演算法in-memoryasyncio)
- 兩個維度疊加:`wait = max(min_interval_wait, rpm_window_wait)`
- FIFO 順序由「預訂發生在鎖內」保證;釋鎖才 sleep
- 設定變更後**下一個 acquire 自動讀新值**,不需要重啟

### 功能 D:Proxy 分流
- 流程:[propose § 4](./propose-v1.2.0.md#4-流程概要) + [propose § 6.3](./propose-v1.2.0.md#63-整合到-proxy)
- OR 撞限額 → failover;Internal 撞限額 → 等待 → 超時 429

### 功能 E:Internal client 與 factory
- OpenAI-compatible `/chat/completions` 同 OR 既有 client schema
- httpx 連線失敗 / 5xx → `InternalError` → AppError `internal_unavailable` 502
- 在 `run_chat` 入口檢查:若 model.provider=internal 且 `INTERNAL_LLM_BASE_URL` 空 → 500 `provider_misconfigured`

### 功能 F:代理 endpoint 收斂
- 新 canonical `POST /api/v1/model/chat`;舊 `/model/openrouter/chat` deprecated alias
- 舊路徑保留**至少到 v1.4**

### 功能 G:Admin UI 三頁改動
- 詳細:[propose § 9](./propose-v1.2.0.md#9-前端-ui)

## 錯誤處理對照表

| 情境 | HTTP | `detail` | `data` | 觸發位置 |
| --- | --- | --- | --- | --- |
| Internal 等待超過 `RATE_WAIT_TIMEOUT` | 429 | `internal_busy` | `{retry_after_seconds: N}` | `proxy.run_chat` |
| OR 所有 active Key 撞速率限制 | 429 | `rate_limited` | — | `proxy.run_chat` |
| Internal server 連線失敗 / 5xx | 502 | `internal_unavailable` | — | `clients/internal/client.py` |
| Provider=internal 但 env 沒設 base_url | 500 | `provider_misconfigured` | — | `proxy.run_chat` 入口 |
| POST `/api/v1/models` body provider=openrouter | 400 | `provider_not_allowed` | — | `api/v1/models.py` |
| 模型不存在 / 停用 / 軟刪除 | 403 | `model_forbidden` | — | proxy whitelist(沿用 v1.1) |

## 交付物清單

- **後端**:
  - 新增:`backend/alembic/versions/0002_provider_rate_limit.py`、`backend/app/clients/internal/{__init__.py,client.py}`、`backend/app/clients/factory.py`、`backend/app/services/rate_limit.py`、`backend/tests/services/test_rate_limit.py`
  - 改名:`backend/app/api/v1/model_openrouter.py` → `model_chat.py`
  - 修改:`models/{model,openrouter_key}.py`、`schemas/{model,openrouter_key}.py`、`repositories/model.py`、`services/{proxy,sync}.py`、`api/v1/{models,openrouter_keys,model_chat,__init__}.py`、`core/config.py`
- **前端**:
  - 修改:`types/api.ts`、`lib/api/{endpoints,error-map}.ts`、`app/(main)/admin/models/page.tsx`、`app/(main)/openrouter-keys/page.tsx`、`app/(main)/user-guide/page.tsx`
- **Migration**:`backend/alembic/versions/0002_provider_rate_limit.py`
- **環境變數**(`.env.example` 與 `.env` 同步):
  - `INTERNAL_LLM_BASE_URL`(空 = 停用本地模型)
  - `INTERNAL_LLM_API_KEY`(可空)
  - `INTERNAL_LLM_REQUEST_TIMEOUT=120`
  - `INTERNAL_LLM_RPM_LIMIT=60`
  - `INTERNAL_LLM_MIN_REQUEST_INTERVAL_MS=0`
  - `INTERNAL_LLM_RATE_WAIT_TIMEOUT=60`
- **文件**:`50-openrouter.md` / `20-backend.md § 3` / `80-permission.md § 5` / `90-task-spec.md § 4.2` / `60-naming-env.md § 2.1`
