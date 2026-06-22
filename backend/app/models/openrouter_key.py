from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, LargeBinary, Numeric, String
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

    # OpenRouter 帳號餘額(由 sync 流程回填;一般使用者不可見,僅 admin)
    credits_used_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6), nullable=True
    )
    credits_limit_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6), nullable=True
    )
    credits_is_free_tier: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    credits_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # v1.2 速率限制(per-Key);0 = 不限
    rpm_limit: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    min_request_interval_ms: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    # 壞 key 短期停用:dispatch 撞 401(失效)/ 402(餘額不足)時設為 now()+cooldown,
    # 派工查詢(list_active_by_department)會跳過未到期者;到期自動恢復,不需人工。
    disabled_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
