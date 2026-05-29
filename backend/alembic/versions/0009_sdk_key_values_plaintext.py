"""v1.5 修訂:sdk_api_keys 移除加密欄,改為 key_values TEXT 純明文。

業務決議:admin 後台要能直接在 DB 編輯 SDK Key 明文(以便補 v1.5 之前
建立的舊資料),因此放棄 AES-GCM 可逆加密的中間層,改用純 TEXT 欄。

對先前已套用 0008(BYTEA key_encrypted)的環境:
- upgrade 會 DROP 舊欄並 ADD 新欄(IF EXISTS 防呆)
- 既有 v1.5 期間建立的 key_encrypted 資料無法保留,需要的話請 admin 在
  新欄填入明文,或在後台重新建立 key

Revision ID: 0009_sdk_key_values_plaintext
Revises: 0008_sdk_key_encrypted
Create Date: 2026-05-29
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0009_sdk_key_values_plaintext"
down_revision: Union[str, Sequence[str], None] = "0008_sdk_key_encrypted"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE sdk_api_keys DROP COLUMN IF EXISTS key_encrypted")
    op.add_column(
        "sdk_api_keys",
        sa.Column("key_values", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sdk_api_keys", "key_values")
    op.add_column(
        "sdk_api_keys",
        sa.Column("key_encrypted", sa.LargeBinary(), nullable=True),
    )
