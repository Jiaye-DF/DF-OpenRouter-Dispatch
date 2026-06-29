"""v2.0.2:資料表名稱對照字典 table_catalog(建表 + trigger + 19 筆種子)。

依 propose-v2.0.2 § 5 建立資料字典表(實體表名 → 中文顯示名 + 分組 + 說明):
- 沿用專案慣例:pid BIGSERIAL PK + table_catalog_uid UUID unique + 必備四欄
  + set_updated_at trigger;軟引用、無 DB 層 FK。
- 建表即帶表級 + 每欄 COMMENT(必備欄位用 tasks-v2.0.2 § 罐頭文案逐字,
  與 model `comment=` 同源同文案,避免 alembic autogenerate 誤判)。
- 種子 19 筆(propose § 3 全列:18 既有 + table_catalog 自身 category='系統'),
  table_name UNIQUE,ON CONFLICT (table_name) DO NOTHING 保冪等。
- 本表自我登錄一筆(吃自己的狗糧,符合 Design-Base § 3.5 新規則)。
- UUID 採 UUIDv7(uuid_utils.uuid7,對齊 01-identifiers.md)。

Revision ID: 0021_table_catalog
Revises: 0020_usage_logs_ai_eval_flags
Create Date: 2026-06-25
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
from uuid_utils import uuid7

from alembic import op

revision: str = "0021_table_catalog"
down_revision: str | Sequence[str] | None = "0020_usage_logs_ai_eval_flags"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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


# 種子:propose-v2.0.2 § 3 全 19 列(18 既有 + table_catalog 自身)。
# (table_name, display_name_zh, category, sort_order)
_SEED_ROWS: list[tuple[str, str, str, int]] = [
    ("users", "使用者", "帳號", 1),
    ("departments", "部門", "帳號", 2),
    ("projects", "專案", "帳號", 3),
    ("refresh_tokens", "更新權杖", "帳號", 4),
    ("user_tokens", "使用者權杖", "帳號", 5),
    ("user_tokens_revocations", "使用者權杖撤銷", "帳號", 6),
    ("audit_logs", "稽核紀錄", "稽核", 7),
    ("models", "模型", "模型管理", 8),
    ("model_tiers", "模型分級", "模型管理", 9),
    ("allowed_models", "模型白名單", "模型管理", 10),
    ("openrouter_keys", "OpenRouter 金鑰", "金鑰", 11),
    ("internal_keys", "內部金鑰", "金鑰", 12),
    ("sdk_api_keys", "SDK API 金鑰", "金鑰", 13),
    ("api_key_requests", "金鑰申請單", "金鑰", 14),
    ("usage_logs", "用量紀錄", "計量", 15),
    ("ai_eval_judge_settings", "判別模型設定", "AI 分析", 16),
    ("ai_model_evaluations", "模型評審結果", "AI 分析", 17),
    ("ai_model_eval_candidates", "模型評審候選", "AI 分析", 18),
    ("table_catalog", "資料表名稱對照", "系統", 19),
]


def upgrade() -> None:
    op.create_table(
        "table_catalog",
        sa.Column(
            "pid",
            sa.BigInteger(),
            primary_key=True,
            autoincrement=True,
            comment="內部自增主鍵,禁對外暴露 | internal auto-increment PK",
        ),
        sa.Column(
            "table_catalog_uid",
            pg.UUID(as_uuid=True),
            nullable=False,
            unique=True,
            comment="對外 UUID 識別(UUIDv7) | external UID",
        ),
        sa.Column(
            "table_name",
            sa.String(length=64),
            nullable=False,
            unique=True,
            comment="實體表名(如 users) | physical table name",
        ),
        sa.Column(
            "display_name_zh",
            sa.String(length=128),
            nullable=False,
            comment="中文顯示名(如 使用者) | display name (zh)",
        ),
        sa.Column(
            "category",
            sa.String(length=32),
            nullable=True,
            comment="分組(帳號/金鑰/計量/AI 分析…),利搜尋與分類 | category",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="用途說明(與該表 COMMENT ON TABLE 同源) | description",
        ),
        sa.Column(
            "sort_order",
            sa.SmallInteger(),
            nullable=True,
            comment="顯示排序 | display sort order",
        ),
        *_required_columns(),
        comment=(
            "資料表名稱對照字典:實體表名 → 中文顯示名 | "
            "data dictionary of table names"
        ),
    )
    op.execute(
        "CREATE TRIGGER trg_table_catalog_updated_at "
        "BEFORE UPDATE ON table_catalog "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )

    # 種子 19 筆;table_name UNIQUE + ON CONFLICT DO NOTHING 保冪等(重跑不重複)。
    insert_stmt = sa.text(
        "INSERT INTO table_catalog "
        "(table_catalog_uid, table_name, display_name_zh, category, sort_order) "
        "VALUES (:uid, :table_name, :display_name_zh, :category, :sort_order) "
        "ON CONFLICT (table_name) DO NOTHING"
    )
    bind = op.get_bind()
    for table_name, display_name_zh, category, sort_order in _SEED_ROWS:
        bind.execute(
            insert_stmt,
            {
                "uid": UUID(str(uuid7())),
                "table_name": table_name,
                "display_name_zh": display_name_zh,
                "category": category,
                "sort_order": sort_order,
            },
        )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_table_catalog_updated_at ON table_catalog"
    )
    op.drop_table("table_catalog")
