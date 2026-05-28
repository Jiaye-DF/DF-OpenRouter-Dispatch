"""v1.5 增量：usage_logs 加 project_uid FK(對齊 docs/Tasks/v1.5/propose-v1.5.0.md)。

寫入時(代理呼叫)必帶 X-Project-Id;既有歷史不回填,允許 NULL。
ON DELETE SET NULL:刪 project 不影響既有 usage 紀錄(改顯示為「未分類」)。

Revision ID: 0005_usage_logs_project_uid
Revises: 0004_users_sso_user_id
Create Date: 2026-05-28
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision: str = "0005_usage_logs_project_uid"
down_revision: Union[str, Sequence[str], None] = "0004_users_sso_user_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "usage_logs",
        sa.Column("project_uid", pg.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_usage_logs_project_uid",
        "usage_logs",
        "projects",
        ["project_uid"],
        ["project_uid"],
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_usage_logs_project_uid_time",
        "usage_logs",
        ["project_uid", "created_at"],
        postgresql_where=sa.text("is_deleted = FALSE"),
    )


def downgrade() -> None:
    op.drop_index("idx_usage_logs_project_uid_time", table_name="usage_logs")
    op.drop_constraint("fk_usage_logs_project_uid", "usage_logs", type_="foreignkey")
    op.drop_column("usage_logs", "project_uid")
