"""v1.2 增量:internal_keys 表(per-Key DB-driven)。

Revision ID: 0003_internal_keys
Revises: 0002_provider_rate_limit
Create Date: 2026-05-12
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import context
from alembic import op

revision: str = "0003_internal_keys"
down_revision: Union[str, Sequence[str], None] = "0002_provider_rate_limit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "internal_keys",
        sa.Column("pid", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "internal_key_uid",
            pg.UUID(as_uuid=True),
            nullable=False,
            unique=True,
        ),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("base_url", sa.String(length=512), nullable=False),
        # api_key 可選(內網信任時為 NULL);有值則以 AES-256-GCM 加密
        sa.Column("key_ciphertext", sa.LargeBinary(), nullable=True),
        sa.Column("key_last4", sa.String(length=8), nullable=True),
        sa.Column(
            "rpm_limit",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "min_request_interval_ms",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
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
        sa.CheckConstraint("rpm_limit >= 0", name="chk_internal_keys_rpm"),
        sa.CheckConstraint(
            "min_request_interval_ms >= 0",
            name="chk_internal_keys_min_interval",
        ),
    )
    op.create_index(
        "idx_internal_keys_active",
        "internal_keys",
        ["is_active"],
        postgresql_where=sa.text("is_deleted = FALSE"),
    )
    # 沿用 set_updated_at trigger function(v1.0 baseline 已建立)
    op.execute(
        "CREATE TRIGGER trg_internal_keys_updated_at "
        "BEFORE UPDATE ON internal_keys "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_internal_keys_updated_at ON internal_keys")
    op.drop_index("idx_internal_keys_active", table_name="internal_keys")
    op.drop_table("internal_keys")
