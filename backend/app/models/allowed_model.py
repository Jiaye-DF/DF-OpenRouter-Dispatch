from uuid import UUID

from sqlalchemy import BigInteger, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AllowedModel(Base, TimestampMixin):
    """Sync 模型白名單 — 只有此表中 is_active=TRUE 的 model_key,sync 後才會被啟用。"""

    __tablename__ = "allowed_models"

    pid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    allowed_model_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), unique=True, nullable=False
    )
    model_key: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
