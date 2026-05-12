from uuid import UUID

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

    pid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    internal_key_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), unique=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    key_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    key_last4: Mapped[str | None] = mapped_column(String(8), nullable=True)

    # 速率限制(per-Key;0 = 不限)
    rpm_limit: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    min_request_interval_ms: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
