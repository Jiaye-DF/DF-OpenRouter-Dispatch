from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_uid(self, user_uid: UUID | str) -> User | None:
        stmt = select(User).where(User.user_uid == user_uid, User.is_deleted.is_(False))
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_account(self, account: str) -> User | None:
        stmt = select(User).where(
            func.lower(User.account) == account.lower(),
            User.is_deleted.is_(False),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list(
        self,
        *,
        page: int,
        size: int,
        department_uid: UUID | None = None,
    ) -> tuple[list[User], int]:
        stmt = select(User).where(User.is_deleted.is_(False))
        count_stmt = select(func.count()).select_from(User).where(User.is_deleted.is_(False))
        if department_uid is not None:
            stmt = stmt.where(User.department_uid == department_uid)
            count_stmt = count_stmt.where(User.department_uid == department_uid)
        stmt = stmt.order_by(User.pid.desc()).offset((page - 1) * size).limit(size)
        items = list((await self.db.execute(stmt)).scalars().all())
        total = int((await self.db.execute(count_stmt)).scalar_one())
        return items, total

    def add(self, user: User) -> None:
        self.db.add(user)

    async def update_fields(self, user: User, **fields: Any) -> None:
        for k, v in fields.items():
            setattr(user, k, v)
        await self.db.flush()
