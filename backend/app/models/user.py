from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import BigInteger, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    __table_args__ = (
        sa.Index(
            "idx_users_department_uid",
            "department_uid",
            postgresql_where=sa.text("is_deleted = false"),
        ),
        sa.Index(
            "idx_users_sso_user_id",
            "sso_user_id",
            postgresql_where=sa.text("is_deleted = false"),
        ),
        sa.Index(
            "uq_users_account",
            sa.text("lower((account)::text)"),
            unique=True,
            postgresql_where=sa.text("is_deleted = false"),
        ),
        sa.ForeignKeyConstraint(
            ["department_uid"],
            ["departments.department_uid"],
            name="users_department_uid_fkey",
        ),
        {"comment": "使用者"},
    )

    pid: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        comment="內部自增主鍵,禁對外暴露 | internal auto-increment PK",
    )
    user_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        unique=True,
        nullable=False,
        comment="對外 UUID 識別(UUIDv7) | external UID",
    )
    account: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="登入帳號 | login account",
    )
    username: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="使用者顯示名稱(PII) | display name (PII)",
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="密碼雜湊(argon2id) | password hash",
    )
    role: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        comment="角色權限 | role",
    )
    department_uid: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="所屬部門 UID(關聯 departments) | department UID",
    )
    employee_id: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        comment="員工編號(PII) | employee ID (PII)",
    )
    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="電子郵件(PII) | email (PII)",
    )
    sso_user_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="DF-SSO 的 userId(azure oid),供 back-channel logout 反查本地帳號 | DF-SSO user ID",
    )
    failed_login_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="登入失敗次數 | failed login count",
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="帳號鎖定至此時間 | locked until",
    )
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="密碼最後變更時間 | password changed at",
    )
