from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import BigInteger, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Department(Base, TimestampMixin):
    __tablename__ = "departments"

    __table_args__ = (
        sa.Index(
            "uq_departments_code",
            sa.text("lower((code)::text)"),
            unique=True,
            postgresql_where=sa.text("is_deleted = false"),
        ),
        {"comment": "部門"},
    )

    pid: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        comment="內部自增主鍵,禁對外暴露 | internal auto-increment PK",
    )
    department_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        unique=True,
        nullable=False,
        comment="對外 UUID 識別(UUIDv7) | external UID",
    )
    code: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="成本中心代碼 | cost center code",
    )
    org_code: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        comment="組織代碼 | organization code",
    )
    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="部門名稱 | department name",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="部門說明 | description",
    )
