from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.allowed_model import AllowedModel


class AllowedModelRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_active_keys(self) -> set[str]:
        """回傳當前 active 且未刪除的 model_key 集合 — sync 套白名單時使用。"""
        stmt = select(AllowedModel.model_key).where(
            AllowedModel.is_active.is_(True),
            AllowedModel.is_deleted.is_(False),
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        return set(rows)

    async def list_all(self) -> list[AllowedModel]:
        """後台列表 — 含 inactive,但不含 is_deleted。"""
        stmt = (
            select(AllowedModel)
            .where(AllowedModel.is_deleted.is_(False))
            .order_by(AllowedModel.pid.asc())
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_by_uid(self, uid: UUID) -> AllowedModel | None:
        stmt = select(AllowedModel).where(
            AllowedModel.allowed_model_uid == uid,
            AllowedModel.is_deleted.is_(False),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def find_by_key(self, model_key: str) -> AllowedModel | None:
        stmt = select(AllowedModel).where(AllowedModel.model_key == model_key)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    def add(self, row: AllowedModel) -> None:
        self.db.add(row)
