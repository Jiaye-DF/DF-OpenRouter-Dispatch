from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import BigInteger, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AllowedModel(Base, TimestampMixin):
    """Sync 模型白名單 — 只有此表中 is_active=TRUE 的 model_key,sync 後才會被啟用。"""

    __tablename__ = "allowed_models"

    __table_args__ = (
        sa.Index(
            "idx_allowed_models_active",
            "model_key",
            postgresql_where=sa.text("(is_active = true) AND (is_deleted = false)"),
        ),
        {"comment": "模型白名單"},
    )

    pid: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        comment="內部自增主鍵,禁對外暴露 | internal auto-increment PK",
    )
    allowed_model_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        unique=True,
        nullable=False,
        comment="對外 UUID 識別(UUIDv7) | external UID",
    )
    model_key: Mapped[str] = mapped_column(
        String(256),
        unique=True,
        nullable=False,
        comment="白名單 model_key,sync 後僅此表 is_active=TRUE 者啟用 | whitelisted model key",
    )
    note: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="備註 | note",
    )
