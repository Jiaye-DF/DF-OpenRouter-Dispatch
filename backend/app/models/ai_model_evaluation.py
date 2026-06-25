from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import BigInteger, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AiModelEvaluation(Base, TimestampMixin):
    """模型適配評審結果父表(本版只建表,僅判別階段欄位)。

    `usage_log_uid` 軟引用 `usage_logs.usage_log_uid`,一對一(unique)。
    `department_uid` / `user_uid` 為 denormalize 欄位(null)。
    重跑(v2.0.2)、人類裁決(v2.0.3)、成本(v2.0.4)欄位本版不建,屆時各自 migration 增補。
    """

    __tablename__ = "ai_model_evaluations"

    __table_args__ = (
        sa.Index(
            "idx_ai_model_evaluations_status",
            "status",
            postgresql_where=sa.text("(is_deleted = false)"),
        ),
        {"comment": "模型評審結果"},
    )

    pid: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        comment="內部自增主鍵,禁對外暴露 | internal auto-increment PK",
    )
    ai_evaluation_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        unique=True,
        nullable=False,
        comment="對外 UUID 識別(UUIDv7) | external UID",
    )
    # 軟引用 usage_logs.usage_log_uid:來源 log,一對一(unique)
    usage_log_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        unique=True,
        nullable=False,
        comment="來源 log(軟引用 usage_logs.usage_log_uid,一對一 unique) | source usage log",
    )
    # denormalize 自 usage_logs(null)
    department_uid: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="部門(denormalize 自 usage_logs;軟引用 departments.department_uid) | denormalized department",
    )
    user_uid: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="使用者(denormalize 自 usage_logs;軟引用 users.user_uid) | denormalized user",
    )
    # 原模型(= usage_logs.model)
    ai_original_model: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="原使用模型(= usage_logs.model) | original model",
    )
    # 任務工作摘要(v2.0.1 寫入)
    ai_task_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="任務工作摘要(評審產出,v2.0.1 寫入) | task summary (judge output)",
    )
    # 任務意圖
    ai_task_intent: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="任務意圖(評審產出) | task intent (judge output)",
    )
    # 任務複雜度
    ai_task_complexity: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
        comment="任務複雜度(評審產出) | task complexity (judge output)",
    )
    # pending / evaluated / error
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="pending",
        server_default="pending",
        comment="評審狀態:pending/evaluated/error | evaluation status",
    )
    # 評審完成時間(null)
    ai_evaluated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="評審完成時間(UTC+8,v2.0.1 寫入) | evaluated at",
    )
