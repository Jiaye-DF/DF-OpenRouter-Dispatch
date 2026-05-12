"""v1.2: models.provider + rename model_key;openrouter_keys 加 RPM/interval。

Revision ID: 0002_provider_rate_limit
Revises: 0001_baseline
Create Date: 2026-05-12
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0002_provider_rate_limit"
down_revision: Union[str, Sequence[str], None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. models 加 provider 欄位(既有資料以 DEFAULT 補)
    op.add_column(
        "models",
        sa.Column(
            "provider",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'openrouter'"),
        ),
    )

    # 2. models rename openrouter_model_id → model_key(同步 rename UNIQUE 索引)
    op.alter_column(
        "models",
        "openrouter_model_id",
        new_column_name="model_key",
    )
    op.execute(
        "ALTER INDEX models_openrouter_model_id_key RENAME TO models_model_key_key"
    )

    # 3. models 加 provider 索引
    op.create_index(
        "idx_models_provider",
        "models",
        ["provider"],
        postgresql_where=sa.text("is_deleted = FALSE"),
    )

    # 4. openrouter_keys 加 rpm_limit / min_request_interval_ms(0 = 不限)
    op.add_column(
        "openrouter_keys",
        sa.Column(
            "rpm_limit",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "openrouter_keys",
        sa.Column(
            "min_request_interval_ms",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_check_constraint(
        "chk_openrouter_keys_rpm",
        "openrouter_keys",
        "rpm_limit >= 0",
    )
    op.create_check_constraint(
        "chk_openrouter_keys_min_interval",
        "openrouter_keys",
        "min_request_interval_ms >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "chk_openrouter_keys_min_interval", "openrouter_keys", type_="check"
    )
    op.drop_constraint("chk_openrouter_keys_rpm", "openrouter_keys", type_="check")
    op.drop_column("openrouter_keys", "min_request_interval_ms")
    op.drop_column("openrouter_keys", "rpm_limit")

    op.drop_index("idx_models_provider", table_name="models")
    op.execute(
        "ALTER INDEX models_model_key_key RENAME TO models_openrouter_model_id_key"
    )
    op.alter_column("models", "model_key", new_column_name="openrouter_model_id")
    op.drop_column("models", "provider")
