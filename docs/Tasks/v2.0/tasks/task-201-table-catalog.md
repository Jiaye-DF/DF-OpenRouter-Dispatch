---
id: task-201
title: table_catalog 字典表 + model + 19 筆種子(migration 0021)
status: done
parallel: true
depends_on: []
affected_files:
  - backend/alembic/versions/0021_table_catalog.py
  - backend/app/models/table_catalog.py
  - backend/app/models/__init__.py
estimated_hours: 3
---

## 目標

建立資料表名稱對照字典 `table_catalog`(實體表名 → 中文顯示名),migration `0021` 含建表 + `set_updated_at` trigger + 19 筆種子;同步建 SQLAlchemy model 並註冊 `__init__.py`。本表自身亦帶 `COMMENT` 並自我登錄一筆(符合 Design-Base 新規則)。

## 設計(對齊 propose-v2.0.2 §5)

- migration `0021_table_catalog.py`,`down_revision = "0020_usage_logs_ai_eval_flags"`。
- 欄位:`pid`(BIGSERIAL PK)、`table_catalog_uid`(UUID unique)、`table_name`(VARCHAR(64) unique not null)、`display_name_zh`(VARCHAR(128) not null)、`category`(VARCHAR(32) null)、`description`(TEXT null)、`sort_order`(SMALLINT null)、`is_active`/`is_deleted`/`created_at`/`updated_at`(必備四欄)。
- 沿用 `0019` 的 `_required_columns()` 風格 + `CREATE TRIGGER trg_table_catalog_updated_at ... set_updated_at()`。
- **建表即帶 COMMENT**:`op.create_table` 各 `sa.Column(..., comment=...)` + 表級 `comment=`。必備欄位用 tasks-v2.0.2.md §「罐頭文案基準」逐字文案;表級 `資料表名稱對照字典:實體表名 → 中文顯示名 | data dictionary of table names`。
- **種子 19 筆**:`op.bulk_insert` 或 `op.execute(INSERT ... ON CONFLICT (table_name) DO NOTHING)`,內容取 propose-v2.0.2 §3 全 19 列(18 既有 + `table_catalog` 自身,`category='系統'`)。`table_catalog_uid` 用 `uuid_utils.uuid7()`(對齊 `01-identifiers.md`)。
- model `table_catalog.py`:繼承 `Base, TimestampMixin`,各 `mapped_column(..., comment=...)` 文案與 migration 完全一致。
- `downgrade`:drop trigger → drop table。

## Acceptance

- [ ] `cd backend && uv run alembic upgrade head` 套用至 `0021_table_catalog` 成功
- [ ] round-trip:`uv run alembic downgrade -1 && uv run alembic upgrade head` 無誤
- [ ] 種子 19 筆:`cd backend && uv run python -c "import asyncio; from sqlalchemy import text; from app.core.database import engine
async def m():
    async with engine.connect() as c:
        n=(await c.execute(text('select count(*) from table_catalog'))).scalar(); assert n==19, n
asyncio.run(m())"`
- [ ] 表級 COMMENT 非空:同上 connection 跑 `select obj_description('table_catalog'::regclass)` 斷言非 None
- [ ] model 匯入:`cd backend && uv run python -c "from app.models import TableCatalog; assert TableCatalog.__table__.c.table_name.comment"`
- [ ] `cd backend && uv run ruff check . && uv run mypy app/models/table_catalog.py`

## 必讀檔(Just-in-time)
- `04-databases/00-overview.md`
- `04-databases/01-identifiers.md`
- `04-databases/08-alembic.md`
- `04-databases/90-project-database.md`(§ 3.5 自我說明 + § 4 trigger)
