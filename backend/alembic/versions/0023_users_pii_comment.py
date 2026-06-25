"""v2.0:users 三個 PII 欄位 COMMENT 補 (PII) 標註(雙軌與 model comment= 一致)。

scan-project R-PII-002:users.username / employee_id / email 屬 PII,但 0022
回填的 COMMENT 未加 (PII) 尾標(對照 api_key_requests.owner_email 已標)。本檔
把這三欄的 DB COMMENT 更新為帶 (PII) 版本,與 model `comment=` 逐字一致,
避免雙軌漂移(對齊 04-databases/00-overview.md § 自我說明)。

純 COMMENT 異動,不動欄位結構。downgrade 還原為不帶 (PII) 的原文。

Revision ID: 0023_users_pii_comment
Revises: 0022_backfill_comments
Create Date: 2026-06-25
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0023_users_pii_comment"
down_revision: str | Sequence[str] | None = "0022_backfill_comments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "COMMENT ON COLUMN users.username IS "
        "'使用者顯示名稱(PII) | display name (PII)'"
    )
    op.execute(
        "COMMENT ON COLUMN users.employee_id IS "
        "'員工編號(PII) | employee ID (PII)'"
    )
    op.execute(
        "COMMENT ON COLUMN users.email IS '電子郵件(PII) | email (PII)'"
    )


def downgrade() -> None:
    op.execute("COMMENT ON COLUMN users.username IS '使用者顯示名稱 | display name'")
    op.execute("COMMENT ON COLUMN users.employee_id IS '員工編號 | employee ID'")
    op.execute("COMMENT ON COLUMN users.email IS '電子郵件 | email'")
