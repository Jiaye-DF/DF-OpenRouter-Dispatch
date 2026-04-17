from uuid import UUID

from sqlalchemy import BigInteger, String, Text
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    pid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    audit_log_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), unique=True, nullable=False
    )
    actor_user_uid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(16), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_uid: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    result: Mapped[str] = mapped_column(String(16), nullable=False, default="success")
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    extra: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
