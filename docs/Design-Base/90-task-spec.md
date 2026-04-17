# 90 · Task 產出規範

本文件規範 `docs/Tasks/v*-p*/Task-v*-p*.md` 的撰寫格式、前置檢查與對齊 Design-Base 的強制流程。所有 AI 協作產出的 Task **必須**符合本規範。

## 1. 適用範圍

- `docs/Tasks/v*-p*/` 目錄下的 Task 文件均適用。命名規則：`v` = version、`p` = process step（例：`v1-p1.0` = 版本 1 第 1.0 步驟）。
- 範例：`docs/Tasks/v1-p1.0/Task-v1-p1.0.md`、`docs/Tasks/v1-p1.1/Task-v1-p1.1.0.md`。
- 一份 Task 文件對應一個版本的交付範圍；跨版本的大型功能**應**拆為多份。
- 同一 process 下的多個子步驟 / 規劃文件（例：`Plan-v1-p1.1.md`、`Task-v1-p1.1.0.md`）統一放置於同一 `docs/Tasks/v*-p*/` 目錄。

## 2. Task 文件結構

每份 Task 文件**必須**包含以下區塊，順序固定：

```markdown
# Task v<版號>

## 版本資訊
- 前置依賴：<列出前版本已完成的功能，或寫「無」>
- 本版本範圍：<一句話摘要>
- 對齊的 Design-Base 章節：
  - [00-overview.md § 技術棧](../../Design-Base/00-overview.md#技術棧)
  - [20-backend.md § 1 統一 Response 格式](../../Design-Base/20-backend.md#1-統一-response-格式)
  - …

## Definition of Done
- [ ] <可驗證的交付條件 1>
- [ ] <可驗證的交付條件 2>
- [ ] Swagger 可於 `/api/docs` 查閱新增 API
- [ ] 單元測試 / 整合測試覆蓋關鍵流程
- [ ] `.env.example` 與 `.env` 同步更新（若有新變數）

## 功能設計
### 功能 A
### 功能 B

## 交付物清單
- 後端檔案：<列出新增 / 修改的路徑>
- 前端檔案：<列出新增 / 修改的路徑>
- Migration：<列出 V{版號}__{描述}.sql>
- 環境變數：<列出新增 key>
```

## 3. 前置檢查（AI 產 Task 前必做）

AI 在產出或修改 `docs/Tasks/v*-p*/Task-v*-p*.md` **之前必須**完成：

1. **閱讀全部 Design-Base 檔案**：`00-overview.md` → `90-task-spec.md`。
2. **確認對齊章節**：在 Task 的「對齊的 Design-Base 章節」列出引用的具體章節錨點，**不得**只寫檔名。
3. **檢查衝突**：Task 的設計**禁止**與 Design-Base 的任何規定衝突；若規範缺漏，**應**先補 Design-Base 再開 Task。
4. **檢查 `.env.example`**：若 Task 涉及新環境變數，**必須**同步於 `.env.example` 加上 key。
5. **檢查 Migration**：若 Task 涉及 DB Schema，**必須**同步產生 Flyway Migration 檔名與編號。
6. **檢查 OpenRouter 整合**：若 Task 涉及代理、模型呼叫或金鑰流，**必須**對齊 [50-openrouter.md](./50-openrouter.md)。

## 4. 產出內容規範

### 4.1 Response Schema

- **必須**使用 Pydantic BaseModel 明確定義，**禁止**使用 `dict` 當 response type。
- 欄位命名對照 [60-naming-env.md § 1](./60-naming-env.md#1-命名慣例)。
- 資料表對外識別**必須**使用 `<table>_uid` (UUIDv7)，**禁止**暴露內部 `pid` 或外部系統 id 作為操作 key（詳見 [30-database.md](./30-database.md)）。

### 4.2 API 路徑

- **必須**以 `/api/v1` 為前綴。
- 管理端**必須**使用 kebab-case 複數（例：`/api-keys`）。
- 代理端**必須**使用 `/api/v1/proxy/<openrouter-path>` 格式（例：`/api/v1/proxy/chat/completions`），以維持與 OpenRouter 相容。
- 單一資源以 UID 作為 path parameter。

### 4.3 敏感欄位

- OpenRouter 原生 API Key、使用者密碼 hash、本地金鑰明文 / hash **禁止**出現於 Response、Log、Commit。
- 從 OpenRouter 回傳的資料若包含內部識別（provider token、route metadata 等），**必須**在 Task 文件中明列「過濾欄位表」，並於後端 response 前剔除。
- 本地金鑰於建立 API **僅一次**明文回傳，後續查詢只能回傳 prefix。Task 設計須明確標註此行為。

### 4.4 錯誤處理

- Task 設計**必須**附上「錯誤處理對照表」，列出主要錯誤情境與 HTTP status code，遵循 [20-backend.md § 2](./20-backend.md#2-錯誤訊息規範) 與 [50-openrouter.md § 9](./50-openrouter.md#9-錯誤對應)。

### 4.5 用量與稽核

- 代理端功能**必須**說明如何寫入 `usage_logs`（對齊 [50-openrouter.md § 10](./50-openrouter.md#10-用量紀錄usage-log)）。
- 管理端異動操作**必須**說明如何寫入稽核 Log（對齊 [80-permission.md § 9](./80-permission.md#9-稽核-log)）。

## 5. 禁止事項

Task 設計**禁止**：

- 引入 Design-Base 未允許的技術棧或套件。
- 繞過統一 Response 格式（`{ success, code, data, detail }`）；串流端點例外，但須以 [20-backend.md § 1](./20-backend.md#1-統一-response-格式) 的方式處理起始錯誤。
- 繞過 Table 設計必備欄位（`pid` / `<table>_uid` / `is_active` / `is_deleted` / `created_at` / `updated_at`）。
- 在前端直接呼叫 OpenRouter API 或繞過後端代理。
- 將外部系統的內部 id（例如 OpenRouter 回傳的 `id`）作為本地 PK 或對外 UID。
- 在管理端接受 `ord_*` 本地金鑰，或在代理端接受管理 Cookie。
- 在 Response、Log、Commit 中洩漏敏感資訊。

## 6. 檢核清單

Task 撰寫完成後，**必須**自我檢核以下項目：

- [ ] 文件結構符合 § 2（版本資訊 / DoD / 功能設計 / 交付物清單）
- [ ] 已完成 § 3 前置檢查（已讀 Design-Base / 列出對齊章節 / 無衝突 / `.env.example` 同步 / Migration 同步 / OpenRouter 對齊）
- [ ] Response Schema 符合 § 4.1（Pydantic 明確定義、UID 對外、過濾敏感欄位）
- [ ] API 路徑符合 § 4.2（管理端 kebab-case 複數；代理端 `/proxy/*`）
- [ ] 已明列敏感欄位過濾表（若涉及 OpenRouter 或金鑰）
- [ ] 已附錯誤處理對照表
- [ ] 代理端功能已說明 `usage_logs` 寫入；管理端異動已說明稽核 Log
- [ ] 未觸犯 § 5 禁止事項
