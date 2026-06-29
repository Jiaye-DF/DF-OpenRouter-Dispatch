"""v2.0:ai_self_vote 語意更正 — 改為「裁判 vs 推薦」自我偏好偏差。

ai_model_eval_candidates.ai_self_vote 原定義/實作為「推薦是否與**原模型**同廠商」,
但欄名(self-vote)與設計目的(降自我偏好偏差 + 盲化)實指「該判別模型是否推薦
**自己家**的模型」。本檔將比對對象更正為「判別模型 vs 推薦」,並同步更新 DB COMMENT
與 model `comment=` 逐字一致(對齊 04-databases/00-overview.md § 自我說明)。

純 COMMENT 異動,不動欄位結構;邏輯更正在 services/ai_model_eval.py。
downgrade 還原為原「與原模型同廠商」版本文案。

Revision ID: 0024_self_vote_comment
Revises: 0023_users_pii_comment
Create Date: 2026-06-26
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0024_self_vote_comment"
down_revision: str | Sequence[str] | None = "0023_users_pii_comment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "COMMENT ON COLUMN ai_model_eval_candidates.ai_self_vote IS "
        "'推薦是否與判別模型同廠商(自我偏好偏差監控) | self-vote flag (judge self-preference bias)'"
    )


def downgrade() -> None:
    op.execute(
        "COMMENT ON COLUMN ai_model_eval_candidates.ai_self_vote IS "
        "'推薦是否與原模型同廠商(偏差監控) | self-vote flag (bias monitoring)'"
    )
