from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import BigInteger, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    __table_args__ = (
        sa.Index(
            "uq_projects_dept_code",
            "department_uid",
            sa.text("lower((code)::text)"),
            unique=True,
            postgresql_where=sa.text("is_deleted = false"),
        ),
        sa.ForeignKeyConstraint(
            ["department_uid"],
            ["departments.department_uid"],
            name="projects_department_uid_fkey",
        ),
        {"comment": "專案"},
    )

    pid: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        comment="內部自增主鍵,禁對外暴露 | internal auto-increment PK",
    )
    project_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        unique=True,
        nullable=False,
        comment="對外 UUID 識別(UUIDv7) | external UID",
    )
    department_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        comment="所屬部門 UID(關聯 departments) | department UID",
    )
    code: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="專案代碼(Snowflake,呼叫端 X-Project-Code) | project code",
    )
    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="專案名稱 | project name",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="專案說明 | description",
    )
