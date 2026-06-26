# 30 · 資料庫與 Migration 規範

本文件定義資料表設計、軟刪除、Migration 與共用 Trigger 的規範。

## 1. 必備欄位

**所有**業務資料表**必須**包含下列欄位。**資料表名稱一律使用 snake_case 複數形式**（例：`api_keys`、`usage_logs`、`users`），**欄位名稱則以實體單數為準**（例：`api_key_uid`、`user_uid`）。

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| `pid` | `BIGSERIAL PRIMARY KEY` | 內部使用的流水號主鍵，**禁止**對外暴露 |
| `<entity>_uid` | `UUID NOT NULL UNIQUE` | 對外使用的唯一識別，採 **UUIDv7**；外鍵、API path 一律使用此欄位；命名以**實體單數**為基（例：`users` 表的 UID 欄位為 `user_uid`） |
| `is_active` | `BOOLEAN NOT NULL DEFAULT TRUE` | 啟用狀態（停用後保留資料但不可使用） |
| `is_deleted` | `BOOLEAN NOT NULL DEFAULT FALSE` | 軟刪除標記（查詢預設過濾 `WHERE is_deleted = FALSE`） |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT NOW()` | 建立時間（UTC） |
| `updated_at` | `TIMESTAMPTZ NOT NULL DEFAULT NOW()` | 更新時間（UTC），由 trigger 自動維護 |

## 2. 命名範例

```sql
CREATE TABLE api_keys (
    pid                    BIGSERIAL PRIMARY KEY,
    api_key_uid            UUID NOT NULL UNIQUE,
    name                   VARCHAR(128) NOT NULL,
    description            TEXT,
    is_active              BOOLEAN NOT NULL DEFAULT TRUE,
    is_deleted             BOOLEAN NOT NULL DEFAULT FALSE,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_api_keys_uid ON api_keys (api_key_uid);
CREATE INDEX idx_api_keys_active ON api_keys (is_active, is_deleted);
```

## 3. 重要規則

1. **資料表名稱一律使用複數**：`api_keys`、`users`、`usage_logs`；**禁止**使用單數形式。
2. **主鍵 `pid` 僅限資料庫內部使用**：JOIN、index、sequence，效能優先。
3. **對外識別一律使用 `<entity>_uid`**（實體單數）：API path（`/api-keys/{uid}`）、外鍵欄位、response 欄位名均使用 UUID；**禁止**使用複數形式欄位名。
4. **外鍵命名**：其他表引用此表時使用 `<entity>_uid`，例 `usage_logs` 表引用 `api_keys` 時欄位為 `api_key_uid UUID REFERENCES api_keys(api_key_uid)`。
5. **外部系統 id**：若需儲存第三方系統（OpenRouter 等）回傳的 id，以獨立欄位命名（例如 `openrouter_generation_id VARCHAR(64)`），**禁止**當作本地 PK 或對外 UID 使用。
6. **UUIDv7 生成**：Python 標準 `uuid` 模組尚無內建 v7，**應**使用 `uuid-utils` 套件（`from uuid_utils import uuid7`）。UUIDv7 前 48 bit 為 timestamp，天然可排序，可取代 `created_at` 做分頁 cursor。
7. **軟刪除**：SQLAlchemy Query **必須**預設附加 `.where(Model.is_deleted == False)`；可透過 session scoped filter 或自訂 Query class 實作。真正 `DELETE` **僅允許**在 Migration 或手動維運情境。
8. **時間欄位**：一律使用 `TIMESTAMPTZ`，程式端以 UTC 處理，前端顯示時再轉當地時區。
9. **敏感欄位加密**：儲存 OpenRouter API Key、使用者密碼 hash 等敏感欄位時，**必須**以加密或 hash 後寫入，**禁止**以明文存放。解密金鑰一律透過環境變數注入。
10. **Index / Trigger 命名**：以**複數表名**為基（例：`idx_api_keys_uid`、`trg_api_keys_updated_at`）。

## 3.5 資料表自我說明:COMMENT + 字典登錄(永遠遵守)

**凡 migration 動到 schema,同一份 migration 內必同步維護 COMMENT 與字典**,缺者不得合併。依異動類型:

### A. 新建資料表(`op.create_table`)

兩件事都要做:

1. **補 COMMENT**(表級 + 全欄位,雙軌一致):
   - migration 下 `COMMENT ON TABLE <table> IS '...'` 與每欄 `COMMENT ON COLUMN <table>.<col> IS '...'`(中英雙語);**不得**只建表不寫說明。
   - 對應 SQLAlchemy Model 欄位帶 `comment=`,文案與 DB `COMMENT` 一致(避免 alembic autogenerate 誤判)。
   - 必備欄位(`pid` / `<entity>_uid` / `is_active` / `is_deleted` / `created_at` / `updated_at`)套統一罐頭文案。
   - 通用規則見 `00-overview.md § 自我說明`。
2. **登錄字典 `table_catalog`**:同一份 migration upsert 一筆(`table_name` → `display_name_zh` + `category` + `description`),`ON CONFLICT (table_name) DO NOTHING` 保冪等;`description` 與該表 `COMMENT ON TABLE` 同源同文案。

### B. 新增 / 異動欄位(`op.add_column` / `op.alter_column`)

- **新增欄位**:該欄**必**同步 `COMMENT ON COLUMN`(雙語)+ Model 欄位帶 `comment=`(同文案);**不得**只 add_column 不寫說明。
- **異動欄位語意**(改型別 / 改用途):**必**同步更新該欄 COMMENT 與 Model `comment=`,使說明不過期。
- **字典處理**:`table_catalog` 為**表級**對照,改欄位通常不需動;但**若該表尚未在字典**(歷史遺留表),藉這次異動順手 upsert 補登一筆。

> `table_catalog` 表由 **v2.0.2** 建立(見 `docs/Tasks/v2.0/propose-v2.0.2.md`);本規則於 v2.0.2 合併後對所有後續 schema 異動生效。
> 目的:DBeaver / `psql \d+` 直接可讀 schema,前端 / 報表可由 `table_catalog` 取中文表名,避免「表 / 欄多了沒人知道是什麼」。

## 4. `updated_at` 自動更新

於 Alembic baseline migration(`backend/alembic/baseline_sql/V1__init_auth.sql`)定義共用 trigger function：

```sql
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

每個表建立時掛載（`<table>` 為複數表名）：

```sql
CREATE TRIGGER trg_<table>_updated_at
BEFORE UPDATE ON <table>
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
```

## 5. Migration

- 所有 Schema 變更**必須**透過 Alembic Migration,**禁止**手動修改資料庫。
- Migration 檔案位於 `backend/alembic/versions/`,檔名由 Alembic 產生(`<revision>_<slug>.py`)。
- baseline 檔(`backend/alembic/versions/0001_baseline_flyway_v1_v11.py`)為原 Flyway V1~V11 的封存,內容仍為原始 SQL,放在 `backend/alembic/baseline_sql/` 並由 baseline migration 按版號順序執行。**baseline 檔案禁止修改**。
- 從 baseline 之後的 migration 走 Alembic 標準 Python API(`op.create_table` / `op.add_column` / `op.execute` 等)。
- 產生新 migration:
  ```bash
  cd backend
  alembic revision -m "<描述>"                  # 手寫
  alembic revision --autogenerate -m "<描述>"   # 由 SQLAlchemy model diff 產生
  ```
- 每次功能若涉及 Schema 變更,**必須**同步提交對應 Alembic Migration 檔。
- **禁止**對已合併到 `main` 的 Migration 做任何修改(會造成 alembic_version 對不上 / production 重跑),需以新 revision 進行調整。
- Migration 套用:
  ```bash
  alembic upgrade head     # 升到最新
  alembic downgrade -1     # 回退一版(僅用於本機)
  alembic current          # 查詢目前 revision
  alembic history          # 查詢 revision 歷史
  ```

## 6. 歷史遺留 Migration 的補救模式

已合併至 `main` 的 Migration 一經發現不符本文件 § 1 必備欄位或其他規範時,**禁止**回頭修改原檔(production 已套用、alembic_version 已記錄,改檔會造成歷史不一致);**必須**以新 revision `DROP + CREATE` 或 `ALTER` 的方式補救。流程:

1. **確認遺留檔不動**:原 migration 檔保留於版控,作為歷史紀錄與稽核依據。
2. **新增補救 Migration**(`alembic revision -m "redefine_<table>"` 或 `fix_<table>`):
   - 若結構差異大(缺 `pid` / `<table>_uid` / `is_*` 等必備欄位):以 `op.execute("DROP TABLE IF EXISTS <table>")` + `op.create_table(...)` 重建。
   - 若只是欄位缺漏:以 `op.add_column(...)` 補齊。
3. **補救 Migration 檔頭必須加註解**說明:被補救的 revision、違反的章節、補救方式。範例:

```python
"""redefine api_keys: 依 docs/Design-Base/30-database.md § 1 重新定義。

被補救:0003_create_api_keys 的 api_keys 缺 <entity>_uid / is_active,不符必備欄位。
以 DROP + CREATE 方式補救,0003 檔保留於版控不得修改。
"""

def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS api_keys")
    op.create_table("api_keys", ...)
```

4. **禁止**透過直接修改 `alembic_version` 表或刪除 revision 檔來繞過遺留檔;若遺留檔已在正式環境執行過,**必須**走新 revision 補救,不得事後竄改。
5. **補救後**:於補救 Migration 的 commit message 與對應 Task 文件中同步標註「補救 <舊 revision>」,便於追溯。

## 7. 業務代碼產生:Snowflake ID

部分欄位需要「**對使用者顯示**」的全域唯一代碼(例:`projects.code` → 呼叫端 `X-Project-Code` header)。這類欄位**不適合**用 `<entity>_uid`(UUIDv7 含 hyphen 共 36 字,當 header / URL / 口頭傳遞太冗長),也**不應**讓使用者自訂(會有撞名、命名爭議),因此採 Twitter 風格的 **Snowflake ID**,由後端統一產生。

### 結構(64-bit)

| Bits | 用途 | 範圍 |
| --- | --- | --- |
| 41 | 自訂 epoch 起的毫秒數 | ~69 年 |
| 10 | worker id | 0–1023 |
| 12 | 同一毫秒內的 sequence | 0–4095 |

- **自訂 epoch**:`2026-01-01T00:00:00Z`(寫死於 [`backend/app/core/snowflake.py`](../../../backend/app/core/snowflake.py))。
- **輸出**:`generate_id_str()` 回傳十進位字串(最長 19 字),寫入欄位型別 `VARCHAR(64)` 即可。
- **worker id**:由環境變數 `SNOWFLAKE_WORKER_ID` 注入(0–1023),預設為 `1`。

### 重要規則

1. **適用範圍**:**僅限**「需對外顯示且需穩定可被引用」的業務代碼(目前為 `projects.code`)。**禁止**用於:
   - Row PK → 用 `BIGSERIAL pid`。
   - 對外 row 識別 → 用 `UUIDv7 <entity>_uid`。
   - **任何密碼性質憑證**(SDK Key、User Token、API Key 等)→ Snowflake 帶時間戳可預測,**必須**改用 `secrets.token_hex` / `secrets.token_urlsafe` 等密碼學亂數。
2. **多 worker 部署**:每個會產生 Snowflake ID 的 process **必須**配發**不同** `SNOWFLAKE_WORKER_ID`,否則同毫秒不同 worker 仍會撞 ID。Coolify / k8s 部署時需於 deployment template 注入。
3. **免撞名檢查**:Snowflake 全域唯一(在 worker id 分配正確的前提下),引入此策略的欄位**不需要**額外做 `UNIQUE` 查詢檢查 — 但 DB schema 仍應加 `UNIQUE` 約束作為最後防線。
4. **epoch 不可更動**:一旦正式環境產生過 ID,變更 epoch 會讓既有 ID 失去時間語義,並可能與新 ID 重疊。如需擴展年限,**應**走新 generator(例:`generate_id_v2`),不得就地改參數。
5. **新欄位採用前需評估**:採 Snowflake 等同於放棄「使用者命名」的彈性。若該欄位的語義是「人類可讀的名稱」(例:部門 `code` 是縮寫如 `T000`)而非機器序號,**應**維持使用者輸入 + 撞名檢查的模式,不要強行套 Snowflake。
