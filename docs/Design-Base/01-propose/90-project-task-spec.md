# 90 · Task 產出規範(DF-OpenRouter-Dispatch 特有)

> **本檔為本專案特有的 Task 產出規範**(原扁平 `docs/Design-Base/90-task-spec.md`,2026-06-25 遷入)。通用版本工作流(propose / tasks / fixed / changelog / multi-agent)以 HE 的 `01-propose/00-overview.md` ～ `07-rule-evolution.md` 為準;本檔為其**專案專屬補充**(對齊章節、OpenRouter / 稽核 / UID 等本專案硬性檢核)。
> **載入原則改採 HE Just-in-time Loading**:不再要求「讀全部 Design-Base」,改依 `docs/Design-Base/README.md` 的「任務→檔案」對照表按需載入。

本文件規範 `docs/Tasks/v<major>.<minor>/{propose,tasks}-v<major>.<minor>.<patch>.md` 的撰寫格式、前置檢查與對齊 Design-Base 的強制流程。所有 AI 協作產出的 Task **必須**符合本規範。

## 1. 適用範圍與資料夾結構

- 所有版本文件統一放於 `docs/Tasks/v<major>.<minor>/`(**2-digit minor anchor**)。本專案採此式,**有別於** HE 通用模板的 `vX.Y.Z/`(屬 [`00-overview.md`](./00-overview.md) 所載的專案偏離)。**禁止**散落他處或舊式 `v*-p*/`。
- 一個 minor 資料夾**容納該 minor 下所有 patch**;patch 以**檔名** `vX.Y.Z` 區分,**不另開資料夾**。
- 結構:

```
docs/Tasks/v<major>.<minor>/
├── propose-v<major>.<minor>.<patch>.md      # 每個 patch 一份(詳設母本,User 寫;§2.1)
├── workflow/
│   └── workflow-v<major>.<minor>.<patch>.md # 編排計畫(orchestrator 產;§2.2)
├── tasks/
│   └── task-NNN-<slug>.md                   # 逐項可執行任務(orchestrator 產;§2.3)
└── fixed.md                                 # 該版本規範違反 / bug 根因累積(§N 格式;§2.4)
# CHANGELOG.md 置於 repo 根目錄,跨版本對外彙整(§2.5)
```

- 範例:`docs/Tasks/v2.0/propose-v2.0.0.md`、`docs/Tasks/v2.0/workflow/workflow-v2.0.0.md`、`docs/Tasks/v2.0/tasks/task-001-ai-eval-schema.md`。
- 檔名一律小寫 dash 分隔;版號 3-digit semver(判準見 [`05-version-bump.md`](./05-version-bump.md))。
- **propose 為母本**(詳設);同 patch 的 workflow + tasks 為其執行拆解,有歧異以 workflow/tasks 為實作依據。
- v1.0~v1.10 等既有版本已**回溯對齊**本結構:原 `tasks-vX.Y.Z.md` 已移入 `workflow/workflow-vX.Y.Z.md`(版本級契約=編排計畫),v1.6 巢狀 patch 子資料夾已扁平化為同層檔。既有版屬**凍結紀錄**,**不**回溯再切 per-task(`tasks/` 留空);`tasks/` per-task 拆分自 v2.0 起新版適用。

## 2. 文件角色與格式(hybrid:詳設 propose + 編排 workflow + 逐項 tasks)

| 文件 | 角色 | 由誰寫 | 風格 |
| --- | --- | --- | --- |
| `propose-vX.Y.Z.md` | 版本/patch 目標 + **完整設計** | User | 本專案詳設風格(§2.1) |
| `workflow/workflow-vX.Y.Z.md` | 拆解總表 + 並行/依賴 + 執行流程 + DoD | Orchestrator | §2.2 |
| `tasks/task-NNN-*.md` | 單一可執行任務(1–4 hr) | Orchestrator | §2.3(對齊 [`02-task-decomposition.md`](./02-task-decomposition.md)) |
| `fixed.md` | 規範違反 / bug 根因 | Agent 累積 | §N([`04-fixed-format.md`](./04-fixed-format.md) / [`99-code-review/01-fixed-md.md`](../99-code-review/01-fixed-md.md)) |
| `CHANGELOG.md`(repo 根) | 對外 user-facing | Agent/User | [`06-changelog.md`](./06-changelog.md) |

### 2.1 propose-vX.Y.Z.md(詳設母本)

本專案 propose **保留完整設計文件風格**(目標 / 動機 / 範圍 In·Out Scope / 資料流 / 資料模型 / API / 前端 / 設定 / 設計取捨 / 待確認),**有別於** HE [`01-propose-format.md`](./01-propose-format.md) 的輕量版。理由:本專案 propose 即設計拍板紀錄,價值高。對齊章節須引具體 Design-Base 錨點(見 §3)。

### 2.2 workflow/workflow-vX.Y.Z.md(編排計畫)

orchestrator 由 propose 拆出。**必含**:

```markdown
# Workflow v<major>.<minor>.<patch>

> 狀態:進行中(已完成 N/M)

## 版本資訊
- 母本 propose:[propose-v<…>.md](../propose-v<…>.md)
- 對齊的 Design-Base 章節:<具體錨點清單>

## Definition of Done
- [ ] <可驗證的交付條件>
- [ ] Swagger 於 `/api/docs` 可查閱新增 API
- [ ] 單元 / 整合測試覆蓋關鍵流程
- [ ] `.env.example` 與 `.env` 同步更新(若有新變數)

## 拆解總表
| # | 標題 | 狀態 | 並行 | 依賴 | 影響檔案 |
| --- | --- | --- | --- | --- | --- |
| 001 | … | pending | ✓ | — | `backend/app/api/...` |

## 執行流程(multi-agent)
<orchestrator-workers 順序;同檔互鎖序列化;跨 area 串(後端 API → 前端串接 → e2e);對齊 03-multi-agent-flow.md>
```

### 2.3 tasks/task-NNN-<slug>.md(逐項任務)

每個任務一檔(粒度 **1–4 hr**;方法論見 [`02-task-decomposition.md`](./02-task-decomposition.md)):

```markdown
---
id: task-001
title: <一句話>
status: pending          # pending | in_progress | done | blocked
parallel: true
depends_on: []
affected_files:
  - backend/app/api/v1/xxx.py
estimated_hours: 3
---

## 目標
<1–2 句>

## Acceptance
- [ ] <機械可驗證:`uv run pytest tests/...` 全綠 / `curl ... | grep`>
- [ ] response 殼為 ApiResponse([`03-backend/01-routing.md`](../03-backend/01-routing.md))
- [ ] `mypy` / `ruff` green

## 必讀檔(Just-in-time)
- <依任務情境,對齊 [`docs/Design-Base/README.md`](../README.md) 對照表>
```

### 2.4 fixed.md(§N 格式)

該版本內所有規範違反 / bug 根因的累積;`## §{N}` 連號,**根因為核心**。完整格式見 [`04-fixed-format.md`](./04-fixed-format.md)。既有版本的舊式 `# Fix:` 自由格式為凍結紀錄,不回頭重排;v2.0 起一律走 §N 式。

### 2.5 CHANGELOG.md(repo 根)

minor / major release 前彙整對外 user-facing 條目;格式見 [`06-changelog.md`](./06-changelog.md)。**禁**寫內部根因(那是 fixed.md)。

## 3. 前置檢查（AI 產 Task 前必做）

AI 在產出或修改 `docs/Tasks/v<major>.<minor>/workflow/` 或 `tasks/` 文件**之前必須**完成:

1. **按需載入 Design-Base**(HE Just-in-time Loading):依 `docs/Design-Base/README.md` 的「任務 → 必讀檔」對照表載入該任務情境的規範檔,**不必**全資料夾掃描;永遠載入 `00-overview/00-overview.md` + 涉及領域的 `0X/00-overview.md` 風格地板。
2. **確認對齊章節**：在 Task 的「對齊的 Design-Base 章節」列出引用的具體章節錨點，**不得**只寫檔名。
3. **檢查衝突**：Task 的設計**禁止**與 Design-Base 的任何規定衝突；若規範缺漏，**應**先補 Design-Base 再開 Task。
4. **檢查 `.env.example`**：若 Task 涉及新環境變數，**必須**同步於 `.env.example` 加上 key。
5. **檢查 Migration**：若 Task 涉及 DB Schema，**必須**同步產生 Alembic Migration 檔（`backend/alembic/versions/<revision>_<描述>.py`),透過 `alembic revision -m "<描述>"` 或 `alembic revision --autogenerate -m "<描述>"` 產生。
6. **檢查 OpenRouter 整合**：若 Task 涉及代理、模型呼叫或金鑰流，**必須**對齊 [50-openrouter.md](../90-third-party-service/50-openrouter.md)。

## 4. 產出內容規範

### 4.1 Response Schema

- **必須**使用 Pydantic BaseModel 明確定義，**禁止**使用 `dict` 當 response type。
- 欄位命名對照 [60-naming-env.md § 1](../00-overview/91-project-naming-env.md#1-命名慣例)。
- 資料表對外識別**必須**使用 `<table>_uid` (UUIDv7)，**禁止**暴露內部 `pid` 或外部系統 id 作為操作 key（詳見 [30-database.md](../04-databases/90-project-database.md)）。

### 4.2 API 路徑

- **必須**以 `/api/v1` 為前綴。
- 管理端**必須**使用 kebab-case 複數（例：`/api-keys`）。
- 代理端**必須**使用 `/api/v1/model/<action>` 格式（v1.2 起;例:`/api/v1/model/chat`),action 為功能語意,**不**綁定特定 provider。舊 `/api/v1/model/openrouter/chat` 為 deprecated alias,保留至 v1.4。
- 單一資源以 UID 作為 path parameter。

### 4.3 敏感欄位

- OpenRouter 原生 API Key、使用者密碼 hash、本地金鑰明文 / hash **禁止**出現於 Response、Log、Commit。
- 從 OpenRouter 回傳的資料若包含內部識別（provider token、route metadata 等），**必須**在 Task 文件中明列「過濾欄位表」，並於後端 response 前剔除。
- 本地金鑰於建立 API **僅一次**明文回傳，後續查詢只能回傳 prefix。Task 設計須明確標註此行為。

### 4.4 錯誤處理

- Task 設計**必須**附上「錯誤處理對照表」，列出主要錯誤情境與 HTTP status code，遵循 [20-backend.md § 2](../03-backend/90-project-backend.md#2-錯誤訊息規範) 與 [50-openrouter.md § 9](../90-third-party-service/50-openrouter.md#9-錯誤對應)。

### 4.5 用量與稽核

- 代理端功能**必須**說明如何寫入 `usage_logs`（對齊 [50-openrouter.md § 10](../90-third-party-service/50-openrouter.md#10-用量紀錄usage-log)）。
- 管理端異動操作**必須**說明如何寫入稽核 Log（對齊 [80-permission.md § 9](../03-backend/92-project-permission.md#9-稽核-log)）。

## 5. 禁止事項

Task 設計**禁止**：

- 引入 Design-Base 未允許的技術棧或套件。
- 繞過統一 Response 格式（`{ success, code, data, detail }`）；串流端點例外，但須以 [20-backend.md § 1](../03-backend/90-project-backend.md#1-統一-response-格式) 的方式處理起始錯誤。
- 繞過 Table 設計必備欄位（`pid` / `<table>_uid` / `is_active` / `is_deleted` / `created_at` / `updated_at`）。
- 在前端直接呼叫 OpenRouter API 或繞過後端代理。
- 將外部系統的內部 id（例如 OpenRouter 回傳的 `id`）作為本地 PK 或對外 UID。
- 在管理端接受 `X-SDK-Key` / `X-User-Token`，或在代理端接受管理 Cookie / Access Token。
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
