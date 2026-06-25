[//]: # (此檔為 v2.0.2 任務提案,實作前先由使用者確認範圍與設計取捨。)

# Propose v2.0.2 · 資料庫自我說明【全表/欄位 COMMENT + 資料表名稱對照字典】

> 此為 **proposal**(規劃草案),確認後即轉為正式 `tasks-v2.0.2.md`。
>
> 本版為 **DB 治理 / 可維護性**,與 v2.0.x「模型適配評審」功能線正交。**不動任何既有欄位定義、不打 OpenRouter、不改業務邏輯**;純補 metadata + 新增一張對照字典表。

## 1. 目標(本版)

目前資料庫 **18 張業務表、所有欄位皆無任何 PostgreSQL `COMMENT`**(`grep comment=` 於 models / migrations 全數 0 命中),導致用 DB 工具(DBeaver / psql `\d+` / pgAdmin)瀏覽 schema 時無從得知每張表、每個欄位的用途,**搜尋與維護困難**。

> **含 v2.0.0 / v2.0.1 新建之物**:評審地基 3 張 `ai_` 表(v2.0.0,migration `0019`)與 `usage_logs` 的 2 個新評審旗標欄(v2.0.1,migration `0020`:`ai_evaluated_at` / `ai_evaluated_status`)**皆在本 comment 規則訂立前建立、目前同樣無 `COMMENT`**,本版回填一併涵蓋。

本版補齊:

1. **全表 + 全欄位補 `COMMENT`**:對現有 18 張表(含上述新表 / 新欄)逐一 `COMMENT ON TABLE` + `COMMENT ON COLUMN`,讓 schema 自帶說明,DB 工具與 `\d+` 直接可讀。
2. **新增「資料表名稱對照」字典表**:存每張實體表名 → 中文顯示名(+ 分組 / 說明),例 `users` → 使用者;作為 app / 前端可查的資料字典來源。
3. **慣例化**:之後新表的 model / migration **一律帶 `comment=`**,並同步登錄對照字典 —— **規範已於前一輪寫入 Design-Base**(`04-databases/00-overview.md § 自我說明` + `90-project-database.md § 3.5`),本版負責建立規範所指的 `table_catalog` 機制。

> **本版刻意不做**:不做對照字典的維護 UI(留待確認,§ 8.2)、不改既有欄位型別 / 約束、不碰 v2.0.x 評審管線。

## 2. 範圍(本版)

### In Scope

- **現有 18 表的 `COMMENT`**(§ 4):migration `0022` 對全表下 `COMMENT ON TABLE` + 各欄位 `COMMENT ON COLUMN`(含 v2.0.0/v2.0.1 新建的 `ai_` 表與 `usage_logs` 評審旗標欄)。
- **`table_catalog` 對照字典表**(§ 5):migration `0021` 新增表 + 初始種子資料(18 既有 + 自身 = **19 筆**)。
- **慣例落地驗證**(§ 6):Design-Base 規則已於前一輪寫入;本版確認 `table_catalog` 機制可被該規則引用。

### Out of Scope

- **對照字典維護 UI / API** → 待確認是否本版做或順延(§ 8.2)。
- **欄位層級的中文對照表**(本版欄位說明走 `COMMENT ON COLUMN`,不另建欄位字典表)。
- **既有欄位型別 / 約束 / 命名變更**(純加 metadata,不改結構)。
- **v2.0.x 評審功能**(本版正交,不涉及)。

## 3. 表清單(18 既有 + 1 新增 = 19,COMMENT 與字典皆涵蓋全部)

| # | 實體表名 | 中文顯示名(草案,可調) | 分組 |
| --- | --- | --- | --- |
| 1 | `users` | 使用者 | 帳號 |
| 2 | `departments` | 部門 | 帳號 |
| 3 | `projects` | 專案 | 帳號 |
| 4 | `refresh_tokens` | 更新權杖 | 帳號 |
| 5 | `user_tokens` | 使用者權杖 | 帳號 |
| 6 | `user_tokens_revocations` | 使用者權杖撤銷 | 帳號 |
| 7 | `audit_logs` | 稽核紀錄 | 稽核 |
| 8 | `models` | 模型 | 模型管理 |
| 9 | `model_tiers` | 模型分級 | 模型管理 |
| 10 | `allowed_models` | 模型白名單 | 模型管理 |
| 11 | `openrouter_keys` | OpenRouter 金鑰 | 金鑰 |
| 12 | `internal_keys` | 內部金鑰 | 金鑰 |
| 13 | `sdk_api_keys` | SDK API 金鑰 | 金鑰 |
| 14 | `api_key_requests` | 金鑰申請單 | 金鑰 |
| 15 | `usage_logs` | 用量紀錄 | 計量 |
| 16 | `ai_eval_judge_settings` | 判別模型設定 | AI 分析 |
| 17 | `ai_model_evaluations` | 模型評審結果 | AI 分析 |
| 18 | `ai_model_eval_candidates` | 模型評審候選 | AI 分析 |
| 19 | `table_catalog` | 資料表名稱對照 | 系統 |

> 第 19 列為**本版新增**的字典表自身(§ 5);依 Design-Base 新規則,新表須自我登錄字典,故種子含此筆。
> 中文顯示名 / 分組為草案,以你回饋為準(§ 8.2)。`alembic_version` 等 alembic 系統表不納入。

## 4. 全表/欄位 COMMENT(migration `0022`)

- **手段**:純 `op.execute("COMMENT ON TABLE ... IS '...'")` 與 `COMMENT ON COLUMN ...`,**不 alter 任何欄位**。`downgrade` 將 comment 設回 `NULL`(`COMMENT ON ... IS NULL`)。
- **內容來源**:表級說明取自 § 3 對照表;欄位級說明逐欄補(優先參考既有 model 的行內註解,如 `usage_logs.used_tools`、`usage_logs.project_uid`,以及 **v2.0.1 新加的 `usage_logs.ai_evaluated_at` / `ai_evaluated_status`**(model 已有清楚中文註解)直接轉成 `COMMENT`;v2.0.0 三張 `ai_` 表欄位則參考 `0019` migration 的 docstring 與 propose-v2.0.0 § 4 表格)。
- **必備欄位統一文案**:`is_active`(是否啟用)、`is_deleted`(是否軟刪除)、`created_at`(建立時間)、`updated_at`(更新時間)、`pid`(內部自增主鍵)、`*_uid`(對外 UUID 識別)— 共用罐頭文案,migration 內以 helper 批次套用,減少重複。
- **雙軌一致(已決議,§ 8)**:`COMMENT` 是 DB 原生 metadata,SQLAlchemy model 的 `comment=` 是程式端來源。本版同時**回填 model 的 `comment=`**(讓 `Base.metadata` 與 DB 對齊,日後 autogenerate diff 不會誤判),migration 與 model 文案須一致。

## 5. 資料表名稱對照字典 `table_catalog`(新增表,migration `0021`)

遵循專案既有慣例(`pid` BigInteger 自增 PK + `*_uid` UUID unique + 必備四欄 + `set_updated_at` trigger;軟引用、無 DB 層 FK)。**本表自身亦帶 `COMMENT` 並自我登錄一筆**(吃自己的狗糧,符合 Design-Base 新規則)。

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| `pid` | BIGINT, PK, autoincrement | 內部自增主鍵 |
| `table_catalog_uid` | UUID, unique | 對外識別 |
| `table_name` | VARCHAR(64), **unique**, NOT NULL | 實體表名(如 `users`) |
| `display_name_zh` | VARCHAR(128), NOT NULL | 中文顯示名(如 使用者) |
| `category` | VARCHAR(32), null | 分組(帳號 / 金鑰 / 計量 / AI 分析…),利搜尋與分類 |
| `description` | TEXT, null | 用途說明(與該表 `COMMENT ON TABLE` 同源) |
| `sort_order` | SMALLINT, null | 顯示排序 |
| `is_active` / `is_deleted` / `created_at` / `updated_at` | — | 必備欄位 |

- **種子資料**:migration 內一次插入 § 3 全部 **19 筆**(18 既有 + `table_catalog` 自身)。
- **冪等**:`table_name` UNIQUE;種子用 upsert(`ON CONFLICT (table_name) DO NOTHING`),重跑不重複。
- **定位**:此表是**人類可維護的資料字典**(未來可接 UI / 給前端做欄位中文化下拉、報表標題);DB `COMMENT` 是給 DBA / SQL 工具看的原生 metadata。兩者同源、互補。

## 6. 慣例落地(規範同步)

避免「補完又漂移」:

- **規範已落地(前一輪完成)**:
  - `docs/Design-Base/04-databases/00-overview.md` 新增「自我說明:COMMENT」一節(表級 + 欄位級 + 雙軌一致,HE 通用地板)。
  - `docs/Design-Base/04-databases/90-project-database.md` 新增 `§ 3.5 資料表自我說明:COMMENT + 字典登錄`,綁定 `table_catalog`,並註明此表由 v2.0.2 建立、合併後對後續新表生效。
  - AGENTS.md 不重述 DB 細則(委派 Design-Base),無須同步。
- **本版負責**:實作規則所指的 `table_catalog`(§ 5)、回填現有 schema 的 COMMENT(§ 4),讓上述規則自 v2.0.2 起可實際被遵循。
- **後續可選**:`/scan-project` 加一條「新表缺 comment / 未登錄字典」檢查(待確認,§ 8)。

## 7. 設定(環境變數)

- 本版**無新增 env**(純 DB migration + 種子資料)。

## 8. 設計取捨 / 待使用者確認

### 已決議(2026-06-25)

- **版號 slot**:**確認用 v2.0.2**。`propose-v2.0.0 § 2` 藍圖原把 v2.0.2 暫定給「真實重跑」,本版佔用後評審線後續版號順延(真實重跑→v2.0.3、人類裁決→v2.0.4…)。
- **雙軌一致策略**:**確認兩邊都寫並保持一致** — DB `COMMENT`(migration)與 model `comment=`(程式)同步維護同一份文案,讓 alembic autogenerate 不誤判。
- **Design-Base 規則已寫入**(前一輪):新表必補 COMMENT + 登錄 `table_catalog`(見 § 6)。
- **v2.0.1 已落地**:migration `0020` 在 `usage_logs` 加 `ai_evaluated_at` / `ai_evaluated_status` 2 欄 + partial index,**未建新表**(評審 3 張 `ai_` 表為 v2.0.0)。新欄無 comment,本版回填涵蓋;migration 編號順移為 `0021`(table_catalog)+ `0022`(COMMENT 回填)。
- 既有 18 張業務表、**全欄位 0 個 `COMMENT`**;models 無任何 `comment=`。
- 既有外鍵採「純 UUID 軟引用 + 索引、無 DB 層 FK」慣例,新表 `table_catalog` 沿用。

### 待使用者確認

1. **是否本版就做維護 UI**:傾向本版只做 DB 層(migration + 種子),字典維護 UI / API 順延。或你要本版一併做唯讀檢視頁?
2. **中文顯示名 / 分組**:§ 3 草案命名是否採用?有無偏好用詞(如「用量紀錄」vs「使用紀錄」、分組粒度)?
3. **欄位級對照**:本版欄位說明只走 `COMMENT ON COLUMN`,**不**另建欄位中文字典表。若日後前端要「欄位中文化」,再開版擴 `table_catalog` 為欄位級或新增子表。可接受嗎?
