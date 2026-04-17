from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_token_revocation import UserTokenRevocation


class UserTokenRevocationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def latest_for_user(self, user_uid: UUID) -> UserTokenRevocation | None:
        stmt = (
            select(UserTokenRevocation)
            .where(
                UserTokenRevocation.user_uid == user_uid,
                UserTokenRevocation.is_deleted.is_(False),
            )
            .order_by(UserTokenRevocation.revoked_issued_at.desc())
            .limit(1)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    def add(self, row: UserTokenRevocation) -> None:
        self.db.add(row)
