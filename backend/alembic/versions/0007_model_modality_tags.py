"""v1.5 增量:models 加 input_modalities / output_modalities 陣列欄。

OpenRouter `/models` 已提供 architecture.input_modalities / output_modalities
兩個 list,可用來呈現「可輸入 / 可輸出」tag(text / image / file / audio ...);
原 modality 字串欄保留(歷史相容),前端顯示改以這兩個陣列為主。

Revision ID: 0007_model_modality_tags
Revises: 0006_allowed_models
Create Date: 2026-05-29
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision: str = "0007_model_modality_tags"
down_revision: Union[str, Sequence[str], None] = "0006_allowed_models"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # text[] 陣列;預設空陣列方便 Python 端統一以 list 處理(避免 None / 空 兩種分支)。
    op.add_column(
        "models",
        sa.Column(
            "input_modalities",
            pg.ARRAY(sa.String(length=32)),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
    )
    op.add_column(
        "models",
        sa.Column(
            "output_modalities",
            pg.ARRAY(sa.String(length=32)),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
    )


def downgrade() -> None:
    op.drop_column("models", "output_modalities")
    op.drop_column("models", "input_modalities")
