from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import BigInteger, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class SdkApiKey(Base, TimestampMixin):
    __tablename__ = "sdk_api_keys"

    __table_args__ = (
        sa.Index(
            "idx_sdk_api_keys_dept",
            "department_uid",
            postgresql_where=sa.text("(is_deleted = false)"),
        ),
        sa.Index(
            "idx_sdk_api_keys_prefix",
            "key_prefix",
            postgresql_where=sa.text("(is_deleted = false)"),
        ),
        sa.ForeignKeyConstraint(
            ["department_uid"],
            ["departments.department_uid"],
            name="sdk_api_keys_department_uid_fkey",
        ),
        {"comment": "SDK API 金鑰"},
    )

    pid: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        comment="內部自增主鍵,禁對外暴露 | internal auto-increment PK",
    )
    sdk_api_key_uid: Mapped[UUID] = mapped_column(
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
    key_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="金鑰驗證雜湊(argon2id,不可逆) | key verification hash (argon2id)",
    )
    key_prefix: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="金鑰前綴(供顯示遮罩與查找,非完整明文) | key prefix for masked display",
    )
    # 完整 key 明文(v1.5 修訂)。後台可直接編輯;舊資料 NULL → UI 顯示「請重新建立」。
    # 不走加密 — 業務要求 DB 可直編填值,接受 DB dump 等同明文外洩的風險取捨。
    key_values: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="完整金鑰明文,供後台直編填值(業務取捨,未加密;舊資料 NULL=請重建) | full key plaintext (unencrypted, business trade-off)",
    )
