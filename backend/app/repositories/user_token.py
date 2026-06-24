from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_token import UserToken


class UserTokenRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_active_by_user(self, user_uid: UUID) -> UserToken | None:
        """該使用者目前有效(未撤銷、未刪除)的 token;供沿用同一把。"""
        stmt = (
            select(UserToken)
            .where(
                UserToken.user_uid == user_uid,
                UserToken.revoked_at.is_(None),
                UserToken.is_deleted.is_(False),
            )
            .order_by(UserToken.issued_at.desc())
            .limit(1)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_user_and_token(
        self, user_uid: UUID, token: str
    ) -> UserToken | None:
        """以 (使用者, token 明文) 比對新表;供驗證鏈判斷該 token 是否已落地。

        找得到 → 用本表 revoked_at 判定撤銷;找不到 → 由呼叫端回退舊浮水印方法,
        確保已發出、未落地的舊 token 不會無故失效。
        """
        stmt = select(UserToken).where(
            UserToken.user_uid == user_uid,
            UserToken.token == token,
            UserToken.is_deleted.is_(False),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    def add(self, row: UserToken) -> None:
        self.db.add(row)

    async def revoke_active_by_user(
        self, user_uid: UUID, now: datetime, reason: str | None
    ) -> None:
        """把該使用者所有有效 token 標記撤銷(撤銷流程兩張表都要掃)。"""
        stmt = (
            update(UserToken)
            .where(
                UserToken.user_uid == user_uid,
                UserToken.revoked_at.is_(None),
                UserToken.is_deleted.is_(False),
            )
            .values(revoked_at=now, revoked_reason=reason, is_active=False)
        )
        await self.db.execute(stmt)
