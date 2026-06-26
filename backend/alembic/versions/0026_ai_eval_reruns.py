"""v2.1.0:challenger 真實重跑 + 對比裁決新表 + 父表重跑游標兩欄。

依 propose-v2.1.0 § 4 落地:
- 新表 ai_model_eval_reruns(一筆 = 一個 challenger 的真實重跑 + 對比裁決;與
  usage_logs 結構相似但獨立,不混入正常用量/計費統計)。
  - 必備欄位 pid / ai_eval_rerun_uid / is_active / is_deleted / created_at / updated_at;
    set_updated_at trigger 維護 updated_at。
  - 軟引用(純 UUID + 索引,無 DB 層 FK,對齊既有慣例):
    ai_evaluation_uid / usage_log_uid / ai_candidate_uid / model_uid。
  - 冪等:UNIQUE(ai_evaluation_uid, rerun_model) 不分軟刪,避免同 challenger 重複重跑。
  - 索引:idx_..._usage_log_uid(全表)、idx_..._evaluation_uid partial(is_deleted=false)。
  - 金額精度 Numeric(12,6)(cost 系列)/ Numeric(4,3)(compare_score 信心分數),依
    05-precision.md 語意調整(OpenRouter 微量計費),理由見 model docstring。
- 父表 ai_model_evaluations 增重跑游標兩欄(§4.2):
  - ai_reran_at TIMESTAMPTZ NULL:最新一次重跑執行時間;NULL=待重跑(派發掃描鍵)。
  - ai_rerun_status SMALLINT NULL:NULL=未重跑 / 0=失敗 / 1=成功(終局不重派)。

建表即帶表級 + 每欄 COMMENT(中英雙語,與 model comment= 同源同文案,避免 alembic
autogenerate 誤判);新增欄位同步 COMMENT ON COLUMN(對齊 90-project-database.md § 3.5)。
新表登錄 table_catalog 一筆(ON CONFLICT DO NOTHING 保冪等)。

downgrade 對稱還原:drop 父表兩欄 + trigger + 兩索引 + 表(table_catalog 種子隨表移除)。

Revision ID: 0026_ai_eval_reruns
Revises: 0025_backfill_self_vote
Create Date: 2026-06-26
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
from uuid_utils import uuid7

from alembic import op

revision: str = "0026_ai_eval_reruns"
down_revision: str | Sequence[str] | None = "0025_backfill_self_vote"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "ai_model_eval_reruns"


def _required_columns() -> list[sa.Column]:
    """專案必備欄位(is_active / is_deleted / created_at / updated_at)。"""
    return [
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="是否啟用,停用後保留資料但不可使用 | active flag",
        ),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="軟刪除標記,查詢預設過濾 is_deleted=FALSE | soft-delete flag",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="建立時間(UTC+8) | created at",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="更新時間(UTC+8,由 trigger 維護) | updated at",
        ),
    ]


def upgrade() -> None:
    # ── 4.1 新表 ai_model_eval_reruns ───────────────────────────────────────
    op.create_table(
        _TABLE,
        sa.Column(
            "pid",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
            comment="內部自增主鍵,禁對外暴露 | internal auto-increment PK",
        ),
        sa.Column(
            "ai_eval_rerun_uid",
            pg.UUID(as_uuid=True),
            nullable=False,
            unique=True,
            comment="對外 UUID 識別(UUIDv7) | external UID",
        ),
        sa.Column(
            "ai_evaluation_uid",
            pg.UUID(as_uuid=True),
            nullable=False,
            comment="軟引用父評審(來自哪次評審的推薦) | parent evaluation",
        ),
        sa.Column(
            "usage_log_uid",
            pg.UUID(as_uuid=True),
            nullable=False,
            comment="軟引用原始 log(同輸入來源) | source usage log",
        ),
        sa.Column(
            "ai_candidate_uid",
            pg.UUID(as_uuid=True),
            nullable=True,
            comment="軟引用是哪個裁判候選推薦的(去重取代表者) | source candidate",
        ),
        sa.Column(
            "original_model",
            sa.String(length=128),
            nullable=False,
            comment="原模型 key(denormalize,對比顯示) | original model key",
        ),
        sa.Column(
            "rerun_model",
            sa.String(length=128),
            nullable=False,
            comment="challenger 模型 key(實際重跑) | challenger model key",
        ),
        sa.Column(
            "model_uid",
            pg.UUID(as_uuid=True),
            nullable=True,
            comment="challenger model_uid(軟引用 models.model_uid) | challenger model",
        ),
        sa.Column(
            "request_content",
            pg.JSONB(),
            nullable=True,
            comment="重跑輸入快照(可重現;沿用原 log 輸入) | request snapshot",
        ),
        sa.Column(
            "response_summary",
            pg.JSONB(),
            nullable=True,
            comment="challenger 真實輸出({output_text, usage?}) | challenger response",
        ),
        sa.Column(
            "prompt_tokens",
            sa.Integer(),
            nullable=True,
            comment="challenger 真實 prompt token | prompt tokens",
        ),
        sa.Column(
            "completion_tokens",
            sa.Integer(),
            nullable=True,
            comment="challenger 真實 completion token | completion tokens",
        ),
        sa.Column(
            "total_tokens",
            sa.Integer(),
            nullable=True,
            comment="challenger 真實 total token | total tokens",
        ),
        sa.Column(
            "cost_usd",
            sa.Numeric(precision=12, scale=6),
            nullable=True,
            comment="challenger 真實成本(USD,6 位精度) | challenger cost (USD)",
        ),
        sa.Column(
            "original_cost_usd",
            sa.Numeric(precision=12, scale=6),
            nullable=True,
            comment="原呼叫成本(denormalize,對比;USD) | original cost (USD)",
        ),
        sa.Column(
            "cost_delta_usd",
            sa.Numeric(precision=12, scale=6),
            nullable=True,
            comment="成本差 challenger − original(客觀指標;USD) | cost delta (USD)",
        ),
        sa.Column(
            "latency_ms",
            sa.Integer(),
            nullable=True,
            comment="challenger 延遲(毫秒) | latency (ms)",
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'success'"),
            comment="重跑狀態:success/error | rerun status",
        ),
        sa.Column(
            "error_code",
            sa.String(length=64),
            nullable=True,
            comment="錯誤碼(NULL=無錯誤) | error code",
        ),
        sa.Column(
            "openrouter_generation_id",
            sa.String(length=64),
            nullable=True,
            comment="OpenRouter 生成 ID | OpenRouter generation id",
        ),
        sa.Column(
            "compare_winner",
            sa.String(length=16),
            nullable=True,
            comment="裁決:original/challenger/tie | discriminator winner",
        ),
        sa.Column(
            "compare_score",
            sa.Numeric(precision=4, scale=3),
            nullable=True,
            comment="信心分數 0–1(對原推薦合理度的信心) | confidence score 0–1",
        ),
        sa.Column(
            "compare_reason",
            sa.Text(),
            nullable=True,
            comment="裁決理由 | discriminator reason",
        ),
        sa.Column(
            "compare_judge_model",
            sa.String(length=128),
            nullable=True,
            comment="擔任裁決的模型 key(推薦該 challenger 的評審本人) | judge model key",
        ),
        sa.Column(
            "triggered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="重跑執行時間(UTC+8) | triggered at",
        ),
        *_required_columns(),
        sa.UniqueConstraint(
            "ai_evaluation_uid",
            "rerun_model",
            name="uq_ai_model_eval_reruns_evaluation_uid_rerun_model",
        ),
        comment="模型評審 challenger 真實重跑與對比裁決",
    )
    # 前端/查詢:依 usage_log 取該筆所有 challenger(全表索引)
    op.create_index(
        "idx_ai_model_eval_reruns_usage_log_uid",
        _TABLE,
        ["usage_log_uid"],
    )
    # 軟引用父表:依 evaluation 取重跑(partial,排軟刪)
    op.create_index(
        "idx_ai_model_eval_reruns_evaluation_uid",
        _TABLE,
        ["ai_evaluation_uid"],
        postgresql_where=sa.text("is_deleted = FALSE"),
    )
    op.execute(
        "CREATE TRIGGER trg_ai_model_eval_reruns_updated_at "
        f"BEFORE UPDATE ON {_TABLE} "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )

    # 新表登錄字典(§3.5;ON CONFLICT DO NOTHING 保冪等)
    op.get_bind().execute(
        sa.text(
            "INSERT INTO table_catalog "
            "(table_catalog_uid, table_name, display_name_zh, category, "
            "description, sort_order) "
            "VALUES (:uid, :table_name, :display_name_zh, :category, "
            ":description, :sort_order) "
            "ON CONFLICT (table_name) DO NOTHING"
        ),
        {
            "uid": UUID(str(uuid7())),
            "table_name": _TABLE,
            "display_name_zh": "模型評審重跑",
            "category": "AI 分析",
            "description": "模型評審 challenger 真實重跑與對比裁決",
            "sort_order": 20,
        },
    )

    # ── 4.2 父表 ai_model_evaluations 增重跑游標兩欄 ─────────────────────────
    op.add_column(
        "ai_model_evaluations",
        sa.Column(
            "ai_reran_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment=(
                "最新一次重跑執行時間(UTC+8;NULL=待重跑,派發掃描鍵) | reran at"
            ),
        ),
    )
    op.add_column(
        "ai_model_evaluations",
        sa.Column(
            "ai_rerun_status",
            sa.SmallInteger(),
            nullable=True,
            comment=(
                "重跑狀態:NULL=未重跑/0=失敗/1=成功(終局不重派) | rerun status"
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("ai_model_evaluations", "ai_rerun_status")
    op.drop_column("ai_model_evaluations", "ai_reran_at")

    op.execute(
        f"DELETE FROM table_catalog WHERE table_name = '{_TABLE}'"
    )
    op.execute(
        f"DROP TRIGGER IF EXISTS trg_ai_model_eval_reruns_updated_at ON {_TABLE}"
    )
    op.drop_index(
        "idx_ai_model_eval_reruns_evaluation_uid",
        table_name=_TABLE,
    )
    op.drop_index(
        "idx_ai_model_eval_reruns_usage_log_uid",
        table_name=_TABLE,
    )
    op.drop_table(_TABLE)
