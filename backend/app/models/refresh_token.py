from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class RefreshToken(Base, TimestampMixin):
    __tablename__ = "refresh_tokens"

    __table_args__ = (
        sa.Index(
            "idx_refresh_tokens_family",
            "family_uid",
            postgresql_where=sa.text("is_deleted = false"),
        ),
        sa.Index(
            "idx_refresh_tokens_user_uid",
            "user_uid",
            postgresql_where=sa.text("is_deleted = false"),
        ),
        {"comment": "更新權杖"},
    )

    pid: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        comment="內部自增主鍵,禁對外暴露 | internal auto-increment PK",
    )
    refresh_token_uid: Mapped[UUID] = mapped_column(
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
    family_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        comment="token 家族 UID(rotation 鏈,偵測重放) | token family UID",
    )
    token_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="refresh token 雜湊 | token hash",
    )
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="簽發時間 | issued at",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="到期時間 | expires at",
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="撤銷時間 | revoked at",
    )
    replaced_by_uid: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="被哪張新 token 取代(rotation) | replaced-by token UID",
    )
    user_agent: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        comment="簽發時的 User-Agent | user agent",
    )
    ip: Mapped[str | None] = mapped_column(
        INET,
        nullable=True,
        comment="簽發時的來源 IP | source IP",
    )
