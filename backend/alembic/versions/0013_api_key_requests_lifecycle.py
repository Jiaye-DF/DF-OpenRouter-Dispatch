"""v1.9.1:api_key_requests 生命週期欄位 — 規則路由 + AI 欄位驗證 + 自動開通。

擴充申請表為完整生命週期:新增取消/撤銷、AI 決策、開通結果與一次性憑證欄位。
既有 status='pending' 一律改為 'manual_pending'(待人工處理)。

Revision ID: 0013_api_key_requests_lifecycle
Revises: 0012_api_key_requests
Create Date: 2026-06-17
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision: str = "0013_api_key_requests_lifecycle"
down_revision: Union[str, Sequence[str], None] = "0012_api_key_requests"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "api_key_requests",
        sa.Column("cancel_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "api_key_requests",
        sa.Column("cancel_source", sa.String(length=8), nullable=True),
    )
    op.add_column(
        "api_key_requests",
        sa.Column("handled_by_user_uid", pg.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "api_key_requests",
        sa.Column("agent_decision", pg.JSONB(), nullable=True),
    )
    op.add_column(
        "api_key_requests",
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.add_column(
        "api_key_requests",
        sa.Column("created_project_uid", pg.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "api_key_requests",
        sa.Column("created_user_uid", pg.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "api_key_requests",
        sa.Column("created_sdk_key_uid", pg.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "api_key_requests",
        sa.Column("matched_department_uid", pg.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "api_key_requests",
        sa.Column("provisioned_secrets", pg.JSONB(), nullable=True),
    )
    op.add_column(
        "api_key_requests",
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    # 既有 pending 一律改為 manual_pending(待人工處理)
    op.execute(
        "UPDATE api_key_requests SET status='manual_pending' WHERE status='pending'"
    )


def downgrade() -> None:
    # manual_pending 還原為 pending(其餘終態略過)
    op.execute(
        "UPDATE api_key_requests SET status='pending' WHERE status='manual_pending'"
    )
    op.drop_column("api_key_requests", "processed_at")
    op.drop_column("api_key_requests", "provisioned_secrets")
    op.drop_column("api_key_requests", "matched_department_uid")
    op.drop_column("api_key_requests", "created_sdk_key_uid")
    op.drop_column("api_key_requests", "created_user_uid")
    op.drop_column("api_key_requests", "created_project_uid")
    op.drop_column("api_key_requests", "error_message")
    op.drop_column("api_key_requests", "agent_decision")
    op.drop_column("api_key_requests", "handled_by_user_uid")
    op.drop_column("api_key_requests", "cancel_source")
    op.drop_column("api_key_requests", "cancel_reason")
