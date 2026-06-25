from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
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

    __table_args__ = (
        sa.Index(
            "idx_user_tokens_user_uid",
            "user_uid",
            postgresql_where=sa.text("is_deleted = false"),
        ),
        sa.Index(
            "uq_user_tokens_active_user",
            "user_uid",
            unique=True,
            postgresql_where=sa.text("revoked_at IS NULL AND is_deleted = false"),
        ),
        {"comment": "使用者權杖"},
    )

    pid: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        comment="內部自增主鍵,禁對外暴露 | internal auto-increment PK",
    )
    user_tokens_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        unique=True,
        nullable=False,
        comment="對外 UUID 識別(UUIDv7) | external UID",
    )
    user_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        comment="所屬使用者 UID(關聯 users) | user UID",
    )
    token: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="User Token 明文,供重複申請沿用與追蹤 | user token value",
    )
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="簽發時間 | issued at",
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="撤銷時間(標記停用) | revoked at",
    )
    revoked_reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="撤銷原因 | revoked reason",
    )
