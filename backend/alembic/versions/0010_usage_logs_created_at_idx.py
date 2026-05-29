"""v1.6:usage_logs 加 created_at 部分索引,支撐儀表板時間範圍彙總。

儀表板各維度彙總(overview / by-model / by-user / timeseries)在 admin
未選任何部門 / 專案 / 使用者、僅帶時間範圍時,原本無索引可用 → 全表 Seq Scan。
現儀表板預設並強制帶時間範圍(當月),故補一支 created_at 部分索引
(WHERE is_deleted = FALSE)支撐 range scan;隨 usage_logs 成長亦不致退化。

既有複合索引 (department_uid/user_uid/model/project_uid, created_at) 仍負責
「有指定該維度 + 時間範圍」的查詢,兩者互補。

Revision ID: 0010_usage_logs_created_at_idx
Revises: 0009_sdk_key_values_plaintext
Create Date: 2026-05-29
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0010_usage_logs_created_at_idx"
down_revision: Union[str, Sequence[str], None] = "0009_sdk_key_values_plaintext"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "idx_usage_logs_created_at",
        "usage_logs",
        [sa.text("created_at DESC")],
        postgresql_where=sa.text("is_deleted = FALSE"),
    )


def downgrade() -> None:
    op.drop_index("idx_usage_logs_created_at", table_name="usage_logs")
