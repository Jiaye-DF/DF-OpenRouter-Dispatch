from uuid import UUID

from sqlalchemy import BigInteger, String, Text
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
    # 完整 key 明文(v1.5 修訂)。後台可直接編輯;舊資料 NULL → UI 顯示「請重新建立」。
    # 不走加密 — 業務要求 DB 可直編填值,接受 DB dump 等同明文外洩的風險取捨。
    key_values: Mapped[str | None] = mapped_column(Text, nullable=True)
