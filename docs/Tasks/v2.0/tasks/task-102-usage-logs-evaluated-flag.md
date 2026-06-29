---
id: task-102
title: usage_logs.ai_evaluated_at 旗標欄(migration 0020 + model)
status: pending
parallel: true
depends_on: []
affected_files:
  - backend/alembic/versions/0020_usage_logs_ai_evaluated_at.py
  - backend/app/models/usage_log.py
estimated_hours: 2
---

## 目標

為 `usage_logs` 加派發游標欄 `ai_evaluated_at`(NULL=未評審),供 task-106 dispatcher 掃待評審筆;含 Alembic migration 與 SQLAlchemy 模型欄位。

## 範圍

- migration `0020_usage_logs_ai_evaluated_at.py`:`usage_logs` 加 `ai_evaluated_at TIMESTAMP(timezone=True) NULL`(對齊 `04-databases/06-timezone.md` 全棧 UTC+8)。
- 加 partial index 撈待評審筆:`WHERE ai_evaluated_at IS NULL`(對齊 `04-databases/09-indexes-and-perf.md`)。
- `backend/app/models/usage_log.py`:加對應 `ai_evaluated_at` mapped column(nullable)。
- **note**:propose §4 寫 `0019`,但 `0019` 已被 v2.0.0 foundation 佔用,本 task 用 **`0020`**,`down_revision` 指向 `0019`。

## Acceptance

- [ ] migration revision id ≤ 32 字元(避免 `alembic_version VARCHAR(32)` 截斷,重蹈 0016/0017 deploy 失敗)
- [ ] `cd backend && uv run alembic upgrade head` 成功,`usage_logs` 出現 `ai_evaluated_at` 欄與 partial index
- [ ] `cd backend && uv run alembic downgrade -1` round-trip 成功(欄與 index 移除無殘留)
- [ ] `cd backend && uv run python -c "from app.models.usage_log import UsageLog; print(UsageLog.ai_evaluated_at)"` 無錯
- [ ] `cd backend && uv run ruff check app/models/usage_log.py` 無 warning;`uv run mypy app/models/usage_log.py` green

## 必讀檔(Just-in-time)

- `AGENTS.md`
- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/00-overview/05-timezone.md`
- `docs/Design-Base/04-databases/00-overview.md`
- `docs/Design-Base/04-databases/06-timezone.md`
- `docs/Design-Base/04-databases/08-alembic.md`
- `docs/Design-Base/04-databases/09-indexes-and-perf.md`
- `docs/Design-Base/04-databases/90-project-database.md`
