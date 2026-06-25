from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import BigInteger, String, Text
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    __table_args__ = (
        sa.Index(
            "idx_audit_logs_actor_time",
            "actor_user_uid",
            sa.text("created_at DESC"),
        ),
        sa.Index(
            "idx_audit_logs_target_time",
            "target_type",
            "target_uid",
            sa.text("created_at DESC"),
        ),
        {"comment": "稽核紀錄"},
    )

    pid: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        comment="內部自增主鍵,禁對外暴露 | internal auto-increment PK",
    )
    audit_log_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        unique=True,
        nullable=False,
        comment="對外 UUID 識別(UUIDv7) | external UID",
    )
    actor_user_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        comment="操作者 user_uid | actor user UID",
    )
    actor_role: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        comment="操作者角色 | actor role",
    )
    action: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="操作動作 | action",
    )
    target_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="操作對象類型 | target entity type",
    )
    target_uid: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="操作對象 UID;NULL = 無特定對象 | target UID",
    )
    result: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="success",
        comment="操作結果(success/failure) | action result",
    )
    detail: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="操作明細描述 | detail description",
    )
    ip: Mapped[str | None] = mapped_column(
        INET,
        nullable=True,
        comment="操作來源 IP | source IP",
    )
    extra: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="額外結構化資料 | extra structured data",
    )
