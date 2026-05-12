from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model import Model


class ModelRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def find_by_key(self, mid: str) -> Model | None:
        stmt = select(Model).where(
            Model.model_key == mid,
            Model.is_deleted.is_(False),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_uid(self, model_uid: UUID) -> Model | None:
        stmt = select(Model).where(
            Model.model_uid == model_uid,
            Model.is_deleted.is_(False),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_active(self) -> list[Model]:
        stmt = select(Model).where(
            Model.is_active.is_(True),
            Model.is_deleted.is_(False),
        ).order_by(Model.model_key.asc())
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_all(
        self,
        *,
        page: int = 1,
        size: int = 50,
        include_inactive: bool = False,
        modality: str | None = None,
        tier_key: str | None = None,
    ) -> tuple[list[Model], int]:
        stmt = select(Model).where(Model.is_deleted.is_(False))
        count_stmt = (
            select(func.count())
            .select_from(Model)
            .where(Model.is_deleted.is_(False))
        )
        if not include_inactive:
            stmt = stmt.where(Model.is_active.is_(True))
            count_stmt = count_stmt.where(Model.is_active.is_(True))
        if modality is not None:
            stmt = stmt.where(Model.modality == modality)
            count_stmt = count_stmt.where(Model.modality == modality)
        if tier_key is not None:
            stmt = stmt.where(Model.tier_key == tier_key)
            count_stmt = count_stmt.where(Model.tier_key == tier_key)
        stmt = (
            stmt.order_by(Model.model_key.asc())
            .offset((page - 1) * size)
            .limit(size)
        )
        items = list((await self.db.execute(stmt)).scalars().all())
        total = int((await self.db.execute(count_stmt)).scalar_one())
        return items, total

    def add(self, row: Model) -> None:
        self.db.add(row)

    async def update_admin_fields(self, model_uid: UUID, **patch: Any) -> Model | None:
        """admin 僅可改 is_active / tier_key;其他欄位由呼叫端把關。"""
        row = await self.get_by_uid(model_uid)
        if row is None:
            return None
        for k, v in patch.items():
            setattr(row, k, v)
        await self.db.flush()
        return row

    async def update_fields(self, row: Model, **fields: Any) -> None:
        for k, v in fields.items():
            setattr(row, k, v)
        await self.db.flush()
