"""v2.1:api_key_requests 撤銷理由 — revoke_reason / revoke_source。

撤銷(本人 / admin)須填理由並記錄來源,與取消(cancel_reason / cancel_source)平行。

Revision ID: 0028_apireq_revoke_reason
Revises: 0027_judge_slot_partial_unique
Create Date: 2026-07-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0028_apireq_revoke_reason"
down_revision: str | Sequence[str] | None = "0027_judge_slot_partial_unique"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "api_key_requests",
        sa.Column(
            "revoke_reason",
            sa.Text(),
            nullable=True,
            comment="撤銷原因 | revoke reason",
        ),
    )
    op.add_column(
        "api_key_requests",
        sa.Column(
            "revoke_source",
            sa.String(length=8),
            nullable=True,
            comment="撤銷來源(user / admin) | revoke source",
        ),
    )


def downgrade() -> None:
    op.drop_column("api_key_requests", "revoke_source")
    op.drop_column("api_key_requests", "revoke_reason")
