# Propose v1.2.0 · 本地模型支援 + 速率限制 + 代理 endpoint 收斂

> 此為 **proposal**(規劃草案),確認後即轉為正式 [`tasks-v1.2.0.md`](./tasks-v1.2.0.md)。
>
> 對應母本:[v1.1 已落地的 Models 管理](../v1.1/propose-v1.1.0.md)。

## 1. 目標

三件事一次做掉:

1. **支援企業內部地端 OpenAI-compatible 模型**(vLLM / Ollama / TGI / LiteLLM 等),控管邏輯與 OpenRouter 等同。
2. **加入「每把 Key 速率限制」**:每分鐘最大呼叫數(RPM)+ 最小請求間隔(min interval),避免地端 server 被打爆,同時讓 OpenRouter 走 Free Tier / Paid Tier 不同限額時可分別設定。
3. **代理 endpoint 收斂**:把 `/api/v1/model/openrouter/chat` 收斂成 `/api/v1/model/chat`,舊路徑保留 deprecated alias。

使用者端 SDK 程式碼**完全不變**:同樣 endpoint、同樣 `X-SDK-Key` + `X-User-Token`,只是 `model` 字串換成本地模型 id。

## 2. 動機

- **機密資料不能送外網** → 需要支援地端模型;自架 server 多半 OpenAI-compatible,client 程式碼可重用。
- **地端 GPU 並發有限**(常見 RPM 30~60),直接讓 SDK 任意呼叫易 OOM。
- **OpenRouter 每把 Key 也有限額**(Free Tier 20 RPM),目前被動撞 429。
- 代理 path `/api/v1/model/openrouter/chat` 把 provider 寫死,擴充後語意混亂。

v1.2 用 **RPM + 最小間隔**在代理層主動限速,同時收斂 endpoint。

## 3. 範圍

### In Scope

**Schema**:
- `models` 加 `provider` 欄位(`openrouter` / `internal`,預設 `openrouter`);`openrouter_model_id` 改名為 `model_key`
- `openrouter_keys` 加 `rpm_limit` / `min_request_interval_ms`(0 = 不限)
- 新 env 區塊 `INTERNAL_LLM_*`(base_url / api_key / RPM / 最小間隔 / wait timeout / request timeout)

**後端**:
- 新增 `clients/internal/`(OpenAI-compatible)、`clients/factory.py`、`services/rate_limit.py`
- `proxy.py` 依 `provider` 分流;進入 client 前過 rate limiter(規則見 § 6)
- `POST /api/v1/models` 手動建立 internal 模型;`PATCH` 對 internal 開放更多欄位;`/models/sync` 只動 openrouter

**Endpoint**:
- 新 canonical `POST /api/v1/model/chat`;舊 `/model/openrouter/chat` 維持 deprecated alias

**前端**:
- `/admin/models` 加 provider 徽章 + 「手動新增本地模型」按鈕 + Drawer 條件欄位
- `/admin/openrouter-keys` 加 RPM / interval 顯示與編輯
- `/user-guide` 更新 endpoint + 錯誤碼 + 本地模型段落

### Out of Scope(留待後續版本)

- 多台地端 server(`internal_providers` 表)→ v1.3
- Redis-backed rate limiter(跨 worker)→ v1.3;本版限 `UVICORN_WORKERS=1`
- Streaming proxy(SSE)、Internal cost 估算、部門 ↔ provider 對應
- 模型層級 RPM(本版只在 Key / Provider 層限速)

## 4. 流程概要

```
SDK ─POST /api/v1/model/chat───▶ chat handler
                                  │
                                  │ 1. 認證(X-SDK-Key + X-User-Token,沿用)
                                  │ 2. 查白名單:models WHERE model_key=? AND is_active=TRUE
                                  │
                                  ├─ provider=openrouter ─▶ pick active OR Key
                                  │                         │
                                  │                         ▼
                                  │                    rate_limiter[or_key_uid].acquire(timeout=0)
                                  │                         │
                                  │                         ├─ 通過 → POST OpenRouter /chat/completions
                                  │                         └─ 拒絕 → 換下一把 Key (failover);全部拒絕 → 429 rate_limited
                                  │
                                  └─ provider=internal ────▶ rate_limiter[INTERNAL].acquire(timeout=RATE_WAIT_TIMEOUT)
                                                            │
                                                            ├─ 通過(可能 sleep)→ POST {INTERNAL_LLM_BASE_URL}/chat/completions
                                                            └─ 超時 → 429 internal_busy
```

關鍵差異:

- **OpenRouter**:有多把 Key,撞限額**換下一把**(failover),不 sleep。
- **Internal**:單一 endpoint,撞限額**等待**至下一個 slot 釋放,超過 `RATE_WAIT_TIMEOUT` 才 429。

## 5. 資料模型

### 5.1 `models` 表 — 加 `provider` + 改名

```sql
ALTER TABLE models
    ADD COLUMN provider VARCHAR(32) NOT NULL DEFAULT 'openrouter';

ALTER TABLE models RENAME COLUMN openrouter_model_id TO model_key;
ALTER INDEX models_openrouter_model_id_key RENAME TO models_model_key_key;

CREATE INDEX idx_models_provider ON models (provider) WHERE is_deleted = FALSE;
```

| 欄位 | 語意 |
| --- | --- |
| `provider` | `openrouter` / `internal`;未來可擴充 `azure_openai` 等 |
| `model_key` (was `openrouter_model_id`) | 平台識別模型的 key;openrouter 存 OR id,internal 存 admin 自訂(慣例 `internal/<name>`) |

> **注意**:不在此表加 `max_concurrent_requests` 或 `rpm`。速率控管放在「Key / Provider」層級而非「Model」層級,因為瓶頸是 server / Key 配額,不是模型本身。

### 5.2 `openrouter_keys` 表 — 加 RPM + 最小間隔

```sql
ALTER TABLE openrouter_keys
    ADD COLUMN rpm_limit               INT NOT NULL DEFAULT 0,    -- 0 = 不限
    ADD COLUMN min_request_interval_ms INT NOT NULL DEFAULT 0;    -- 0 = 不限

ALTER TABLE openrouter_keys
    ADD CONSTRAINT chk_openrouter_keys_rpm CHECK (rpm_limit >= 0),
    ADD CONSTRAINT chk_openrouter_keys_min_interval CHECK (min_request_interval_ms >= 0);
```

| 欄位 | 預設 | 說明 |
| --- | --- | --- |
| `rpm_limit` | `0` | `0` = 不限;否則為「最近 60 秒最大呼叫數」 |
| `min_request_interval_ms` | `0` | `0` = 不限;否則為「上次呼叫起算最短間隔(毫秒)」 |

**典型設定範例**:

| 場景 | rpm_limit | min_request_interval_ms |
| --- | --- | --- |
| OpenRouter Free Tier | 20 | 200 |
| OpenRouter 付費 | 200 | 0 |
| 不限速(現況) | 0 | 0 |

### 5.3 `usage_logs` 欄位語意(不改 schema)

internal 呼叫時:

- `openrouter_key_uid` = **NULL**(internal 不走 OR Key pool)
- `cost_usd` = `0`(本版不做 internal cost 估算)
- 其他欄位照常寫入

## 6. 速率限制(本版核心)

### 6.1 設計

兩個維度疊加,**先檢查最小間隔,再檢查 RPM**:

1. **最小間隔**:若 `(now - last_request_ts) < min_request_interval_ms` → 必須等到時間補足
2. **RPM**:若最近 60 秒已有 `rpm_limit` 次呼叫 → 必須等到最舊那筆「滑出視窗」

**儲存粒度與 fallback 行為**:

| Provider | 計數粒度 | 設定來源 | 撞限額時的行為 |
| --- | --- | --- | --- |
| OpenRouter | per-Key(`openrouter_key_uid`) | `openrouter_keys` 表 | **failover** 換下一把 active Key;全部撞牆 → 429 `rate_limited` |
| Internal | per-provider(目前單一,key=`"INTERNAL"`) | `.env` 全域 | **等待**直到下一個 slot;超過 `INTERNAL_LLM_RATE_WAIT_TIMEOUT` → 429 `internal_busy` |

**為什麼不混用兩種行為**:OR 有 pool 所以 failover 是天然解;internal 單台沒得換,只能排隊等。等待是 internal 場景下的合理行為(避免直接打爆 GPU)。

### 6.2 演算法(in-memory,asyncio)

放在 `app/services/rate_limit.py` 的 `KeyRateLimiter`,核心邏輯:

1. 維護 `deque[float]` 儲存最近 60 秒「已預訂」的呼叫時間戳。
2. `acquire(wait_timeout)` 在 `asyncio.Lock` 內完成:
   - 清除 60 秒前的舊時間戳
   - 計算需等待秒數 = `max(min_interval_wait, rpm_window_wait)`
   - 若 wait > `wait_timeout` → 拋 `RateLimitExceeded(retry_after_seconds=...)`
   - 預訂 slot(`deque.append(now + wait)`)、更新 `last_request_ts`,釋鎖
3. 釋鎖後才 `asyncio.sleep(wait)`,避免阻塞其他 Key 的 limiter。
4. FIFO 由「預訂發生在鎖內」保證(先進來的先拿到較早的 slot)。

實作細節(完整 pseudo-code)留到 [`tasks-v1.2.0.md`](./tasks-v1.2.0.md) 再展開。

### 6.3 整合到 proxy

`proxy.run_chat` 在 `_check_model_whitelist` 之後,依 `model_row.provider` 走兩條路徑:

- **`internal`**:`rate_limiter[INTERNAL].acquire(wait_timeout=INTERNAL_LLM_RATE_WAIT_TIMEOUT)`,捕到 `RateLimitExceeded` 直接 raise `internal_busy` 429,帶 `retry_after_seconds`。
- **`openrouter`**:迴圈 `pick_random_active`,每把 Key 都 `acquire(wait_timeout=0)`(不 sleep);拿不到就 `tried.add` 換下一把。全部 Key 都撞牆 → raise `rate_limited` 429。

### 6.4 設定變更生效時機

`openrouter_keys` PATCH 更新後**下一個 acquire 自動讀新值**(limiter 從 `key_row` 即時取 `rpm_limit` / `min_request_interval_ms`,不快取參數),不需要重啟。

## 7. API 端點

> **Response 格式**:所有新端點皆沿用 [docs/Design-Base/20-backend.md § 1](../../Design-Base/20-backend.md#1-統一-response-格式) 的 `ApiResponse`(`success` / `code` / `data` / `detail`),由 `app/core/response.py` 的 `success_response()` / `failure_response()` 包裝。錯誤碼若需帶結構化 payload(例 `internal_busy` 的 `retry_after_seconds`),放在 `data` 欄位,前端可 `error.data.retry_after_seconds` 解析。

**成功範例**:

```json
{ "success": true, "code": 200, "data": { ... }, "detail": "success" }
```

**失敗範例**(internal 排隊超時):

```json
{ "success": false, "code": 429, "data": { "retry_after_seconds": 23 }, "detail": "internal_busy" }
```

### 7.1 代理 path 收斂

| Method | Path | 認證 | 說明 |
| --- | --- | --- | --- |
| POST | `/api/v1/model/chat` | SDK Key + User Token | **新 canonical**,所有 provider 共用 |
| POST | `/api/v1/model/openrouter/chat` | 同上 | **Deprecated alias**;Swagger 標 `deprecated: true` |

> 舊 path 保留**至少 2 個 minor 版本**;v1.4 前不刪。

### 7.2 模型 CRUD 擴充

| Method | Path | 認證 | 變動 |
| --- | --- | --- | --- |
| POST | `/api/v1/models` | Admin | **新增**(本版):僅接受 `provider=internal`;openrouter 必須走同步 |
| PATCH | `/api/v1/models/{uid}` | Admin | **擴充**:internal 可改 `name` / `description` / `context_length` / `tier_key` / `is_active`;openrouter 維持 v1.1(僅 `tier_key` / `is_active`) |
| POST | `/api/v1/models/sync` | Admin | **行為不變**:只同步 `provider=openrouter`;internal 完全不動 |

#### POST `/api/v1/models` Request

```json
{
  "provider": "internal",
  "model_key": "internal/llama3-70b",
  "name": "Llama 3 70B (內部)",
  "description": "vLLM,4-bit 量化",
  "context_length": 8192,
  "tier_key": "free",
  "modality": "text->text"
}
```

### 7.3 `openrouter_keys` PATCH 擴充

新增可編輯欄位 `rpm_limit` / `min_request_interval_ms`:

```json
{
  "is_active": true,
  "rpm_limit": 20,
  "min_request_interval_ms": 200
}
```

### 7.4 新增錯誤碼

| 碼 | HTTP | data | 觸發 |
| --- | --- | --- | --- |
| `internal_busy` | 429 | `{retry_after_seconds: N}` | internal 等待超過 `RATE_WAIT_TIMEOUT` |
| `rate_limited` | 429 | — | OpenRouter 全部 active Key 都撞限額 (沿用既有錯誤碼,擴充觸發情境) |
| `internal_unavailable` | 502 | — | internal server 連線失敗 / 5xx |
| `provider_misconfigured` | 500 | — | 模型 provider=internal 但 env 沒設 `INTERNAL_LLM_BASE_URL` |
| `provider_not_allowed` | 400 | — | POST `/api/v1/models` 傳 `provider=openrouter` |

## 8. 環境變數

`.env.example` 新增區塊:

```dotenv
# --- Internal LLM (本地 OpenAI-compatible server) ---
INTERNAL_LLM_BASE_URL=                          # 例:http://vllm.corp.local:8000/v1;留空 = 停用本地模型
INTERNAL_LLM_API_KEY=                           # 可空(內網信任)
INTERNAL_LLM_REQUEST_TIMEOUT=120                # 單次呼叫 httpx timeout(秒)

# Internal 速率限制(全域,本版單台 server)
INTERNAL_LLM_RPM_LIMIT=60                       # 每分鐘最大呼叫數(0 = 不限)
INTERNAL_LLM_MIN_REQUEST_INTERVAL_MS=0          # 連續呼叫最小間隔(毫秒;0 = 不限)
INTERNAL_LLM_RATE_WAIT_TIMEOUT=60               # 撞限額時最長等待秒數,超過 → 429 internal_busy
```

`app/core/config.py` 對應加 6 個 Settings 欄位。

## 9. 前端 UI

### 9.1 `/admin/models`

- 列表加 `provider` 徽章欄(openrouter 藍 / internal 紫)
- 工具列新增「**手動新增本地模型**」按鈕,Dialog 欄位:`model_key` / `name` / `description` / `context_length` / `tier_key` / `modality`(不含 RPM)
- 編輯 Drawer 依 `provider` 開放欄位(規則見 § 7.2)
- 同步按鈕 tooltip 註明「不影響本地模型」

### 9.2 `/admin/openrouter-keys`

- 列表加 `RPM` / `最小間隔` 兩欄(`0` 顯示「不限」)
- 新增 / 編輯 Dialog 加對應 2 個 number 欄位,placeholder「0 = 不限」,tooltip 解釋疊加效果

### 9.3 `/user-guide`

- endpoint 範例改為 `POST /api/v1/model/chat`
- 新增「本地模型」小節(同 header,僅換 `model` 字串)
- 錯誤對照表加 `internal_busy` / `rate_limited`,建議實作端用指數退避

## 10. 既有程式改動(高階)

**後端**:

- `alembic/versions/0002_*.py`:`models` 加 `provider` + rename `openrouter_model_id`→`model_key`;`openrouter_keys` 加 RPM / interval 2 欄 + CHECK
- `models/` + `schemas/` + `repositories/`:同步更新欄名與新欄位
- `clients/internal/`(新):OpenAI-compatible client
- `clients/factory.py`(新):依 provider 回 client
- `services/rate_limit.py`(新):`KeyRateLimiter` 與 registry
- `services/proxy.py`:`run_chat` refactor,分流 + rate limiter
- `services/sync.py`:upsert 加 `WHERE provider='openrouter'`
- `api/v1/`:`model_openrouter.py` → `model_chat.py`(新路徑 + alias);`models.py` 加 POST
- `core/config.py`:`INTERNAL_LLM_*` 6 個設定

**前端**:

- `types/api.ts`:`Model` / `OpenRouterKey` 對應新欄位
- `(main)/admin/models/page.tsx`:provider 徽章 + 手動新增 Dialog + Drawer 條件欄位
- `(main)/openrouter-keys/page.tsx`:列表與 Dialog 加 RPM / interval
- `(main)/user-guide/page.tsx`:endpoint 範例 + 錯誤碼 + 本地模型段落

> 完整檔案路徑、import 列、refactor 細節由 [`tasks-v1.2.0.md`](./tasks-v1.2.0.md) 拆分時逐項展開。

## 11. 與 Design-Base 對齊

| Design-Base 章節 | 本版相依/影響 |
| --- | --- |
| [20-backend.md § 1 統一 Response 格式](../../Design-Base/20-backend.md#1-統一-response-格式) | 所有新端點走 `ApiResponse`,結構化錯誤 payload 放 `data` |
| [20-backend.md § 3 路由與 API 命名](../../Design-Base/20-backend.md) | model path 解耦 openrouter;deprecated alias 政策需明文化 |
| [30-database.md § 5 Migration](../../Design-Base/30-database.md#5-migration) | 新 Alembic revision(加欄位 + rename + CHECK) |
| [50-openrouter.md](../../Design-Base/50-openrouter.md) | 改寫為涵蓋多 provider(或拆出 51-internal.md);新增「速率限制」小節 |
| [60-naming-env.md § 2.1](../../Design-Base/60-naming-env.md) | `.env.example` 新增 `# --- Internal LLM ---` 區塊 |
| [80-permission.md § 5 代理端 Proxy 存取規則](../../Design-Base/80-permission.md#5-代理端proxy存取規則) | endpoint path 收斂;白名單仍是 `models.is_active` |
| [90-task-spec.md](../../Design-Base/90-task-spec.md) | tasks-v1.2 對齊本 propose |

## 12. 已決議

對話過程中已收斂的設計決策(實作時直接套用,不再 challenge):

| # | 項目 | 決議 |
| --- | --- | --- |
| D1 | 代理 endpoint 命名 | 統一為 `/api/v1/model/chat`;舊 `/api/v1/model/openrouter/chat` 保留為 deprecated alias |
| D2 | 速率控管粒度 | **per-Key / per-Provider**(OR 放 `openrouter_keys` 表,Internal 放 env);不放 `models` 表 |
| D3 | API 回應格式 | 沿用 `ApiResponse`(`success` / `code` / `data` / `detail`),結構化錯誤 payload 放 `data` |

## 13. 開放問題(待決議)

| # | 問題 | 推薦方向 |
| --- | --- | --- |
| Q1 | RPM 撞限額,OR 與 Internal 行為不同(failover vs 等待)— OK? | **OK**;OR 有 pool 才用 failover,Internal 單台只能等 |
| Q2 | `min_request_interval_ms` 與 `rpm_limit` 哪個優先? | **疊加**(取兩者所需等待時間的較大者) |
| Q3 | 設定變動是否需要重啟? | **不需要**;rate limiter 每次 acquire 讀當前資料 |
| Q4 | `openrouter_model_id` 改名 `model_key`? | **改**;此欄已不只屬於 OpenRouter |
| Q5 | multi-worker 怎麼辦? | **本版限制 `UVICORN_WORKERS=1`**;Redis 版留 v1.3 |
| Q6 | 本地模型 cost? | **本版固定 0** |
| Q7 | `provider` 欄位 enum vs varchar? | **varchar**;擴新 provider 不必動 DDL |
| Q8 | 多台地端 server? | **本版單台用 env**;多台 → v1.3 `internal_providers` 表 |

## 14. Definition of Done

**Schema 與後端**:

- [ ] Alembic migration:`models.provider` + rename `model_key`;`openrouter_keys` 加 RPM / interval + CHECK
- [ ] `clients/internal/`、`clients/factory.py`、`services/rate_limit.py` 新檔完成
- [ ] `proxy.py` 分流(OR failover / Internal 等待)+ usage_log 適配 internal

**API**:

- [ ] `POST /api/v1/models`(僅 provider=internal)
- [ ] `PATCH /api/v1/models/{uid}` / `PATCH /api/v1/openrouter-keys/{uid}` 條件性欄位
- [ ] `POST /api/v1/model/chat` 新路徑 + 舊 deprecated alias 仍可用
- [ ] Swagger `/api/docs` 兩條 chat path 可見(舊標 deprecated)

**前端**:

- [ ] `/admin/models`:provider 徽章 / 手動新增 Dialog / Drawer 條件欄位
- [ ] `/admin/openrouter-keys`:RPM / interval 顯示與編輯
- [ ] `/user-guide`:endpoint + 錯誤碼 + 本地模型段落

**測試**(關鍵情境;細項拆到 tasks):

- [ ] `KeyRateLimiter` 單元測試:RPM 視窗、最小間隔、等待超時、視窗滑動
- [ ] OR Key 撞 RPM → failover 下一把;全部撞牆 → `rate_limited`
- [ ] Internal 撞 RPM → 延遲後成功;超過 `RATE_WAIT_TIMEOUT` → `internal_busy`
- [ ] Internal server 5xx → `internal_unavailable`;env 未設 + 有 internal model → `provider_misconfigured`

**文件**:

- [ ] `.env.example` 加 `INTERNAL_LLM_*` 區塊
- [ ] `50-openrouter.md` 涵蓋多 provider 與速率限制;`80-permission.md` / `20-backend.md` endpoint 段落同步

## 15. 後續版本(資訊性,不在本版實作)

| 版本 | 主題 |
| --- | --- |
| v1.3 候選 | 多地端 server(`internal_providers` 表)+ Redis-backed rate limiter(解除單 worker 限制) |
| v1.4 候選 | Streaming proxy(SSE) |
| v1.x 候選 | 部門 ↔ provider 對應、Internal cost 估算、觀察性(`usage_logs.rate_wait_ms`) |
