"""v2.0:usage_logs 加模型適配評審旗標欄(ai_evaluated_at + ai_evaluated_status)。

模型適配評審(task-106 dispatcher)需掃描尚未評審的用量紀錄,並由寫入端
(task-104/105)回填評審執行結果。於 usage_logs 加兩欄(全棧 UTC+8,對齊
04-databases/06-timezone.md):

- ai_evaluated_at TIMESTAMP(timezone=True) NULL:最新一次評審「執行時間」。
  NULL=尚未評審;不論評審成功或失敗,寫入端皆會更新此欄。
- ai_evaluated_status SMALLINT NULL:最新一次評審結果。NULL=尚未評審、
  0=評審失敗、1=評審成功。本版不為此欄建 index(失敗重查機制留後續版本)。

Partial index 只索引待評審(ai_evaluated_at IS NULL)且未軟刪的列,支撐
dispatcher「撈待評審筆」走 index scan;已跑過的列(無論成敗)不入索引,
隨評審推進索引自然收斂、儲存成本極低(對齊 04-databases/09-indexes-and-perf.md)。
既有歷史紀錄兩欄皆為 NULL,不影響舊資料。

Revision ID: 0020_usage_logs_ai_eval_flags
Revises: 0019_ai_eval_foundation
Create Date: 2026-06-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0020_usage_logs_ai_eval_flags"
down_revision: str | Sequence[str] | None = "0019_ai_eval_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "usage_logs",
        sa.Column("ai_evaluated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "usage_logs",
        sa.Column("ai_evaluated_status", sa.SmallInteger(), nullable=True),
    )
    # dispatcher 撈待評審筆:只索引未評審(ai_evaluated_at IS NULL)且未軟刪的稀少子集
    op.create_index(
        "idx_usage_logs_ai_unevaluated",
        "usage_logs",
        [sa.text("created_at DESC")],
        postgresql_where=sa.text("ai_evaluated_at IS NULL AND is_deleted = FALSE"),
    )


def downgrade() -> None:
    op.drop_index("idx_usage_logs_ai_unevaluated", table_name="usage_logs")
    op.drop_column("usage_logs", "ai_evaluated_status")
    op.drop_column("usage_logs", "ai_evaluated_at")
