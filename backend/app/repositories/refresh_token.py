from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_token import RefreshToken


class RefreshTokenRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_uid(self, refresh_token_uid: UUID | str) -> RefreshToken | None:
        stmt = select(RefreshToken).where(
            RefreshToken.refresh_token_uid == refresh_token_uid,
            RefreshToken.is_deleted.is_(False),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    def add(self, row: RefreshToken) -> None:
        self.db.add(row)

    async def revoke(
        self,
        row: RefreshToken,
        *,
        now: datetime,
        replaced_by_uid: UUID | None = None,
    ) -> None:
        row.revoked_at = now
        if replaced_by_uid is not None:
            row.replaced_by_uid = replaced_by_uid
        await self.db.flush()

    async def revoke_family(self, family_uid: UUID, *, now: datetime) -> None:
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.family_uid == family_uid, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await self.db.execute(stmt)

    async def revoke_all_for_user(self, user_uid: UUID, *, now: datetime) -> None:
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.user_uid == user_uid, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await self.db.execute(stmt)
