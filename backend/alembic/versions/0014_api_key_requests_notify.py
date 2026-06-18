"""v1.9.2:api_key_requests 開通完成 Email 通知留痕。

新增 notified_at(寄送成功時間)/ notify_error(失敗原因,不含憑證)兩欄。

Revision ID: 0014_api_key_requests_notify
Revises: 0013_api_key_requests_lifecycle
Create Date: 2026-06-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014_api_key_requests_notify"
down_revision: str | Sequence[str] | None = "0013_api_key_requests_lifecycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "api_key_requests",
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "api_key_requests",
        sa.Column("notify_error", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("api_key_requests", "notify_error")
    op.drop_column("api_key_requests", "notified_at")
