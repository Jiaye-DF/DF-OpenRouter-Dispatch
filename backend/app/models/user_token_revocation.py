from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class UserTokenRevocation(Base, TimestampMixin):
    __tablename__ = "user_tokens_revocations"

    __table_args__ = (
        sa.Index(
            "idx_user_tokens_revocations_user",
            "user_uid",
            postgresql_where=sa.text("is_deleted = false"),
        ),
        sa.ForeignKeyConstraint(
            ["user_uid"],
            ["users.user_uid"],
            name="user_tokens_revocations_user_uid_fkey",
        ),
        {"comment": "使用者權杖撤銷"},
    )

    pid: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        comment="內部自增主鍵,禁對外暴露 | internal auto-increment PK",
    )
    user_tokens_revocation_uid: Mapped[UUID] = mapped_column(
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
    revoked_issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="被撤銷 token 的簽發時間(浮水印門檻,早於此一律失效) | revoked token issued-at watermark",
    )
    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="撤銷時間 | revoked at",
    )
    reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="撤銷原因 | revoked reason",
    )
