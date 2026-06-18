"""v1.10:departments 新增 org_code(組織代碼)。

原 code 欄位語意調整為「成本中心代碼」(僅顯示文字變更,欄位名不動);
新增 org_code(組織代碼)欄位;一個組織代碼可對應多個成本中心代碼,
故 org_code 不設唯一限制(僅 code 維持部分唯一索引)。
為相容既有資料,org_code 設為可空,既有部門可由 admin 後續補填。

Revision ID: 0015_departments_org_code
Revises: 0014_api_key_requests_notify
Create Date: 2026-06-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0015_departments_org_code"
down_revision: str | Sequence[str] | None = "0014_api_key_requests_notify"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "departments",
        sa.Column("org_code", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("departments", "org_code")
