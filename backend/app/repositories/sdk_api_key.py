from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sdk_api_key import SdkApiKey


class SdkApiKeyRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_uid(self, sdk_api_key_uid: UUID) -> SdkApiKey | None:
        stmt = select(SdkApiKey).where(
            SdkApiKey.sdk_api_key_uid == sdk_api_key_uid,
            SdkApiKey.is_deleted.is_(False),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list(
        self,
        *,
        page: int,
        size: int,
        department_uid: UUID | None = None,
    ) -> tuple[list[SdkApiKey], int]:
        stmt = select(SdkApiKey).where(SdkApiKey.is_deleted.is_(False))
        count_stmt = (
            select(func.count())
            .select_from(SdkApiKey)
            .where(SdkApiKey.is_deleted.is_(False))
        )
        if department_uid is not None:
            stmt = stmt.where(SdkApiKey.department_uid == department_uid)
            count_stmt = count_stmt.where(SdkApiKey.department_uid == department_uid)
        stmt = stmt.order_by(SdkApiKey.pid.desc()).offset((page - 1) * size).limit(size)
        items = list((await self.db.execute(stmt)).scalars().all())
        total = int((await self.db.execute(count_stmt)).scalar_one())
        return items, total

    async def get_active_by_department(self, department_uid: UUID) -> SdkApiKey | None:
        """取該部門最新一把仍啟用的 SDK 金鑰;供規則路由自動取用。"""
        stmt = (
            select(SdkApiKey)
            .where(
                SdkApiKey.department_uid == department_uid,
                SdkApiKey.is_active.is_(True),
                SdkApiKey.is_deleted.is_(False),
            )
            .order_by(SdkApiKey.pid.desc())
        )
        return (await self.db.execute(stmt)).scalars().first()

    async def list_active_by_prefix(self, prefix: str) -> list[SdkApiKey]:
        stmt = select(SdkApiKey).where(
            SdkApiKey.key_prefix == prefix,
            SdkApiKey.is_active.is_(True),
            SdkApiKey.is_deleted.is_(False),
        )
        return list((await self.db.execute(stmt)).scalars().all())

    def add(self, row: SdkApiKey) -> None:
        self.db.add(row)

    async def update_fields(self, row: SdkApiKey, **fields: Any) -> None:
        for k, v in fields.items():
            setattr(row, k, v)
        await self.db.flush()
