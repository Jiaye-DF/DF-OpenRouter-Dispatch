---
id: task-206
title: 全表/欄位 COMMENT 回填 migration(autogen 自 model)0022
status: done
parallel: false
depends_on: [task-201, task-202, task-203, task-204, task-205]
affected_files:
  - backend/alembic/versions/0022_backfill_table_column_comments.py
estimated_hours: 3
---

## 目標

待全部 model `comment=` 就位(201–205)後,以 `alembic revision --autogenerate` 從 model metadata 差異產生 migration `0022`,把 18 張既有表的表級 + 欄位級 COMMENT 一次回寫 DB。DB COMMENT 與 model `comment=` 天然同源,杜絕雙軌漂移。

## 設計

- 前置:本機 DB 已 `alembic upgrade head` 到 `0021`(table_catalog 已建妥、已含 comment → autogen 不應再動它)。
- `cd backend && uv run alembic revision --autogenerate -m "backfill_table_column_comments"`,產出 rename 為 `0022_backfill_table_column_comments.py`,`down_revision = "0021_table_catalog"`。
- **人工核對 autogen 結果**:
  - 僅含 `op.create_table_comment` / `op.alter_column(..., comment=..., existing_*=...)` 之類**純 comment 異動**;**禁**出現 `create_table` / `drop_column` / 型別變更(若有 → 表示 model 被誤改,退回對應 201–205 task)。
  - 涵蓋全部 18 表(`table_catalog` 不在本檔,已於 0021 帶 comment)。
  - `downgrade` 將 comment 還原為 `None`(autogen 已具 `existing_comment`)。
- 若 autogen 未捕捉 comment(alembic 設定未開 comparator)→ 改為手寫 `op.execute("COMMENT ON TABLE/COLUMN ...")` 全表回填,文案與 model 一致。

## Acceptance

- [ ] migration 檔存在:`[ -f backend/alembic/versions/0022_backfill_table_column_comments.py ]`
- [ ] 不含結構異動:`cd backend && ! grep -nE "create_table\(|drop_column|drop_table" alembic/versions/0022_backfill_table_column_comments.py`
- [ ] `cd backend && uv run alembic upgrade head` 套用至 `0022` 成功
- [ ] round-trip:`cd backend && uv run alembic downgrade -1 && uv run alembic upgrade head` 無誤
- [ ] DB 層抽驗(表級 + 欄位級 COMMENT 非空):
```
cd backend && uv run python -c "
import asyncio
from sqlalchemy import text
from app.core.database import engine
async def m():
    async with engine.connect() as c:
        t=(await c.execute(text(\"select obj_description('usage_logs'::regclass)\"))).scalar()
        col=(await c.execute(text(\"select col_description('usage_logs'::regclass,(select attnum from pg_attribute where attrelid='usage_logs'::regclass and attname='model'))\"))).scalar()
        assert t and col, (t,col)
asyncio.run(m())"
```
- [ ] `cd backend && uv run ruff check alembic/versions/0022_backfill_table_column_comments.py`

## 必讀檔(Just-in-time)
- `04-databases/00-overview.md`(§ 自我說明)
- `04-databases/08-alembic.md`
- `04-databases/90-project-database.md`(§ 5 Migration + § 3.5)
