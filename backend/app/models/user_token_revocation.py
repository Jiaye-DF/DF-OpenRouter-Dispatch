from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class UserTokenRevocation(Base, TimestampMixin):
    __tablename__ = "user_tokens_revocations"

    pid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_tokens_revocation_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), unique=True, nullable=False
    )
    user_uid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    revoked_issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
