from uuid import UUID

from sqlalchemy import BigInteger, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class SdkApiKey(Base, TimestampMixin):
    __tablename__ = "sdk_api_keys"

    pid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    sdk_api_key_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), unique=True, nullable=False
    )
    department_uid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(32), nullable=False)
    # AES-GCM 加密的完整 key(v1.5 新增)。NULL = migration 前舊資料無法復原明文。
    key_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
