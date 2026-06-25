from decimal import Decimal
from uuid import UUID

from sqlalchemy import BigInteger, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ModelTier(Base, TimestampMixin):
    __tablename__ = "model_tiers"

    __table_args__ = ({"comment": "模型分級"},)

    pid: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        comment="內部自增主鍵,禁對外暴露 | internal auto-increment PK",
    )
    tier_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        unique=True,
        nullable=False,
        comment="對外 UUID 識別(UUIDv7) | external UID",
    )

    key: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        nullable=False,
        comment="分級 key,一旦建立不可改名(避免 models.tier_key 失聯) | tier key (immutable)",
    )
    label_zh: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="中文顯示名 | Chinese label",
    )
    label_en: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="英文顯示名 | English label",
    )
    color: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
        comment="顯示色碼 | display color",
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="排序順序 | sort order",
    )

    auto_match_min_price_per_mtok: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 12),
        nullable=True,
        comment="同步時自動匹配的價格下限(USD per token);NULL = 不參與自動匹配 | auto-match min price",
    )
    auto_match_max_price_per_mtok: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 12),
        nullable=True,
        comment="同步時自動匹配的價格上限(USD per token);NULL = 不參與自動匹配 | auto-match max price",
    )
