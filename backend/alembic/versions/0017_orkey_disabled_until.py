"""v1.10:openrouter_keys 新增 disabled_until(壞 key 短期停用 cooldown)。

dispatch 撞 401(失效)/ 402(餘額不足)時,把該 key disabled_until 設為 now()+cooldown,
派工查詢跳過未到期者,到期自動恢復。可空(預設不停用);既有資料不受影響。

Revision ID: 0017_orkey_disabled_until
Revises: 0016_apireq_status_default
Create Date: 2026-06-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0017_orkey_disabled_until"
down_revision: str | Sequence[str] | None = "0016_apireq_status_default"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "openrouter_keys",
        sa.Column("disabled_until", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("openrouter_keys", "disabled_until")
