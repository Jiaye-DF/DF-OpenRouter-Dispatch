---
id: task-202
title: 必備欄位 comment= 注入 TimestampMixin(共用罐頭文案)
status: done
parallel: true
depends_on: []
affected_files:
  - backend/app/models/base.py
estimated_hours: 1
---

## 目標

為 `TimestampMixin` 的四個共用欄位(`is_active` / `is_deleted` / `created_at` / `updated_at`)補 `comment=`,使全部 18 表 + `table_catalog` 的必備欄位於 autogenerate(task-206)時一次帶出 COMMENT,避免逐表重寫。

## 設計

- 僅改 `backend/app/models/base.py` 的 `TimestampMixin`,各 `mapped_column` 加 `comment=`,文案取 tasks-v2.0.2.md §「罐頭文案基準」**逐字**:
  - `is_active` → `是否啟用,停用後保留資料但不可使用 | active flag`
  - `is_deleted` → `軟刪除標記,查詢預設過濾 is_deleted=FALSE | soft-delete flag`
  - `created_at` → `建立時間(UTC+8) | created at`
  - `updated_at` → `更新時間(UTC+8,由 trigger 維護) | updated at`
- **不**動 `Base`、**不**新增欄位、**不**碰任何 model 子類。
- `pid` / `<entity>_uid` 不在本 mixin(各 model 自定義),由 task-203/204/205 各自補,不屬本 task。

## Acceptance

- [ ] 四欄皆有 comment(以既有 model 驗證繼承結果):`cd backend && uv run python -c "from app.models import Model
for n in ('is_active','is_deleted','created_at','updated_at'):
    assert Model.__table__.c[n].comment, n"`
- [ ] `cd backend && uv run ruff check app/models/base.py && uv run mypy app/models/base.py`
- [ ] 全 model 仍可匯入:`cd backend && uv run python -c "import app.models"`

## 必讀檔(Just-in-time)
- `04-databases/00-overview.md`(§ 自我說明 + BaseModel)
- `04-databases/90-project-database.md`(§ 1 必備欄位 + § 3.5)
