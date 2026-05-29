"""v1.5 增量:sdk_api_keys 加 key_encrypted BYTEA。

業務需求:admin 後台需可隨時檢視 SDK Key 完整明文(對齊 OpenRouter Key 的可逆加密策略)。
保留原有 argon2 key_hash 不動 — auth path 不受影響;新建立的 key 會同時寫 key_encrypted,
舊資料因無原始明文無法回填,UI 端顯示「不可顯示」。

Revision ID: 0008_sdk_key_encrypted
Revises: 0007_model_modality_tags
Create Date: 2026-05-29
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0008_sdk_key_encrypted"
down_revision: Union[str, Sequence[str], None] = "0007_model_modality_tags"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sdk_api_keys",
        sa.Column("key_encrypted", sa.LargeBinary(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sdk_api_keys", "key_encrypted")
