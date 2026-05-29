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

    async def get_by_email(self, email: str) -> User | None:
        """以 Email(不分大小寫)查使用者;供 DF-SSO 登入對應本地帳號。

        email 無唯一約束,取第一筆即可(資料正常時不會重複)。
        """
        stmt = select(User).where(
            func.lower(User.email) == email.lower(),
            User.is_deleted.is_(False),
        )
        return (await self.db.execute(stmt)).scalars().first()

    async def get_by_sso_user_id(self, sso_user_id: str) -> User | None:
        """以 SSO userId(azure oid)查使用者;供 back-channel logout 反查。"""
        stmt = select(User).where(
            User.sso_user_id == sso_user_id,
            User.is_deleted.is_(False),
        )
        return (await self.db.execute(stmt)).scalars().first()

    async def list(
        self,
        *,
        page: int,
        size: int,
        department_uid: UUID | None = None,
        role: str | None = None,
        q: str | None = None,
    ) -> tuple[list[User], int]:
        stmt = select(User).where(User.is_deleted.is_(False))
        count_stmt = select(func.count()).select_from(User).where(User.is_deleted.is_(False))
        if department_uid is not None:
            stmt = stmt.where(User.department_uid == department_uid)
            count_stmt = count_stmt.where(User.department_uid == department_uid)
        if role is not None and role.strip():
            stmt = stmt.where(User.role == role)
            count_stmt = count_stmt.where(User.role == role)
        if q is not None and q.strip():
            kw = f"%{q.strip().lower()}%"
            cond = func.lower(User.username).like(kw) | func.lower(
                func.coalesce(User.email, "")
            ).like(kw)
            stmt = stmt.where(cond)
            count_stmt = count_stmt.where(cond)
        stmt = stmt.order_by(User.pid.desc()).offset((page - 1) * size).limit(size)
        items = list((await self.db.execute(stmt)).scalars().all())
        total = int((await self.db.execute(count_stmt)).scalar_one())
        return items, total

    async def list_for_dropdown(
        self,
        *,
        department_uid: UUID | None = None,
        limit: int = 2000,
    ) -> list[User]:
        """供儀表板下拉用的精簡列表(免分頁,內部 limit 保險)。"""
        stmt = (
            select(User)
            .where(User.is_deleted.is_(False), User.is_active.is_(True))
            .order_by(User.username.asc())
            .limit(limit)
        )
        if department_uid is not None:
            stmt = stmt.where(User.department_uid == department_uid)
        return list((await self.db.execute(stmt)).scalars().all())

    def add(self, user: User) -> None:
        self.db.add(user)

    async def update_fields(self, user: User, **fields: Any) -> None:
        for k, v in fields.items():
            setattr(user, k, v)
        await self.db.flush()
