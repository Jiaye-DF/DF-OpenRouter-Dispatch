from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model import Model
from app.models.model_tier import ModelTier


class ModelTierRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_uid(self, tier_uid: UUID) -> ModelTier | None:
        stmt = select(ModelTier).where(
            ModelTier.tier_uid == tier_uid,
            ModelTier.is_deleted.is_(False),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def find_by_key(self, key: str) -> ModelTier | None:
        stmt = select(ModelTier).where(
            ModelTier.key == key,
            ModelTier.is_deleted.is_(False),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_active(self) -> list[ModelTier]:
        stmt = (
            select(ModelTier)
            .where(
                ModelTier.is_active.is_(True),
                ModelTier.is_deleted.is_(False),
            )
            .order_by(ModelTier.sort_order.asc(), ModelTier.pid.asc())
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_all(self) -> list[ModelTier]:
        stmt = (
            select(ModelTier)
            .where(ModelTier.is_deleted.is_(False))
            .order_by(ModelTier.sort_order.asc(), ModelTier.pid.asc())
        )
        return list((await self.db.execute(stmt)).scalars().all())

    def add(self, row: ModelTier) -> None:
        self.db.add(row)

    async def update_fields(self, row: ModelTier, **fields: Any) -> None:
        for k, v in fields.items():
            setattr(row, k, v)
        await self.db.flush()

    async def is_in_use(self, tier_key: str) -> list[Model]:
        """回傳引用此 tier 的 active models 列表;tier 服務於拒刪時用於 detail.using_models。"""
        stmt = select(Model).where(
            Model.tier_key == tier_key,
            Model.is_deleted.is_(False),
        )
        return list((await self.db.execute(stmt)).scalars().all())
