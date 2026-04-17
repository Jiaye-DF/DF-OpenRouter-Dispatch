from uuid import UUID

from sqlalchemy import BigInteger, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class OpenRouterKey(Base, TimestampMixin):
    __tablename__ = "openrouter_keys"

    pid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    openrouter_key_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), unique=True, nullable=False
    )
    department_uid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    key_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    key_last4: Mapped[str] = mapped_column(String(8), nullable=False)
