"""v1.3 增量：users.sso_user_id(DF-SSO azure oid,供 back-channel logout 反查)。

Revision ID: 0004_users_sso_user_id
Revises: 0003_internal_keys
Create Date: 2026-05-22
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0004_users_sso_user_id"
down_revision: Union[str, Sequence[str], None] = "0003_internal_keys"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("sso_user_id", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "idx_users_sso_user_id",
        "users",
        ["sso_user_id"],
        postgresql_where=sa.text("is_deleted = FALSE"),
    )


def downgrade() -> None:
    op.drop_index("idx_users_sso_user_id", table_name="users")
    op.drop_column("users", "sso_user_id")
