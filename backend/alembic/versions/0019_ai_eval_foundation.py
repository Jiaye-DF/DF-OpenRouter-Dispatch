"""v2.0.0:模型適配評審地基三張表(全 ai_ 前綴,本版只建表,無資料寫入)。

依 propose-v2.0.0 § 4 建立:
- ai_eval_judge_settings:判別模型設定(model_uid 軟引用 models;ai_judge_slot 1/2/3 唯一)。
- ai_model_evaluations:評審結果父表(usage_log_uid 軟引用 usage_logs,unique;僅判別階段欄位)。
- ai_model_eval_candidates:候選子表(ai_evaluation_uid 軟引用父表;model_uid 軟引用 models)。

外鍵採本專案既有「純 UUID 軟引用 + 索引」慣例(全 16 個既有 model / migration 皆無 DB 層
ForeignKey 約束),join 目標欄位(models.model_uid / usage_logs.usage_log_uid)皆為 unique,
另於各引用欄位建索引以利 join。三表皆掛 set_updated_at trigger 維護 updated_at。

子表 propose 僅列 created_at,但依 task-001 Acceptance 三表皆含 updated_at 必備欄位,
故 ai_model_eval_candidates 亦建 updated_at + trigger。

Revision ID: 0019_ai_eval_foundation
Revises: 0018_user_tokens
Create Date: 2026-06-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision: str = "0019_ai_eval_foundation"
down_revision: str | Sequence[str] | None = "0018_user_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _required_columns() -> list[sa.Column]:
    """專案必備欄位(is_active / is_deleted / created_at / updated_at)。"""
    return [
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
    ]


def upgrade() -> None:
    # ── 4.1 ai_eval_judge_settings ──────────────────────────────────────────
    op.create_table(
        "ai_eval_judge_settings",
        sa.Column("pid", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "ai_judge_setting_uid",
            pg.UUID(as_uuid=True),
            nullable=False,
            unique=True,
        ),
        sa.Column("model_uid", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("ai_judge_slot", sa.SmallInteger(), nullable=False, unique=True),
        *_required_columns(),
    )
    # 軟引用 models.model_uid:依 model 查設定
    op.create_index(
        "idx_ai_eval_judge_settings_model_uid",
        "ai_eval_judge_settings",
        ["model_uid"],
        postgresql_where=sa.text("is_deleted = FALSE"),
    )
    op.execute(
        "CREATE TRIGGER trg_ai_eval_judge_settings_updated_at "
        "BEFORE UPDATE ON ai_eval_judge_settings "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )

    # ── 4.2 ai_model_evaluations ────────────────────────────────────────────
    op.create_table(
        "ai_model_evaluations",
        sa.Column("pid", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "ai_evaluation_uid",
            pg.UUID(as_uuid=True),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "usage_log_uid", pg.UUID(as_uuid=True), nullable=False, unique=True
        ),
        sa.Column("department_uid", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("user_uid", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("ai_original_model", sa.String(length=128), nullable=False),
        sa.Column("ai_task_summary", sa.Text(), nullable=True),
        sa.Column("ai_task_intent", sa.String(length=64), nullable=True),
        sa.Column("ai_task_complexity", sa.String(length=16), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("ai_evaluated_at", sa.DateTime(timezone=True), nullable=True),
        *_required_columns(),
    )
    # 列表 / 過濾用
    op.create_index(
        "idx_ai_model_evaluations_status",
        "ai_model_evaluations",
        ["status"],
        postgresql_where=sa.text("is_deleted = FALSE"),
    )
    op.execute(
        "CREATE TRIGGER trg_ai_model_evaluations_updated_at "
        "BEFORE UPDATE ON ai_model_evaluations "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )

    # ── 4.3 ai_model_eval_candidates ────────────────────────────────────────
    op.create_table(
        "ai_model_eval_candidates",
        sa.Column("pid", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "ai_candidate_uid",
            pg.UUID(as_uuid=True),
            nullable=False,
            unique=True,
        ),
        sa.Column("ai_evaluation_uid", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("model_uid", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("ai_recommend_model", sa.String(length=128), nullable=True),
        sa.Column("ai_recommend_tier", sa.String(length=32), nullable=True),
        sa.Column("ai_recommend_reason", sa.Text(), nullable=True),
        sa.Column("ai_fit_score", sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column("ai_self_vote", sa.Boolean(), nullable=True),
        *_required_columns(),
    )
    # 軟引用父表:依 evaluation 取候選
    op.create_index(
        "idx_ai_model_eval_candidates_evaluation_uid",
        "ai_model_eval_candidates",
        ["ai_evaluation_uid"],
        postgresql_where=sa.text("is_deleted = FALSE"),
    )
    # 軟引用 models.model_uid
    op.create_index(
        "idx_ai_model_eval_candidates_model_uid",
        "ai_model_eval_candidates",
        ["model_uid"],
        postgresql_where=sa.text("is_deleted = FALSE"),
    )
    op.execute(
        "CREATE TRIGGER trg_ai_model_eval_candidates_updated_at "
        "BEFORE UPDATE ON ai_model_eval_candidates "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_ai_model_eval_candidates_updated_at "
        "ON ai_model_eval_candidates"
    )
    op.drop_index(
        "idx_ai_model_eval_candidates_model_uid",
        table_name="ai_model_eval_candidates",
    )
    op.drop_index(
        "idx_ai_model_eval_candidates_evaluation_uid",
        table_name="ai_model_eval_candidates",
    )
    op.drop_table("ai_model_eval_candidates")

    op.execute(
        "DROP TRIGGER IF EXISTS trg_ai_model_evaluations_updated_at "
        "ON ai_model_evaluations"
    )
    op.drop_index(
        "idx_ai_model_evaluations_status", table_name="ai_model_evaluations"
    )
    op.drop_table("ai_model_evaluations")

    op.execute(
        "DROP TRIGGER IF EXISTS trg_ai_eval_judge_settings_updated_at "
        "ON ai_eval_judge_settings"
    )
    op.drop_index(
        "idx_ai_eval_judge_settings_model_uid",
        table_name="ai_eval_judge_settings",
    )
    op.drop_table("ai_eval_judge_settings")
