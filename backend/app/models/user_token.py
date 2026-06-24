from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class UserToken(Base, TimestampMixin):
    """使用者目前持有的 User Token(一人一把,落地儲存供沿用/追蹤)。

    與 user_tokens_revocations(浮水印,驗證鏈強制失效依據)分工:
    本表存「token 明文」,供同一使用者重複申請時沿用同一把、admin 追蹤與重送。
    撤銷時兩張表都會處理:浮水印讓 token 於驗證鏈失效,本表 revoked_at 標記停用。
    """

    __tablename__ = "user_tokens"

    pid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_tokens_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), unique=True, nullable=False
    )
    user_uid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    token: Mapped[str] = mapped_column(Text, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
