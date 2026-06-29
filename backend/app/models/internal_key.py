from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import BigInteger, Integer, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class InternalKey(Base, TimestampMixin):
    """企業內部 OpenAI-compatible LLM server 連線設定(per-Key,v1.2)。

    與 `openrouter_keys` 平行,但**全平台共用**(無 `department_uid`)。
    `api_key` 可選 — 內網信任時為 NULL,否則以 AES-256-GCM 加密儲存於 `key_ciphertext`。
    """

    __tablename__ = "internal_keys"

    __table_args__ = (
        sa.Index(
            "idx_internal_keys_active",
            "is_active",
            postgresql_where=sa.text("(is_deleted = false)"),
        ),
        sa.CheckConstraint("rpm_limit >= 0", name="chk_internal_keys_rpm"),
        sa.CheckConstraint(
            "min_request_interval_ms >= 0", name="chk_internal_keys_min_interval"
        ),
        {"comment": "內部金鑰"},
    )

    pid: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        comment="內部自增主鍵,禁對外暴露 | internal auto-increment PK",
    )
    internal_key_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        unique=True,
        nullable=False,
        comment="對外 UUID 識別(UUIDv7) | external UID",
    )
    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="連線設定顯示名稱(管理用,非機密) | display name",
    )
    base_url: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        comment="內部 OpenAI-compatible LLM server base URL | internal LLM server base URL",
    )
    key_ciphertext: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        nullable=True,
        comment="內網 API Key 密文(AES-256-GCM;內網信任時為 NULL) | encrypted API key ciphertext (nullable)",
    )
    key_last4: Mapped[str | None] = mapped_column(
        String(8),
        nullable=True,
        comment="金鑰末四碼(供顯示遮罩,非完整明文) | last 4 chars for masked display",
    )

    # 速率限制(per-Key;0 = 不限)
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
