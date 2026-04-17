# CLAUDE.md

Claude Code 在任何專案共用的基本規範。專案特定設計請參考 [docs/Design-Base/\*](docs/Design-Base/)。

## 基本原則

- 回應、註解、文件一律使用**繁體中文**。
- 保持簡潔：不主動新增檔案、不過度抽象、不預先設計未存在的需求。
- 不主動添加註解，除非 WHY 難以從程式碼推斷。
- 遵循既有程式碼風格與命名慣例，不擅自重構無關區塊。

## 開發前必檢查

每次開始開發前，依序確認：

1. `.env.example` 存在（每個專案必備）。
2. `.env` 存在；若無，提醒使用者從 `.env.example` 複製建立。
3. `.env.example` 所有鍵名皆已於 `.env` 填入值；缺漏則逐一列出後暫停。
4. 程式碼中使用的環境變數皆已於 `.env.example` 定義；缺漏則提醒同步更新。

## 敏感資訊

- Token、密碼、連線字串、API Key 一律透過環境變數注入。
- `.gitignore` 須明確排除 `.env`、credentials 等敏感檔案。
- 發現疑似敏感資訊於程式碼或 commit 中，立即提醒使用者。

## 後端 API 文件

- 有後端程式的專案**必須**提供 Swagger / OpenAPI 文件。
- 存取路徑統一為 **`/api/docs`**（禁用 `/swagger`、`/docs`、`/openapi` 等其他路徑）。
- FastAPI：初始化時明確指定 `docs_url="/api/docs"`。
- 新增或修改 API 時，須同步維護 Request / Response Schema 與欄位說明。

## Git 工作流程

- 主分支 `main`，新功能從 `main` 切出 feature branch。
- Commit Message 使用**繁體中文**，格式 `<類型>: <描述>`。
  - 類型：`Add` / `Modify` / `Fix` / `Refactor` / `Docs`
- AI 產生的 commit 一律加 `(AI)` 前綴，例：`(AI) Add: 新增使用者管理功能`。
- 未經使用者允許，禁止破壞性操作（`--force`、`reset --hard`、`--no-verify`）。

## 自訂指令

| 指令                                                | 說明                           |
| --------------------------------------------------- | ------------------------------ |
| [`/commit-all`](.claude/commands/commit-all.md)     | 一鍵提交並推送當前分支所有變更 |
| [`/merge-main`](.claude/commands/merge-main.md)     | 合併當前分支至 `main`          |
| [`/scan-project`](.claude/commands/scan-project.md) | 掃描專案結構並分析潛在問題     |
| [`/dev-up`](.claude/commands/dev-up.md)             | 一鍵啟動本機開發環境           |

## 規範優先順序

衝突時以下列順序決定：
**`docs/Design-Base/*`（專案規範）** > **本檔案（通用規範）** > 其他。