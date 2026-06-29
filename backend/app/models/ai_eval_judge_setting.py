from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import BigInteger, SmallInteger
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AiEvalJudgeSetting(Base, TimestampMixin):
    """判別模型設定:被選為「判別模型」的模型(恰 3 筆有效,槽位 1/2/3)。

    `model_uid` 軟引用 `models.model_uid`(沿用本專案純 UUID 軟引用慣例,不建 DB 層 FK)。
    `ai_judge_slot` 為槽位 1/2/3,唯一,限定恰 3 個判別模型。
    """

    __tablename__ = "ai_eval_judge_settings"

    __table_args__ = (
        sa.Index(
            "idx_ai_eval_judge_settings_model_uid",
            "model_uid",
            postgresql_where=sa.text("(is_deleted = false)"),
        ),
        {"comment": "判別模型設定"},
    )

    pid: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        comment="內部自增主鍵,禁對外暴露 | internal auto-increment PK",
    )
    ai_judge_setting_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        unique=True,
        nullable=False,
        comment="對外 UUID 識別(UUIDv7) | external UID",
    )
    # 軟引用 models.model_uid:被選為判別模型的模型
    model_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        comment="被選為判別模型的模型(軟引用 models.model_uid) | judge model",
    )
    # 槽位 1/2/3(唯一,限定恰 3 個判別模型)
    ai_judge_slot: Mapped[int] = mapped_column(
        SmallInteger,
        unique=True,
        nullable=False,
        comment="判別模型槽位 1/2/3(唯一,限定恰 3 個) | judge slot 1/2/3",
    )
