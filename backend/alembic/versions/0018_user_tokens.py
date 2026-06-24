"""v1.10:user_tokens 表 — User Token 一人一把、落地儲存。

同一使用者跨多專案/重複申請沿用同一把 token(get_or_create),不再撤舊重發。
撤銷時與既有 user_tokens_revocations(浮水印)兩張表並用:
驗證鏈先掃本表比對 token,找不到才回退浮水印,確保已發出、未落地的舊 token 不被誤殺。

Revision ID: 0018_user_tokens
Revises: 0017_orkey_disabled_until
Create Date: 2026-06-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision: str = "0018_user_tokens"
down_revision: str | Sequence[str] | None = "0017_orkey_disabled_until"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_tokens",
        sa.Column("pid", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_tokens_uid", pg.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("user_uid", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(length=255), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    # 依使用者查詢(get_active_by_user / get_by_user_and_token)
    op.create_index(
        "idx_user_tokens_user_uid",
        "user_tokens",
        ["user_uid"],
        postgresql_where=sa.text("is_deleted = FALSE"),
    )
    # 一人最多一把有效 token(DB 層保證沿用語意,避免並發各自新建)
    op.create_index(
        "uq_user_tokens_active_user",
        "user_tokens",
        ["user_uid"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL AND is_deleted = FALSE"),
    )
    op.execute(
        "CREATE TRIGGER trg_user_tokens_updated_at "
        "BEFORE UPDATE ON user_tokens "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_user_tokens_updated_at ON user_tokens")
    op.drop_index("uq_user_tokens_active_user", table_name="user_tokens")
    op.drop_index("idx_user_tokens_user_uid", table_name="user_tokens")
    op.drop_table("user_tokens")
