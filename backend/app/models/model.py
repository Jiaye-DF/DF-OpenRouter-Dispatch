from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Model(Base, TimestampMixin):
    __tablename__ = "models"

    pid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    model_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), unique=True, nullable=False
    )

    # OpenRouter 為事實來源,僅 sync 寫入
    openrouter_model_id: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    context_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    modality: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tokenizer: Mapped[str | None] = mapped_column(String(64), nullable=True)

    price_prompt_per_token: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 12), nullable=True
    )
    price_completion_per_token: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 12), nullable=True
    )
    price_image_per_image: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 12), nullable=True
    )
    price_request_flat: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 12), nullable=True
    )

    # 平台控管(可由 admin 編輯)
    is_moderated: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default="false"
    )
    # tier_key 為 model_tiers.key 的軟引用;NULL = 未分級
    tier_key: Mapped[str | None] = mapped_column(String(32), nullable=True)

    openrouter_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
