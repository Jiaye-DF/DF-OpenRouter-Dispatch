from datetime import datetime
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import BigInteger, Boolean, DateTime, Integer, LargeBinary, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class OpenRouterKey(Base, TimestampMixin):
    __tablename__ = "openrouter_keys"

    __table_args__ = (
        sa.Index(
            "idx_openrouter_keys_dept",
            "department_uid",
            postgresql_where=sa.text("((is_deleted = false) AND (is_active = true))"),
        ),
        sa.ForeignKeyConstraint(
            ["department_uid"],
            ["departments.department_uid"],
            name="openrouter_keys_department_uid_fkey",
        ),
        sa.CheckConstraint("rpm_limit >= 0", name="chk_openrouter_keys_rpm"),
        sa.CheckConstraint(
            "min_request_interval_ms >= 0", name="chk_openrouter_keys_min_interval"
        ),
        {"comment": "OpenRouter 金鑰"},
    )

    pid: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        comment="內部自增主鍵,禁對外暴露 | internal auto-increment PK",
    )
    openrouter_key_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        unique=True,
        nullable=False,
        comment="對外 UUID 識別(UUIDv7) | external UID",
    )
    department_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        comment="所屬部門(軟引用 departments.department_uid) | owning department",
    )
    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="金鑰顯示名稱(管理用,非機密) | key display name",
    )
    key_ciphertext: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
        comment="OpenRouter API Key 密文(AES-256-GCM 加密,金鑰由 ENCRYPTION_KEY 注入) | encrypted API key ciphertext",
    )
    key_prefix: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        comment="金鑰前綴(供顯示遮罩,非完整明文) | key prefix for masked display",
    )
    key_last4: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
        comment="金鑰末四碼(供顯示遮罩,非完整明文) | last 4 chars for masked display",
    )

    # OpenRouter 帳號餘額(由 sync 流程回填;一般使用者不可見,僅 admin)
    credits_used_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6),
        nullable=True,
        comment="OpenRouter 帳號已用額度(USD,sync 回填,僅 admin 可見) | credits used (USD)",
    )
    credits_limit_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6),
        nullable=True,
        comment="OpenRouter 帳號額度上限(USD,sync 回填;NULL=無上限) | credits limit (USD)",
    )
    credits_is_free_tier: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        comment="是否為免費方案帳號(sync 回填) | free tier flag",
    )
    credits_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="餘額最後同步時間(UTC+8) | credits last synced at",
    )

    # v1.2 速率限制(per-Key);0 = 不限
    rpm_limit: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="每分鐘請求上限(per-Key;0=不限) | requests-per-minute limit",
    )
    min_request_interval_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="最小請求間隔毫秒(per-Key;0=不限) | min request interval (ms)",
    )

    # 壞 key 短期停用:dispatch 撞 401(失效)/ 402(餘額不足)時設為 now()+cooldown,
    # 派工查詢(list_active_by_department)會跳過未到期者;到期自動恢復,不需人工。
    disabled_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="短期停用截止時間,撞 401/402 時設 now()+cooldown,到期自動恢復(UTC+8) | disabled until",
    )
