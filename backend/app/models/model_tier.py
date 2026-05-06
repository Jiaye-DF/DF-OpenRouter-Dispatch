from decimal import Decimal
from uuid import UUID

from sqlalchemy import BigInteger, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ModelTier(Base, TimestampMixin):
    __tablename__ = "model_tiers"

    pid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tier_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), unique=True, nullable=False
    )

    # key 一旦建立不可改名(避免 models.tier_key 失聯)
    key: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    label_zh: Mapped[str] = mapped_column(String(64), nullable=False)
    label_en: Mapped[str | None] = mapped_column(String(64), nullable=True)
    color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    # 同步時自動匹配的價格區間(USD per token);NULL = 不參與自動匹配
    auto_match_min_price_per_mtok: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 12), nullable=True
    )
    auto_match_max_price_per_mtok: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 12), nullable=True
    )
