"""v1.9.0:api_key_requests 表 — API Key 申請表單(送出 + 檢視)。

member / admin 皆可送出申請,寫入本表;admin 看全部、member 只看自己。
本版只做送出 + 檢視,status 恆為 "pending"(審核流轉留待 v1.9.1)。

Revision ID: 0012_api_key_requests
Revises: 0011_usage_log_used_tools
Create Date: 2026-06-17
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision: str = "0012_api_key_requests"
down_revision: Union[str, Sequence[str], None] = "0011_usage_log_used_tools"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "api_key_requests",
        sa.Column("pid", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("request_uid", pg.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("applicant_user_uid", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("department_name", sa.String(length=128), nullable=False),
        sa.Column("department_code", sa.String(length=32), nullable=False),
        sa.Column("project_name", sa.String(length=128), nullable=False),
        sa.Column("project_url", sa.String(length=512), nullable=False),
        sa.Column("owner_name", sa.String(length=64), nullable=False),
        sa.Column("owner_email", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    # member 過濾用
    op.create_index(
        "idx_api_key_requests_applicant",
        "api_key_requests",
        ["applicant_user_uid"],
        postgresql_where=sa.text("is_deleted = FALSE"),
    )
    # 列表排序用
    op.create_index(
        "idx_api_key_requests_created_at",
        "api_key_requests",
        ["created_at"],
        postgresql_where=sa.text("is_deleted = FALSE"),
    )
    op.execute(
        "CREATE TRIGGER trg_api_key_requests_updated_at "
        "BEFORE UPDATE ON api_key_requests "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_api_key_requests_updated_at ON api_key_requests"
    )
    op.drop_index("idx_api_key_requests_created_at", table_name="api_key_requests")
    op.drop_index("idx_api_key_requests_applicant", table_name="api_key_requests")
    op.drop_table("api_key_requests")
