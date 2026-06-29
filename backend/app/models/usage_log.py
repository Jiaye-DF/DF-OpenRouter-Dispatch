from datetime import datetime
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import BigInteger, Boolean, DateTime, Integer, Numeric, SmallInteger, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class UsageLog(Base, TimestampMixin):
    __tablename__ = "usage_logs"

    __table_args__ = (
        sa.Index(
            "idx_usage_logs_ai_unevaluated",
            sa.text("created_at DESC"),
            postgresql_where=sa.text("ai_evaluated_at IS NULL AND is_deleted = false"),
        ),
        sa.Index(
            "idx_usage_logs_created_at",
            sa.text("created_at DESC"),
            postgresql_where=sa.text("is_deleted = false"),
        ),
        sa.Index(
            "idx_usage_logs_dept_time",
            "department_uid",
            sa.text("created_at DESC"),
        ),
        sa.Index(
            "idx_usage_logs_model_time",
            "model",
            sa.text("created_at DESC"),
        ),
        sa.Index(
            "idx_usage_logs_model_uid_time",
            "model_uid",
            sa.text("created_at DESC"),
        ),
        sa.Index(
            "idx_usage_logs_project_uid_time",
            "project_uid",
            "created_at",
            postgresql_where=sa.text("is_deleted = false"),
        ),
        sa.Index(
            "idx_usage_logs_used_tools_time",
            sa.text("created_at DESC"),
            postgresql_where=sa.text("used_tools = true AND is_deleted = false"),
        ),
        sa.Index(
            "idx_usage_logs_user_time",
            "user_uid",
            sa.text("created_at DESC"),
        ),
        sa.ForeignKeyConstraint(
            ["project_uid"],
            ["projects.project_uid"],
            name="fk_usage_logs_project_uid",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["department_uid"],
            ["departments.department_uid"],
            name="usage_logs_department_uid_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["model_uid"],
            ["models.model_uid"],
            name="usage_logs_model_uid_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["openrouter_key_uid"],
            ["openrouter_keys.openrouter_key_uid"],
            name="usage_logs_openrouter_key_uid_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["user_uid"],
            ["users.user_uid"],
            name="usage_logs_user_uid_fkey",
        ),
        {"comment": "用量紀錄"},
    )

    pid: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        comment="內部自增主鍵,禁對外暴露 | internal auto-increment PK",
    )
    usage_log_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        unique=True,
        nullable=False,
        comment="對外 UUID 識別(UUIDv7) | external UID",
    )
    user_uid: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="呼叫者 user_uid | caller user UID",
    )
    department_uid: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="呼叫者所屬部門 UID | caller department UID",
    )
    project_uid: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="v1.5 加入;允許 NULL 以容錯既有歷史紀錄(代理新呼叫一律必帶 X-Project-Code) | project UID",
    )
    openrouter_key_uid: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="本次呼叫使用的 OpenRouter 金鑰 UID | OpenRouter key UID",
    )
    model: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="呼叫的模型 key | model key",
    )
    model_uid: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="v1.1 加入;允許 NULL 容錯既有歷史與白名單拒絕情境 | model UID",
    )
    prompt_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="prompt token 數 | prompt tokens",
    )
    completion_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="completion token 數 | completion tokens",
    )
    total_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="總 token 數 | total tokens",
    )
    cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6),
        nullable=False,
        default=0,
        comment="本次呼叫成本(USD) | cost in USD",
    )
    latency_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="延遲(毫秒) | latency in ms",
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        comment="呼叫狀態 | call status",
    )
    error_code: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="錯誤碼;NULL = 無錯誤 | error code",
    )
    request_content: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="請求內容 | request content",
    )
    response_summary: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="回應摘要 | response summary",
    )
    openrouter_generation_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="OpenRouter 生成 ID | OpenRouter generation ID",
    )
    used_tools: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        default=False,
        comment="v1.6.2 加入;本次呼叫是否帶 tools(如 web search),tools 可能觸發額外計費,標記供後台篩選與計費分析 | used tools flag",
    )
    ai_evaluated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="v2.0 加入;最新一次評審執行時間(全棧 UTC+8),NULL=尚未評審;不論成敗皆由評審寫入端更新;排程器以 IS NULL 掃出待評審筆 | AI evaluated at",
    )
    ai_evaluated_status: Mapped[int | None] = mapped_column(
        SmallInteger,
        nullable=True,
        comment="v2.0 加入;最新一次評審結果:NULL=尚未評審、0=失敗、1=成功 | AI evaluated status",
    )
