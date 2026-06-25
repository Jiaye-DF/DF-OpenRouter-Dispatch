# Tasks v1.1.0

## 版本資訊

- 前置依賴:v1.0.0(MVP — 後端 FastAPI、前端 Next.js、Flyway V1-V7、SDK 雙因子代理與 OpenRouter 實打驗證)
- 本版本範圍:Models 管理與 OpenRouter 同步 — 將模型白名單由 env 升級為 DB 驅動,支援 admin 後台管理、自動分級、OpenRouter 帳號餘額同步
- 對齊的 Design-Base 章節:
  - [30-database.md § 1 必備欄位](../../Design-Base/30-database.md#1-必備欄位)
  - [50-openrouter.md § 6 請求改寫與欄位過濾](../../Design-Base/50-openrouter.md#6-請求改寫與欄位過濾)
  - [50-openrouter.md § 9 錯誤對應](../../Design-Base/50-openrouter.md#9-錯誤對應)
  - [50-openrouter.md § 10 用量紀錄](../../Design-Base/50-openrouter.md#10-用量紀錄usage-log)
  - [50-openrouter.md § 11 設定與健康檢查](../../Design-Base/50-openrouter.md#11-設定與健康檢查)
  - [80-permission.md § 4 管理端資源存取規則](../../Design-Base/80-permission.md#4-管理端資源存取規則)
  - [80-permission.md § 5 代理端Proxy存取規則](../../Design-Base/80-permission.md#5-代理端proxy存取規則)
  - [80-permission.md § 9 稽核 Log](../../Design-Base/80-permission.md#9-稽核-log)
  - [11-ui-ux.md § Sidebar](../../Design-Base/11-ui-ux.md)
  - [20-backend.md § 1 統一 Response 格式](../../Design-Base/20-backend.md#1-統一-response-格式)
- 母本 propose:[`propose-v1.1.0.md`](./propose-v1.1.0.md)(包含設計推導與決議過程)

> 本 Tasks 為**實作契約**;設計理由與替代方案請參考母本 propose。內容若與 propose 衝突,以本檔為準。

## Definition of Done

### Migration
- [x] `V8__models.sql` 建立 `models` 表 + index + Trigger(沿用 [30-database.md § 1](../../Design-Base/30-database.md#1-必備欄位) 必備欄位)
- [x] `V9__model_tiers.sql` 建立 `model_tiers` 表 + Trigger + seed 4 級(`free`/`cheap`/`standard`/`expensive`)
- [x] `V10__openrouter_keys_credits.sql` ALTER `openrouter_keys` 加 4 欄(`credits_used_usd` / `credits_limit_usd` / `credits_is_free_tier` / `credits_synced_at`)
- [x] `V11__usage_logs_model_uid.sql` ALTER `usage_logs` 加 `model_uid` UUID FK + index

### Backend
- [x] OpenRouter Client 新增 `list_models()` 與 `get_key_info(api_key)`
- [x] `app/services/sync.py`(新)封裝:advisory lock + 10 min throttle + 模型 upsert + 餘額同步 + 自動分級匹配 + 計數
- [x] `/api/v1/models`(GET 列表 / GET 單筆 / PATCH / POST sync)4 端點齊全
- [x] `/api/v1/model-tiers` CRUD 5 端點齊全
- [x] `/api/v1/openrouter-keys` GET response 加 4 欄餘額(僅 admin 可見)
- [x] `app/services/proxy.py` `_check_model_whitelist` 改 DB 查詢,回傳 `Model` instance 供 `schedule_usage_log` 取 `model_uid`
- [x] `schedule_usage_log` 接受 `model_uid: UUID | None` 並寫入新欄位
- [x] `app/core/config.py` 移除 `ALLOWED_MODELS` 設定與 `allowed_models_list` property;`.env.example` 同步移除
- [x] 同步 / model PATCH / model toggle / tier CRUD 均寫稽核 Log
- [x] Swagger 可於 `/api/docs` 查閱所有新端點

### Frontend
- [x] `/admin/models` 頁面:列表 / `tier` 徽章 / `is_active` toggle / Drawer 編輯 tier
- [x] `/admin/models` 同步按鈕含 cooldown 倒數(成功與 `sync_throttled` 兩種來源同邏輯處理;localStorage 持久化 `last_sync_ts`)
- [x] `/admin/model-tiers`(新)CRUD 頁面 — 列表 / 建立 Dialog / 編輯 Drawer / 刪除 Confirm(含 `tier_in_use` 錯誤訊息)
- [x] `/admin/openrouter-keys` 列表新增餘額欄(進度條 + Free Tier 徽章 + > 24h 警告色)
- [x] Sidebar admin 分組新增「模型管理」、「模型分級」項

### Design-Base 文件同步
- [x] [50-openrouter.md § 6](../../Design-Base/50-openrouter.md#6-請求改寫與欄位過濾) 白名單檢查描述改為「DB 查 `models.is_active`」,刪除 `ALLOWED_MODELS` 行
- [x] [50-openrouter.md § 9](../../Design-Base/50-openrouter.md#9-錯誤對應) 加 `sync_in_progress`/`sync_throttled`/`tier_in_use` 行
- [x] [50-openrouter.md § 11](../../Design-Base/50-openrouter.md#11-設定與健康檢查) 移除 `ALLOWED_MODELS` 段
- [x] [80-permission.md § 4](../../Design-Base/80-permission.md#4-管理端資源存取規則) 表新增「模型 / 模型分級 / OpenRouter 餘額」資源行
- [x] [80-permission.md § 5](../../Design-Base/80-permission.md#5-代理端proxy存取規則) `ALLOWED_MODELS` 行刪除,改述為「`models.is_active` 全域控管」
- [x] [11-ui-ux.md § Sidebar](../../Design-Base/11-ui-ux.md) admin 分組新增「模型管理」、「模型分級」

### 測試
- [x] 整合測試:同步流程(全新建表 / 既有更新 / OR 下架 / 上游失敗 rollback)
- [x] 整合測試:10 min throttle(後端 425 + 前端 cooldown)
- [x] 整合測試:餘額部分失敗 best-effort
- [x] 整合測試:白名單拒絕(不存在 / 停用 / 軟刪除 三種情境均回 403 `model_forbidden`)
- [x] 整合測試:tier CRUD 唯一性、`tier_in_use` 阻擋刪除、自動匹配優先級

## 功能設計

### 功能 A:`models` 表與同步
- Schema:[propose § 5.1](./propose-v1.1.0.md)
- 同步流程:[propose § 6](./propose-v1.1.0.md)
- 旗標語義:單一 `is_active`,合併「OR 仍提供 + 平台允許使用」雙語義(詳 [propose § 5.2](./propose-v1.1.0.md))

### 功能 B:`model_tiers` 表與自動分級
- Schema 與 seed:[propose § 5.3](./propose-v1.1.0.md)
- 自動匹配:`sort_order` 升冪掃描,第一個滿足 `[auto_match_min, auto_match_max)` 的 tier 即為結果;區間重疊以 sort_order 較小者勝
- `key` 建立後**不可改名**(避免 `models.tier_key` 失聯);label / color / sort_order / 區間可編
- 自動分級**僅在新增**(INSERT)模型時生效;既有 `tier_key` 不被覆寫

### 功能 C:OpenRouter 帳號餘額同步
- ALTER:[propose § 5.4](./propose-v1.1.0.md)
- 對每把 active OR Key 呼叫 `GET /auth/key`,回填 4 欄
- 個別失敗 best-effort,計入 `credits_failed`,**不**整批 rollback

### 功能 D:`usage_logs.model_uid` 雙寫
- ALTER:[propose § 5.5](./propose-v1.1.0.md)
- 寫入時:同寫 `model`(字串)與 `model_uid`(若該模型存在於 `models`)
- 既有歷史**不回填**

### 功能 E:Proxy 白名單由 DB 驅動
- 詳細:[propose § 9.1](./propose-v1.1.0.md)
- `ALLOWED_MODELS` env **完全移除**

### 功能 F:Admin 後台三頁
- UI 詳細:[propose § 8](./propose-v1.1.0.md)

## 錯誤處理對照表

| 情境 | HTTP | `detail` | 觸發位置 |
|---|---|---|---|
| 模型不存在於 `models` 表 | 403 | `model_forbidden` | proxy whitelist |
| 模型 `is_active=FALSE` | 403 | `model_forbidden` | proxy whitelist |
| 同步進行中(advisory lock 被持有) | 425 | `sync_in_progress` | sync service |
| 距上次同步 < 10 min | 425 | `sync_throttled`(`data.retry_after_seconds`) | sync service |
| 全部 OR Key 取得 `/models` 失敗 | 502 | `openrouter_unavailable` | sync service |
| `/models` 成功但 upsert 失敗 | 500 | `internal_error`(整批 rollback) | sync service |
| 個別 OR Key `/auth/key` 失敗 | — | best-effort 跳過,計入 `credits_failed` | sync service |
| 刪除 `model_tier` 仍有 model 引用 | 400 | `tier_in_use`(`data.using_models[]`) | tier service |
| 建立 `model_tier` 時 `key` 重複 | 400 | `tier_key_taken` | tier service |
| 一般使用者觸碰 admin 端點 | 403 | `forbidden` | `require_admin` Dependency |

## 敏感欄位過濾

(對齊 [90-task-spec.md § 4.3](../../Design-Base/90-task-spec.md#43-敏感欄位))

| 表 / 欄位 | 過濾規則 |
|---|---|
| `models` 全欄位 | 無敏感資訊,所有登入使用者皆可讀 |
| `model_tiers` 全欄位 | 無敏感資訊 |
| `openrouter_keys.credits_*` 4 欄 | **僅 admin 可見**;一般使用者 GET 必須剔除 |
| `openrouter_keys.key_ciphertext` / `key_prefix` 等既有欄位 | 沿用 v1.0 規則(明文禁回傳) |
| 同步流程 OpenRouter Key 明文 | **禁止**寫入稽核 Log 或 response;使用 `decrypt_key` 取值後立即回收 |

## 用量與稽核

(對齊 [80-permission.md § 9](../../Design-Base/80-permission.md#9-稽核-log))

### 稽核 Log

| action | target_type | target_uid | detail 內容 |
|---|---|---|---|
| `sync_models_and_credits` | `NULL` | `NULL` | `{added, updated, deactivated, credits_synced, credits_failed}` |
| `update_model` | `model` | `model_uid` | 變動前後值的 `is_active` / `tier_key` |
| `create_model_tier` | `model_tier` | `tier_uid` | 建立時的 `key` + `label_zh` |
| `update_model_tier` | `model_tier` | `tier_uid` | 變動前後值 |
| `delete_model_tier` | `model_tier` | `tier_uid` | 被刪除的 `key` |

### Usage Log
- 既有寫入點維持(對齊 [50-openrouter.md § 10](../../Design-Base/50-openrouter.md#10-用量紀錄usage-log))。
- 新增 `model_uid` 欄位寫入(`schedule_usage_log` 接收 `model_uid` 參數)。
- `model_uid` 為 NULL 的情境僅在白名單拒絕(極少見);此時仍寫一筆 `status=error error_code=model_forbidden`。

## 交付物清單

### 後端檔案

| 動作 | 路徑 |
|---|---|
| 新增 | `backend/app/models/model.py`、`backend/app/models/model_tier.py` |
| 新增 | `backend/app/schemas/model.py`、`backend/app/schemas/model_tier.py` |
| 新增 | `backend/app/repositories/model.py`、`backend/app/repositories/model_tier.py` |
| 新增 | `backend/app/services/sync.py`(advisory lock + throttle + upsert + 餘額同步 + 自動分級) |
| 新增 | `backend/app/api/v1/models.py`(列表 / 單筆 / PATCH / sync) |
| 新增 | `backend/app/api/v1/model_tiers.py`(CRUD) |
| 修改 | `backend/app/api/v1/openrouter_keys.py`(response 加 4 欄,僅 admin) |
| 修改 | `backend/app/api/v1/__init__.py`(註冊新 router) |
| 修改 | `backend/app/clients/openrouter/client.py`(新增 `list_models`、`get_key_info`) |
| 修改 | `backend/app/services/proxy.py`(白名單 → DB;`schedule_usage_log` 收 `model_uid`) |
| 修改 | `backend/app/core/config.py`(移除 `ALLOWED_MODELS` 與 `allowed_models_list`) |
| 修改 | `backend/app/models/__init__.py`(import `Model` / `ModelTier`) |
| 新增 | `backend/tests/test_models_sync.py`、`test_model_tiers_crud.py`、`test_proxy_whitelist_db.py` |

### 前端檔案

| 動作 | 路徑 |
|---|---|
| 新增 | `frontend/src/app/(main)/admin/models/page.tsx` |
| 新增 | `frontend/src/app/(main)/admin/model-tiers/page.tsx` |
| 修改 | `frontend/src/app/(main)/admin/openrouter-keys/page.tsx`(列表加餘額欄) |
| 修改 | `frontend/src/lib/api/endpoints.ts`(加 `models` / `model-tiers` 端點常數) |
| 修改 | `frontend/src/types/api.ts`(加 `Model` / `ModelTier` / `Credit` 型別) |
| 修改 | `frontend/src/components/layout/Sidebar.tsx`(admin 分組新增 2 項) |
| 新增 | `frontend/src/components/admin/SyncButton.tsx`(含 cooldown 倒數的可重用元件) |

### Migration

| 檔名 | 內容 |
|---|---|
| `migrations/V8__models.sql` | 建立 `models` 表 + index + Trigger |
| `migrations/V9__model_tiers.sql` | 建立 `model_tiers` 表 + Trigger + seed 4 級 |
| `migrations/V10__openrouter_keys_credits.sql` | ALTER `openrouter_keys` 加 4 欄 |
| `migrations/V11__usage_logs_model_uid.sql` | ALTER `usage_logs` 加 `model_uid` + index |

### 環境變數

| 動作 | key | 備註 |
|---|---|---|
| **移除** | `ALLOWED_MODELS` | `.env.example` / `.env` / `app/core/config.py` 一併刪除 |

## 自我檢核(對齊 [90-task-spec.md § 6](../../Design-Base/90-task-spec.md#6-檢核清單))

- [x] 文件結構符合 § 2(版本資訊 / DoD / 功能設計 / 交付物清單)
- [x] 已完成 § 3 前置檢查(已讀 Design-Base / 列出對齊章節 / 無衝突 / `.env.example` 同步 / Migration 同步 / OpenRouter 對齊)
- [x] Response Schema 符合 § 4.1(Pydantic 明確定義、UID 對外、過濾敏感欄位)
- [x] API 路徑符合 § 4.2(管理端 kebab-case 複數)
- [x] 已明列敏感欄位過濾表
- [x] 已附錯誤處理對照表
- [x] 代理端功能已說明 `usage_logs` 寫入;管理端異動已說明稽核 Log
- [x] 未觸犯 § 5 禁止事項
