from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.internal_key import InternalKey


class InternalKeyRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list(
        self,
        *,
        page: int = 1,
        size: int = 50,
    ) -> tuple[list[InternalKey], int]:
        stmt = select(InternalKey).where(InternalKey.is_deleted.is_(False))
        count_stmt = (
            select(func.count())
            .select_from(InternalKey)
            .where(InternalKey.is_deleted.is_(False))
        )
        stmt = (
            stmt.order_by(InternalKey.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        items = list((await self.db.execute(stmt)).scalars().all())
        total = int((await self.db.execute(count_stmt)).scalar_one())
        return items, total

    async def list_active(self) -> list[InternalKey]:
        stmt = select(InternalKey).where(
            InternalKey.is_active.is_(True),
            InternalKey.is_deleted.is_(False),
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_by_uid(self, internal_key_uid: UUID) -> InternalKey | None:
        stmt = select(InternalKey).where(
            InternalKey.internal_key_uid == internal_key_uid,
            InternalKey.is_deleted.is_(False),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    def add(self, row: InternalKey) -> None:
        self.db.add(row)
