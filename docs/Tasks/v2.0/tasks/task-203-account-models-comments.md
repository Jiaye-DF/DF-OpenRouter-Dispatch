---
id: task-203
title: 帳號群 6 表 model comment=
status: done
parallel: true
depends_on: []
affected_files:
  - backend/app/models/user.py
  - backend/app/models/department.py
  - backend/app/models/project.py
  - backend/app/models/refresh_token.py
  - backend/app/models/user_token.py
  - backend/app/models/user_token_revocation.py
estimated_hours: 3
---

## 目標

為帳號群 6 張表(`users` / `departments` / `projects` / `refresh_tokens` / `user_tokens` / `user_tokens_revocations`)的 model 各**非-mixin 欄位**補 `comment=`(含 `pid` / `<entity>_uid` 及全部業務欄位),作為 task-206 autogenerate 的真相源。

## 設計

- 逐欄 `mapped_column(..., comment=...)`,中英雙語(對齊 `04-databases/00-overview.md § 自我說明`)。
- `pid` / `<entity>_uid` 用 tasks-v2.0.2.md §「罐頭文案基準」逐字文案。
- 業務欄位優先轉用既有行內註解;無註解者依語意補一句。
- **不**改欄位型別 / nullable / 約束;**不**動 `TimestampMixin` 四欄(屬 task-202);**不**動 migration。

## Acceptance

- [ ] 6 表非-mixin 欄位皆有 comment:
```
cd backend && uv run python -c "
from app.models import User, Department, Project, RefreshToken, UserToken, UserTokenRevocation
MIXIN={'is_active','is_deleted','created_at','updated_at'}
for M in (User,Department,Project,RefreshToken,UserToken,UserTokenRevocation):
    for c in M.__table__.columns:
        if c.name in MIXIN: continue
        assert c.comment, f'{M.__tablename__}.{c.name} 缺 comment'
"
```
- [ ] `cd backend && uv run ruff check app/models/ && uv run mypy app/models/user.py app/models/department.py app/models/project.py app/models/refresh_token.py app/models/user_token.py app/models/user_token_revocation.py`

## 必讀檔(Just-in-time)
- `04-databases/00-overview.md`(§ 自我說明)
- `04-databases/90-project-database.md`(§ 1 / § 3.5)
