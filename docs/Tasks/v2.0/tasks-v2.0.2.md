# Tasks v2.0.2 · 資料庫自我說明(全表/欄位 COMMENT + 資料表名稱對照字典)

> 狀態:已完成(6/6)
> 來源:[propose-v2.0.2.md](./propose-v2.0.2.md);Design-Base 規則已落地(`04-databases/00-overview.md § 自我說明`、`90-project-database.md § 3.5`)
> 並行:5 / 序列:1 / 預估總時數:17 hr

| # | 標題 | 狀態 | 並行 | 依賴 | 影響檔案 |
| --- | --- | --- | --- | --- | --- |
| 201 | `table_catalog` 字典表 + model + 19 筆種子(migration 0021) | done | ✓ | — | `backend/alembic/versions/0021_table_catalog.py`、`backend/app/models/table_catalog.py`、`backend/app/models/__init__.py` |
| 202 | 必備欄位 `comment=` 注入 `TimestampMixin`(共用罐頭文案) | done | ✓ | — | `backend/app/models/base.py` |
| 203 | 帳號群 6 表 model `comment=` | done | ✓ | — | `backend/app/models/user.py`、`department.py`、`project.py`、`refresh_token.py`、`user_token.py`、`user_token_revocation.py` |
| 204 | 模型管理+稽核+計量群 5 表 model `comment=` | done | ✓ | — | `backend/app/models/model.py`、`model_tier.py`、`allowed_model.py`、`audit_log.py`、`usage_log.py` |
| 205 | 金鑰+AI 群 7 表 model `comment=` | done | ✓ | — | `backend/app/models/openrouter_key.py`、`internal_key.py`、`sdk_api_key.py`、`api_key_request.py`、`ai_eval_judge_setting.py`、`ai_model_evaluation.py`、`ai_model_eval_candidate.py` |
| 206 | 全表/欄位 COMMENT 回填 migration(改手寫,見註)0022 | done | ✗ | 201, 202, 203, 204, 205 | `backend/alembic/versions/0022_backfill_table_column_comments.py` |

## 收口註記(orchestrator,2026-06-25)

- **全部 6 task done**,Acceptance 在 dev compose backend 容器內全綠(本機 Windows + Python 3.14 跑 alembic 有 cp950/UTF-8 編碼問題、`.env` 的 `DATABASE_URL` 為容器名,故 DB 類驗證一律在容器內跑)。
- **migration chain**:`0020 → 0021_table_catalog → 0022_backfill_comments`。DB 已套到 head `0022`。注意 0022 的 **revision id = `0022_backfill_comments`**(檔名仍為 `0022_backfill_table_column_comments.py`);因 `alembic_version.version_num` 為 `VARCHAR(32)`,完整檔名前綴超長 → 縮短。**後續 migration 的 `down_revision` 須引用 `0022_backfill_comments`**。
- **206 改手寫而非 autogenerate**:`--autogenerate` 雖正確抓到 comment,但夾帶 34×`drop_index`/`create_index` + 11×FK churn 雜訊(本專案 index/FK 在 raw-SQL baseline,未鏡射進 model;autogen 重建 partial index 會遺失 `WHERE` 述詞)。worker 依規格 fallback 改手寫純 `COMMENT ON`(18 表級 + 262 欄位級 = 280 句,downgrade 還原 NULL)。
- **衍生發現 → 已於本次一併修正(model↔DB schema parity)**:原 model↔DB 在 index/FK 層級長期漂移使 autogen 不可信。已把 baseline 既有 index / FK / 表級 comment **逐字鏡射進 17 個 model 的 `__table_args__`**(`table_catalog` 本就已宣告):
  - 影響檔(額外動到,非 201–206 範圍):`backend/app/models/` 的 `user.py`、`department.py`、`project.py`、`refresh_token.py`、`model.py`、`model_tier.py`、`allowed_model.py`、`audit_log.py`、`usage_log.py`、`user_token.py`、`user_token_revocation.py`、`openrouter_key.py`、`internal_key.py`、`sdk_api_key.py`、`api_key_request.py`、`ai_eval_judge_setting.py`、`ai_model_evaluation.py`、`ai_model_eval_candidate.py`。純宣告 DB 既有物件,**未改 schema、未產 migration**。
  - **驗證結果**(容器內 trial autogen):FK churn 9→**0**、表級 comment churn 18→**0**、index churn ~36→**3**、型別/server_default/check 0。
  - **可接受殘差(user 拍板接受)**:剩 3 筆為 functional 唯一索引(`uq_users_account` / `uq_departments_code` / `uq_projects_dept_code`)的 `lower(col::text)` vs pg 正規化 `lower((col)::text)` 括號差異——已知 Alembic 假陽性,index 名/欄位/unique/partial 條件全同,非真實 drift。若日後要字面歸零,於 `alembic/env.py` 加 functional-index comparator 抑制即可。
  - **結論**:`alembic revision --autogenerate` 對 18 表的真實結構 churn 已歸零,autogen 恢復可用。
- **既有技術債(非本版引入)**:全庫 `ruff check .` 約 67 個既有錯(baseline migrations / app/api / app/core 等),本版 6 個改動檔 ruff/mypy 皆乾淨。

## 並行批次

- **批次 1(可同時認領)**:201、202、203、204、205(`affected_files` 互不重疊)
- **批次 2**:206(待 201–205 全 done;autogen 需所有 model `comment=` 就位 + DB 已含 `table_catalog`)

## 必備欄位 COMMENT 罐頭文案(全 task 共用基準)

> 中英雙語(對齊 `04-databases/00-overview.md § 自我說明`)。task-201/202 寫入下列**逐字**文案,task-203/204/205 的 `pid` / `<entity>_uid` 亦用此基準,確保 18 表一致、autogen 無歧異。

| 欄位 | `comment=` 文案(逐字) |
| --- | --- |
| `pid` | `內部自增主鍵,禁對外暴露 \| internal auto-increment PK` |
| `<entity>_uid` | `對外 UUID 識別(UUIDv7) \| external UID` |
| `is_active` | `是否啟用,停用後保留資料但不可使用 \| active flag` |
| `is_deleted` | `軟刪除標記,查詢預設過濾 is_deleted=FALSE \| soft-delete flag` |
| `created_at` | `建立時間(UTC+8) \| created at` |
| `updated_at` | `更新時間(UTC+8,由 trigger 維護) \| updated at` |

> 業務欄位的中文文案,worker 優先轉用 model 既有行內註解(如 `usage_logs.used_tools` / `ai_evaluated_at`),無註解者依欄位語意補一句中英雙語。

## 阻塞點 / 待使用者確認(來自 propose §8,拆解前未決)

> 下列不阻塞批次 1 開工,但影響 task-201 種子內容與是否追加 task:

1. **維護 UI**(propose §8.1):本拆解**未含** UI/API task(傾向本版只做 DB 層)。user 若要唯讀檢視頁 → 追加 207(後端)+ 208(前端)三段鏈。
2. **中文顯示名 / 分組**(propose §8.2):task-201 種子採 propose §3 草案命名;user 改字 → 只動 201,不影響其他 task。
3. **欄位級對照**(propose §8.3):已決議只走 `COMMENT ON COLUMN`,**不**另建欄位字典表 → 無對應 task(符合 scope)。

## 拆解註記(orchestrator)— 已決議(2026-06-25)

- **task 編號**:本版採 `201+` 區塊(v2.0.0=`001+`、v2.0.1=`101+`)。
- **migration 編號**:`0020` 已被 v2.0.1 佔用 → 本版 `0021`(table_catalog)+ `0022`(COMMENT 回填);chain:`0020 → 0021 → 0022`。
- **雙軌一致策略**:**models 為單一真相源**。task-202/203/204/205 對全欄補 `comment=`;task-206 以 `alembic revision --autogenerate` 從 model metadata 差異產生 `0022`,DB COMMENT 與 model `comment=` 天然同源、不漂移。
- **回填範圍**:涵蓋 v2.0.0 三張 `ai_` 表與 v2.0.1 `usage_logs` 兩個新欄(規則前建立、皆無 comment)。
- **In Scope 映射**:propose In Scope ① COMMENT→202/203/204/205/206;② table_catalog→201;③ 慣例落地→規則已於 Design-Base 落地,本版以 201 建立其引用的 `table_catalog` 機制。
