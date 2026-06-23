"""v1.10:api_key_requests.status 欄位 DEFAULT 對齊狀態機初始態。

原 DB DEFAULT 為 'pending',但 v1.9.1 狀態機(manual_pending / agent_done /
done / revoked / cancelled)已無 'pending';service 層 INSERT 皆明確賦值,
此 DEFAULT 幾乎不會命中,但若有路徑漏設會落入無對應的孤兒狀態。
改為 'manual_pending' 對齊初始態。僅變更欄位 DEFAULT,不動既有資料。

Revision ID: 0016_apireq_status_default
Revises: 0015_departments_org_code
Create Date: 2026-06-22
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0016_apireq_status_default"
down_revision: str | Sequence[str] | None = "0015_departments_org_code"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("api_key_requests", "status", server_default="manual_pending")


def downgrade() -> None:
    op.alter_column("api_key_requests", "status", server_default="pending")
