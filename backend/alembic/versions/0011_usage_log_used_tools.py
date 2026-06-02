"""v1.6.2 增量:usage_logs 加 used_tools 布林欄 + 稀少子集 partial index。

tools 參數(如 OpenRouter web search)可能觸發額外計費,故在用量紀錄標記
「本次呼叫是否帶工具」,供後台篩選與計費分析。

- used_tools BOOLEAN NOT NULL DEFAULT FALSE:server_default false 讓既有歷史
  自動回填為 false(tools 在本版本前不存在)。
- Partial index 只索引稀少的 used_tools=TRUE 列,支撐「只看用工具的呼叫 +
  時間範圍」查詢走 range scan;FALSE 列不入索引,儲存成本極低。

Revision ID: 0011_usage_log_used_tools
Revises: 0010_usage_logs_created_at_idx
Create Date: 2026-06-02
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0011_usage_log_used_tools"
down_revision: Union[str, Sequence[str], None] = "0010_usage_logs_created_at_idx"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "usage_logs",
        sa.Column(
            "used_tools",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
    )
    op.create_index(
        "idx_usage_logs_used_tools_time",
        "usage_logs",
        [sa.text("created_at DESC")],
        postgresql_where=sa.text("used_tools = TRUE AND is_deleted = FALSE"),
    )


def downgrade() -> None:
    op.drop_index("idx_usage_logs_used_tools_time", table_name="usage_logs")
    op.drop_column("usage_logs", "used_tools")
