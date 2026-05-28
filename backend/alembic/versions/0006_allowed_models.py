"""v1.5 增量:allowed_models 表 — sync 模型白名單的 DB-driven 來源。

把原本寫死在 sync.py 的 DEFAULT_MODEL_WHITELIST 抽出來,改由本表管理;
未來新增 / 移除允許模型,只動本表,不必改 code + 重啟。

Revision ID: 0006_allowed_models
Revises: 0005_usage_logs_project_uid
Create Date: 2026-05-28
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision: str = "0006_allowed_models"
down_revision: Union[str, Sequence[str], None] = "0005_usage_logs_project_uid"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "allowed_models",
        sa.Column("pid", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "allowed_model_uid",
            pg.UUID(as_uuid=True),
            nullable=False,
            unique=True,
        ),
        # OpenRouter model_key,例 "google/gemini-2.5-flash"
        sa.Column("model_key", sa.String(length=256), nullable=False, unique=True),
        # 備註(可選):為何允許此模型 / 適用情境
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
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
    op.create_index(
        "idx_allowed_models_active",
        "allowed_models",
        ["model_key"],
        postgresql_where=sa.text("is_active = TRUE AND is_deleted = FALSE"),
    )
    op.execute(
        "CREATE TRIGGER trg_allowed_models_updated_at "
        "BEFORE UPDATE ON allowed_models "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )

    # Seed 初始白名單(同步前已寫死於 code 的 3 個);沿用 uuid_generate_v4 (Postgres 內建)。
    op.execute(
        """
        INSERT INTO allowed_models (allowed_model_uid, model_key, note)
        VALUES
            (gen_random_uuid(), 'google/gemini-2.5-flash', '預設白名單'),
            (gen_random_uuid(), 'openai/gpt-4o', '預設白名單'),
            (gen_random_uuid(), 'anthropic/claude-sonnet-4.5', '預設白名單')
        ON CONFLICT (model_key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_allowed_models_updated_at ON allowed_models")
    op.drop_index("idx_allowed_models_active", table_name="allowed_models")
    op.drop_table("allowed_models")
