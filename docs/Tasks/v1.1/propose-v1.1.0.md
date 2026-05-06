# Propose v1.1.0 · Models 管理與同步

> 此為 **proposal**(規劃草案),確認後即轉為正式 [`tasks-v1.1.0.md`](./tasks-v1.1.0.md)。
>
> 原 8 個開放問題已收斂為決議結果(見 § 11)。

## 1. 目標

用於限制使用者可呼叫的 **model 模型**以及對應的**使用方式**:

- 由 admin 在後台**集中控管**哪些模型可被使用者透過代理端呼叫。
- 模型清單**以 OpenRouter 為事實來源**,平台僅做選擇與註記,**不**自行維護模型本體。
- **模型分級系統**(model tiers)由 admin 可 CRUD,作為下一版「角色 / Skill / 配額」限制的接點。

## 2. 動機與背景

v1.0 的限制能力極弱:

- 模型白名單只有**全域** `ALLOWED_MODELS` 環境變數(逗號分隔字串),改一次就要重啟容器。
- 沒有「模型描述、context length、計費」等元資料,管理員需自行查 OpenRouter 文件。
- 沒有**部門/使用者/Skill** 維度的限制(本版本暫不展開,但**資料模型必須預留**)。
- OpenRouter 帳號餘額沒有可視化,管理員不知道金鑰用量狀況。

v1.1 將模型白名單由「環境變數字串」升級為「DB 驅動的可管理清單」,提供 OpenRouter 同步機制以維持資料新鮮度,並把同步 OpenRouter 帳號餘額一起做掉。同步**先採手動觸發**(後台「同步」按鈕,10 分鐘限流),自動排程留待後續版本。

## 3. 範圍

### In Scope

- **`models`** 表 — 模型主檔。**單一 `is_active` 旗標**(預設 TRUE),同時表達「OpenRouter 仍提供 + 平台允許使用」。
- **`model_tiers`** 表 — 模型分級主檔,admin 可 CRUD;支援自訂分級數量(N 層皆可),不再硬編 4 級。
- **`openrouter_keys`** 既有表加 4 欄 — 追蹤 OpenRouter 餘額/限額/Free Tier 旗標/同步時間。
- **`usage_logs`** 既有表加 `model_uid` FK — 對齊 `models.model_uid`,保留原 `model` 字串作 fallback。
- **同步流程**(同一個按鈕觸發兩件事):
  - `GET /api/v1/models` → upsert `models`(同步**不**覆寫 `is_active` 與 `tier_key`,保留 admin 選擇)
  - `GET /auth/key` 對每把 active OR Key → 回填 `openrouter_keys` 餘額欄位
- **Admin 後台頁面**:
  - `/admin/models`:列表 / toggle `is_active` / 編輯 `tier_key` / 觸發同步(含 10 分鐘 cooldown 倒數)
  - `/admin/model-tiers`:tier CRUD(label / 顏色 / 排序 / 自動匹配價格區間)
  - `/admin/openrouter-keys`:既有頁面新增餘額欄位顯示
- **代理端白名單檢查**:`ALLOWED_MODELS` env **完全移除**;改查 `models WHERE openrouter_model_id=? AND is_active=TRUE AND is_deleted=FALSE`。
- **前端「同步」按鈕**:含 debounce + 10 分鐘 cooldown 顯示倒數,防雙擊。

### Out of Scope(留待後續版本)

- 部門 / 使用者級的模型授權對應表(`department_models` / `user_models`)。
- Token / Cost 配額(日 / 月上限)。
- Skill 系統(後續會以 `skills.model_uid` 關聯本表;`skills.allowed_tier_key` 限制可用分級)。
- Cron 自動同步、模型更動 webhook 通知。
- 模型別名(short alias → OpenRouter id)。
- **角色 ↔ tier 強制執行**(本版只儲存 tier,不執行限制邏輯)。

## 4. 流程概要

```
admin                  Backend                       OpenRouter
  │                       │                              │
  │ 1. 點「同步」(10 min  │                              │
  │    cooldown 已通過)   │                              │
  ├──────────────────────▶│                              │
  │                       │ 2. acquire advisory lock     │
  │                       │ 3. GET /models               │
  │                       ├─────────────────────────────▶│
  │                       │ 4. 200 { data:[...] }        │
  │                       │◀─────────────────────────────│
  │                       │ 5. upsert models             │
  │                       │    依 model_tiers 自動分級   │
  │                       │ 6. 對每把 active OR Key:     │
  │                       │    GET /auth/key             │
  │                       ├─────────────────────────────▶│
  │                       │◀─────────────────────────────│
  │                       │ 7. update openrouter_keys    │
  │                       │ 8. 寫稽核 + release lock     │
  │ 9. 回列表(已更新)    │                              │
  │◀──────────────────────│                              │
  │                       │                              │
  │ 10. toggle is_active /│                              │
  │     編輯 tier_key     │                              │
  ├──────────────────────▶│ 11. update models +稽核     │
  │                       │                              │
              (使用者代理呼叫時)
SDK 呼叫 ──────────────▶ chat handler                    
                          │ 查 models WHERE              
                          │   openrouter_model_id=?      
                          │   AND is_active=TRUE         
                          │   AND is_deleted=FALSE       
                          │ 不通過 → 403 model_forbidden 
```

## 5. 資料模型

### 5.1 `models` 表

```sql
CREATE TABLE models (
    pid                            BIGSERIAL    PRIMARY KEY,
    model_uid                      UUID         NOT NULL UNIQUE,

    -- OpenRouter 識別(僅 sync 寫入,admin 唯讀)
    openrouter_model_id            VARCHAR(128) NOT NULL UNIQUE,  -- "openai/gpt-4o"
    name                           VARCHAR(255) NOT NULL,         -- OpenRouter 原始 name,唯讀
    description                    TEXT,

    -- 規格(僅 sync 寫入)
    context_length                 INT,
    max_completion_tokens          INT,
    modality                       VARCHAR(64),                    -- "text->text" / "text+image->text"
    tokenizer                      VARCHAR(64),

    -- 計費(USD;僅 sync 寫入)
    price_prompt_per_token         NUMERIC(20, 12),
    price_completion_per_token     NUMERIC(20, 12),
    price_image_per_image          NUMERIC(20, 12),
    price_request_flat             NUMERIC(20, 12),

    -- 平台控管(可由 admin 編輯)
    is_moderated                   BOOLEAN      NOT NULL DEFAULT FALSE,
    tier_key                       VARCHAR(32),                    -- 對應 model_tiers.key;NULL = 未分級

    -- 同步追蹤
    openrouter_created_at          TIMESTAMPTZ,
    last_synced_at                 TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    -- 必備欄位
    is_active                      BOOLEAN      NOT NULL DEFAULT TRUE,   -- 平台允許使用 + OR 仍提供
    is_deleted                     BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at                     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at                     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_models_active   ON models (is_active)  WHERE is_deleted = FALSE;
CREATE INDEX idx_models_tier_key ON models (tier_key)   WHERE is_deleted = FALSE;

CREATE TRIGGER trg_models_updated_at
BEFORE UPDATE ON models
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
```

### 5.2 旗標語義(**單一 `is_active`**)

依決議 #2,合併原本 `is_enabled` / `is_active` 為單一 `is_active`:

| 場景 | 行為 |
|---|---|
| 同步發現新模型 | INSERT `is_active = TRUE`(預設可用) |
| 同步發現既有模型 | UPDATE 元資料,但**不覆寫 `is_active` 與 `tier_key`**(保留 admin 選擇) |
| 同步發現 OR 已下架 | UPDATE `is_active = FALSE` |
| Admin 手動 toggle | UPDATE `is_active = T/F` + 稽核 Log |
| 代理端白名單 | `is_active = TRUE AND is_deleted = FALSE` 才放行 |

> **取捨**:無法分辨「admin 手動停用」與「OR 下架」— 但稽核 Log 已記錄變動原因,且代理行為無差異,故合併語義可接受(於 admin UI 列表頁會以 `last_synced_at` 與是否仍出現於最新 OR 同步資料反推來源)。

### 5.3 `model_tiers` 表(新增)

依決議 #7,tier 由 admin 可編輯/新增/刪除,不硬編。

```sql
CREATE TABLE model_tiers (
    pid                            BIGSERIAL    PRIMARY KEY,
    tier_uid                       UUID         NOT NULL UNIQUE,

    key                            VARCHAR(32)  NOT NULL UNIQUE,   -- 對應 models.tier_key;**不可改名**
    label_zh                       VARCHAR(64)  NOT NULL,
    label_en                       VARCHAR(64),
    color                          VARCHAR(16),                     -- Tailwind palette 名或 hex
    sort_order                     INT          NOT NULL DEFAULT 0,

    -- 同步時自動匹配的價格區間(USD/M tokens);NULL = 不參與自動匹配
    auto_match_min_price_per_mtok  NUMERIC(20, 12),
    auto_match_max_price_per_mtok  NUMERIC(20, 12),

    is_active                      BOOLEAN      NOT NULL DEFAULT TRUE,
    is_deleted                     BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at                     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at                     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TRIGGER trg_model_tiers_updated_at
BEFORE UPDATE ON model_tiers
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
```

**Migration 預設 seed**(後台可增刪):

| key | label_zh | label_en | color | sort_order | 區間 USD/M tok |
|---|---|---|---|---|---|
| `free` | 免費 | Free | gray | 10 | `[0, 0]` |
| `cheap` | 經濟 | Cheap | green | 20 | `(0, 1)` |
| `standard` | 標準 | Standard | blue | 30 | `[1, 5)` |
| `expensive` | 高階 | Expensive | orange | 40 | `[5, ∞)` |

**規則**:

- `key` 一旦建立**不得改名**(避免 `models.tier_key` 失聯);label / color / sort_order / 區間皆可編。
- 刪除 tier:若仍有 model 引用 → 400 `tier_in_use`,需先重指派或設 NULL。
- 自動匹配優先級:`sort_order` 升冪掃描,第一個滿足區間的 tier 即為結果;區間重疊以 `sort_order` 較小者勝。

### 5.4 `openrouter_keys` 加欄位(依決議 #4)

```sql
ALTER TABLE openrouter_keys
    ADD COLUMN credits_used_usd       NUMERIC(12, 6),
    ADD COLUMN credits_limit_usd      NUMERIC(12, 6),    -- NULL = 無上限
    ADD COLUMN credits_is_free_tier   BOOLEAN,
    ADD COLUMN credits_synced_at      TIMESTAMPTZ;
```

每把 active OR Key 同步時呼叫 `GET /auth/key`,回填 `data: { label, usage, limit, is_free_tier, ... }`。

### 5.5 `usage_logs` 加欄位(依決議 #1)

```sql
ALTER TABLE usage_logs
    ADD COLUMN model_uid UUID REFERENCES models(model_uid);

CREATE INDEX idx_usage_logs_model_uid_time
    ON usage_logs (model_uid, created_at DESC);
```

- 寫入時:同時寫 `model`(字串,沿用)與 `model_uid`(若該模型存在於 `models` 表)。
- `model_uid` 為 NULL 的情境:極罕見(白名單檢查通常先擋下);保留以容錯。
- **既有歷史資料不回填**,新呼叫起才填。

## 6. 同步流程

### 6.1 觸發與限流(依決議 #6)

- 後台「同步」按鈕 → `POST /api/v1/models/sync`(僅 admin)。
- **後端限流**:
  - `pg_try_advisory_xact_lock(LOCK_KEY_MODELS_SYNC)` 防並發 → 失敗 425 `sync_in_progress`
  - 距上次成功同步 < 10 分鐘 → 425 `sync_throttled`,response `data: { retry_after_seconds: <秒> }`
- **前端限流**:
  - 按鈕 click 後立即 disabled 直到 API 回應(防雙擊)。
  - 收 `sync_throttled` → 依 `retry_after_seconds` 倒數,顯示「同步冷卻中(剩餘 mm:ss)」。
  - 成功後寫 `localStorage.last_sync_ts`,進頁面時重算 cooldown 顯示。

### 6.2 流程

```
1. acquire pg_try_advisory_xact_lock(LOCK_KEY_MODELS_SYNC)
   失敗 → 425 sync_in_progress
2. 檢查 max(models.last_synced_at) 距今 < 10 min → 425 sync_throttled
3. 模型同步:
   3.1 GET /models(任一把 is_active OR Key)
   3.2 對 openrouter_model_id 做 UPSERT:
        - 新模型:INSERT,is_active=TRUE,tier_key=自動匹配 model_tiers
        - 既有:UPDATE 元資料(name / description / context_length / pricing / modality)
                **不覆寫** is_active 與 tier_key
        - DB 有但 API 無:UPDATE is_active=FALSE
        - last_synced_at = NOW()
4. 餘額同步(對每把 is_active OR Key):
   4.1 GET /auth/key(用該 Key 自身)
   4.2 回填 credits_used_usd / credits_limit_usd / credits_is_free_tier / credits_synced_at
   4.3 個別 Key 失敗:跳過該把,記 warning 累計到回應中,**不**整批 rollback
5. 寫稽核 Log
   action="sync_models_and_credits"
   detail={"added":N1,"updated":N2,"deactivated":N3,"credits_synced":N4,"credits_failed":N5}
6. commit + release lock
7. 回 200 { added, updated, deactivated, total, credits_synced, credits_failed, synced_at }
```

### 6.3 錯誤對照

| 情境 | HTTP | detail |
|---|---|---|
| 同步進行中(advisory lock 被持有) | 425 | `sync_in_progress` |
| 距上次同步 < 10 min | 425 | `sync_throttled`(回 `retry_after_seconds`) |
| 全部 OR Key 取得 /models 失敗 | 502 | `openrouter_unavailable` |
| /models 成功但 upsert 失敗 | 500 | `internal_error`(整批 rollback) |
| 個別 OR Key /auth/key 失敗 | — | best-effort 跳過,計入 `credits_failed` |

## 7. API 端點

對齊 [20-backend.md § 3](../../Design-Base/20-backend.md#3-路由與-api-命名)。

### 7.1 `models`

| Method | Path | 認證 | 說明 |
|---|---|---|---|
| GET | `/api/v1/models` | Access | 列表;預設僅看 `is_active=TRUE`;admin 可加 `?include_inactive=1` 看停用;支援 `?modality=`、`?tier_key=` filter |
| GET | `/api/v1/models/{model_uid}` | Access | 單筆 |
| PATCH | `/api/v1/models/{model_uid}` | Access + admin | **僅可編輯** `is_active` 與 `tier_key`(`name`/`description`/計費/規格皆唯讀,以 OpenRouter 為準;依決議 #5) |
| POST | `/api/v1/models/sync` | Access + admin | 觸發同步(含 `/auth/key` 餘額) |

#### PATCH Schema(範例)

```json
{
  "is_active": false,
  "tier_key": "expensive"
}
```

> `name` 不在可編輯欄位內。

### 7.2 `model-tiers`(新增)

| Method | Path | 認證 | 說明 |
|---|---|---|---|
| GET | `/api/v1/model-tiers` | Access | 列表(所有人皆可讀,UI 用) |
| GET | `/api/v1/model-tiers/{tier_uid}` | Access | 單筆 |
| POST | `/api/v1/model-tiers` | Access + admin | 建立(`key` 不可重複,建立後不可改) |
| PATCH | `/api/v1/model-tiers/{tier_uid}` | Access + admin | 編輯 `label_zh` / `label_en` / `color` / `sort_order` / 自動匹配區間 |
| DELETE | `/api/v1/model-tiers/{tier_uid}` | Access + admin | 刪除;若仍有 model 使用 → 400 `tier_in_use`(detail 列出哪幾個 model) |

### 7.3 `openrouter-keys`(擴充既有)

GET 列表/單筆 response 新增 4 欄(僅 admin 可見):

```json
{
  "credits_used_usd":   "1.234567",
  "credits_limit_usd":  "20.0",
  "credits_is_free_tier": false,
  "credits_synced_at":  "2026-05-06T10:23:11Z"
}
```

## 8. 前端 UI

### 8.1 `/admin/models`

- Page Title「模型管理」+ Main Content 卡片(對齊 [11-ui-ux.md](../../Design-Base/11-ui-ux.md))。
- **頂部工具列**:
  - 搜尋框(模型名稱、id 模糊比對)
  - Filter chip:`按可用性:全部 / 已啟用 / 已停用`、`按分級:全部 / free / cheap / standard / expensive / 自訂...`(動態載入 `GET /model-tiers`)、`按 modality`
  - 右側「**同步 OpenRouter**」按鈕(僅 admin):
    - click 後 disabled 直到回應(防雙擊)
    - 成功 → 顯示「下次可同步:09:42 後」倒數
    - 收 `sync_throttled` → 顯示倒數
- **列表**(< xl 卡片式 / >= xl 表格):
  - 欄:`name` / `openrouter_model_id` / `tier_key` 徽章 / `context_length` / `modality` / `prompt 價` / `completion 價` / `is_active` toggle
  - `tier_key` 徽章顏色取自 `model_tiers.color`
  - 點 row → Drawer / Dialog 顯示完整 description 與計費明細,並可編輯 `tier_key`(下拉選單來源 `GET /model-tiers`)
- **同步結果** Toast:「新增 N1、更新 N2、停用 N3、餘額同步 N4(失敗 N5)」

### 8.2 `/admin/model-tiers`(新)

- Sidebar admin 分組新增「模型分級」項。
- 列表欄:`label_zh` / `label_en` / `key` / `color` 預覽 / 自動匹配區間 / `sort_order` / 操作。
- 操作:
  - 編輯(Drawer):label / color(色票)/ sort_order / 區間
  - 刪除(Confirm Dialog):若 `tier_in_use` 錯誤,訊息明示哪幾個 model 使用中,提供「跳轉到模型管理」連結
- 建立 Tier:Content Dialog(`size=md`),欄位 `key`(建立後不可改)/ `label_zh` / `label_en` / `color` / 區間。

### 8.3 `/admin/openrouter-keys`(擴充)

- 列表新增「餘額」欄(僅 admin):
  - 顯示 `credits_used_usd / credits_limit_usd`(若 limit 為 NULL → 顯示「無上限」)
  - 進度條 = used / limit;> 80% 警告色
  - `credits_synced_at` 距今 > 24h 顯示警告色 + tooltip「同步資料過時,請執行模型同步」
  - `credits_is_free_tier=true` 顯示「Free Tier」徽章

## 9. 既有程式改動

### 9.1 Proxy 白名單

```python
async def _check_model_whitelist(db: AsyncSession, model: str) -> Model:
    row = await db.execute(
        select(Model).where(
            Model.openrouter_model_id == model,
            Model.is_active.is_(True),
            Model.is_deleted.is_(False),
        )
    )
    instance = row.scalar_one_or_none()
    if instance is None:
        raise AppError("model_forbidden", code=403)
    return instance
```

> 模型不存在與停用一律 403 `model_forbidden`(避免列舉)。回傳 instance 供 `schedule_usage_log` 取 `model_uid`。

### 9.2 環境變數(依決議 #3)

| 變數 | 變動 |
|---|---|
| `ALLOWED_MODELS` | **完全移除**(從 `.env.example` / `app/core/config.py` 一併刪除) |

`docs/Design-Base/50-openrouter.md` § 6 / § 11 與 `docs/Design-Base/80-permission.md` § 5 中 `ALLOWED_MODELS` 段落均同步刪除。

### 9.3 OpenRouter Client 擴充

[backend/app/clients/openrouter/client.py](../../../backend/app/clients/openrouter/client.py):

```python
async def list_models(self) -> list[dict]:
    """GET /models;回傳 data[]。使用任一把 active OR Key。"""

async def get_key_info(self, api_key: str) -> dict:
    """GET /auth/key;回傳 { label, usage, limit, is_free_tier }。"""
```

### 9.4 Usage Log 寫入

[backend/app/services/proxy.py](../../../backend/app/services/proxy.py) `schedule_usage_log` 多吃 `model_uid: UUID | None`,寫入新欄位。

## 10. 與 Design-Base 對齊

| Design-Base 章節 | 本版相依/影響 |
|---|---|
| [30-database.md § 1 必備欄位](../../Design-Base/30-database.md#1-必備欄位) | `models` / `model_tiers` 沿用必備欄位 |
| [30-database.md § Trigger](../../Design-Base/30-database.md) | 沿用 `set_updated_at` Trigger |
| [50-openrouter.md § 6](../../Design-Base/50-openrouter.md#6-請求改寫與欄位過濾) | 白名單檢查改 DB 來源,`ALLOWED_MODELS` 段落刪除 |
| [50-openrouter.md § 9](../../Design-Base/50-openrouter.md#9-錯誤對應) | 新增 `sync_in_progress` / `sync_throttled` / `tier_in_use` |
| [50-openrouter.md § 11](../../Design-Base/50-openrouter.md#11-設定與健康檢查) | `ALLOWED_MODELS` 完全刪除 |
| [80-permission.md § 4](../../Design-Base/80-permission.md#4-管理端資源存取規則) | 新增「模型 / 模型分級 / OpenRouter 餘額」資源 |
| [80-permission.md § 5](../../Design-Base/80-permission.md#5-代理端proxy存取規則) | `ALLOWED_MODELS` 行刪除,改述為「`models.is_active` 全域控管」 |
| [80-permission.md § 9](../../Design-Base/80-permission.md#9-稽核-log) | sync / model PATCH / tier CRUD 均寫稽核 |
| [11-ui-ux.md § Sidebar](../../Design-Base/11-ui-ux.md) | admin 分組新增「模型管理」、「模型分級」 |
| [20-backend.md § 1](../../Design-Base/20-backend.md#1-統一-response-格式) | 全部端點走 ApiResponse |

## 11. 決議結果(原 8 個開放問題)

| # | 問題 | **決議** |
|---|---|---|
| 1 | `usage_logs.model` 是否改為 `model_uid` FK? | **加 FK + 保留字串 fallback**(雙寫) |
| 2 | 新模型 `is_enabled` 預設? | **合併 `is_enabled`/`is_active` 為單一 `is_active`,新模型預設 TRUE** |
| 3 | `ALLOWED_MODELS` env 是否保留? | **完全移除** |
| 4 | 同步是否同時呼叫 `/auth/key`? | **同步;在 `openrouter_keys` 加 4 欄;個別失敗 best-effort** |
| 5 | `models.name` 是否允許 admin 改寫? | **唯讀,以 OpenRouter 為準** |
| 6 | 同步間隔限制? | **後端 10 min(`sync_throttled`)+ 前端 cooldown 倒數 + 防雙擊** |
| 7 | `tier` 自動分級閾值? | **獨立 `model_tiers` 表,admin 可 CRUD,N 級可擴充;自動匹配走表內價格區間** |
| 8 | `tier` 是否做覆寫保護? | **同步只在新增時自動匹配,既有 `tier_key` 不被覆寫** |

## 12. Definition of Done

- [ ] Migration `V8__models.sql` 建立 `models` 表
- [ ] Migration `V9__model_tiers.sql` 建立 `model_tiers` 表 + seed 4 級
- [ ] Migration `V10__openrouter_keys_credits.sql` ALTER `openrouter_keys` +4 欄
- [ ] Migration `V11__usage_logs_model_uid.sql` ALTER `usage_logs` + `model_uid` + index
- [ ] OpenRouter Client 新增 `list_models()` / `get_key_info()`
- [ ] 同步 service:advisory lock + 10 min throttle + 模型 upsert + 餘額同步 + 計數
- [ ] `/api/v1/models` CRUD-lite + sync 端點齊全,Swagger `/api/docs` 可見
- [ ] `/api/v1/model-tiers` CRUD 端點齊全
- [ ] `/api/v1/openrouter-keys` 列表/單筆 response 加 4 欄
- [ ] `/admin/models` 列表 / toggle / 編輯 tier / 同步按鈕含 cooldown 倒數
- [ ] `/admin/model-tiers` CRUD 頁
- [ ] `/admin/openrouter-keys` 列表新增餘額欄位
- [ ] Proxy 白名單改 DB 查詢 + 回傳 model 供 usage log 取 uid;`ALLOWED_MODELS` 從 `.env.example` 與 `config.py` 完全移除
- [ ] 同步、PATCH、Toggle、tier CRUD 均寫稽核 Log
- [ ] 50-openrouter.md / 80-permission.md / 11-ui-ux.md 同步更新(含刪除 `ALLOWED_MODELS` 段落)
- [ ] 整合測試:同步流程(全新建表 / 既有更新 / 下架 / 失敗 rollback)、10 min throttle、餘額部分失敗、白名單拒絕、tier CRUD 唯一性、tier_in_use 阻擋刪除

## 13. 與後續版本的銜接(資訊性,不在本版實作)

### 13.1 解決「便宜任務誤呼叫昂貴模型」

`tier_key` 欄位是這類限制的接點。下一版可選的三種落地路徑(預估難度遞增):

| 路徑 | 規則 | 對使用者影響 |
|---|---|---|
| **A. 角色 ↔ tier 對應**(最簡) | 在 `users.role` / 部門級新增「最高可用 tier」<br>例如一般員工 ≤ `standard`,主管 ≤ `expensive` | 直接呼叫高階模型 → 403 `model_tier_forbidden` |
| **B. Skill 綁模型**(最乾淨) | Skills 系統落地後,使用者**只能跑 Skill**(不開放自由 prompt + 自選模型);Skill 由 admin 預先綁定模型與最大 tokens | 使用者不再有 model 選擇權,自動避免誤用 |
| **C. 單次呼叫 cost 上限**(行為驅動) | 每次呼叫前依 `text` 長度估 prompt tokens × tier 單價,超過部門設定 → 拒絕 | 動態保護,不阻止偶發合理用例 |

> 三者**可並存**:A 是硬天花板,B 是預設使用方式,C 是兜底。

### 13.2 配額(v1.2 候選)

`models` 表可預留 `default_max_request_tokens` 欄位,作為使用者單次呼叫上限的預設值;部門 / 使用者層覆寫由新表處理。

### 13.3 Skills(v1.x 候選)

`skills` 將以 `(skill_uid, model_uid, prompt_template, default_max_tokens, allowed_tier_key)` 結構落地;`model_uid` FK 至 `models.model_uid`,`allowed_tier_key` 對應 `model_tiers.key`。Skill 層的限制以該 FK 與 `allowed_tier_key` 為準,不再走全域白名單。

### 13.4 動態定價快照

每次 sync 可額外寫一筆 `model_pricing_snapshots`(若需要長期成本趨勢分析),本版不做。
