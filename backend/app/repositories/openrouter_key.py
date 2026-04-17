from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.openrouter_key import OpenRouterKey


class OpenRouterKeyRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_uid(self, openrouter_key_uid: UUID) -> OpenRouterKey | None:
        stmt = select(OpenRouterKey).where(
            OpenRouterKey.openrouter_key_uid == openrouter_key_uid,
            OpenRouterKey.is_deleted.is_(False),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list(
        self,
        *,
        page: int,
        size: int,
        department_uid: UUID | None = None,
    ) -> tuple[list[OpenRouterKey], int]:
        stmt = select(OpenRouterKey).where(OpenRouterKey.is_deleted.is_(False))
        count_stmt = (
            select(func.count())
            .select_from(OpenRouterKey)
            .where(OpenRouterKey.is_deleted.is_(False))
        )
        if department_uid is not None:
            stmt = stmt.where(OpenRouterKey.department_uid == department_uid)
            count_stmt = count_stmt.where(OpenRouterKey.department_uid == department_uid)
        stmt = (
            stmt.order_by(OpenRouterKey.pid.desc()).offset((page - 1) * size).limit(size)
        )
        items = list((await self.db.execute(stmt)).scalars().all())
        total = int((await self.db.execute(count_stmt)).scalar_one())
        return items, total

    async def list_active_by_department(self, department_uid: UUID) -> list[OpenRouterKey]:
        stmt = select(OpenRouterKey).where(
            OpenRouterKey.department_uid == department_uid,
            OpenRouterKey.is_active.is_(True),
            OpenRouterKey.is_deleted.is_(False),
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def count_active_by_department(self, department_uid: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(OpenRouterKey)
            .where(
                OpenRouterKey.department_uid == department_uid,
                OpenRouterKey.is_active.is_(True),
                OpenRouterKey.is_deleted.is_(False),
            )
        )
        return int((await self.db.execute(stmt)).scalar_one())

    def add(self, row: OpenRouterKey) -> None:
        self.db.add(row)

    async def update_fields(self, row: OpenRouterKey, **fields: Any) -> None:
        for k, v in fields.items():
            setattr(row, k, v)
        await self.db.flush()
