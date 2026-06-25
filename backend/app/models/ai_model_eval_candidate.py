from decimal import Decimal
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AiModelEvalCandidate(Base, TimestampMixin):
    """各評審候選子表(本版只建表,僅判別階段欄位)。

    `ai_evaluation_uid` 軟引用 `ai_model_evaluations.ai_evaluation_uid`(對應父表)。
    `model_uid` 軟引用 `models.model_uid`(此候選由哪個判別模型產生)。
    sub-table propose 僅列 created_at,但依任務卡 Acceptance 三表皆含 updated_at 必備欄位。
    """

    __tablename__ = "ai_model_eval_candidates"

    pid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ai_candidate_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), unique=True, nullable=False
    )
    # 軟引用 ai_model_evaluations.ai_evaluation_uid:對應父表
    ai_evaluation_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    # 軟引用 models.model_uid:此候選由哪個判別模型產生
    model_uid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    # 推薦模型(限白名單;v2.0.1 寫入)
    ai_recommend_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # 由 model 反查
    ai_recommend_tier: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # 推薦理由
    ai_recommend_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # dim3 吻合度 0–1
    ai_fit_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    # 推薦是否與原模型同廠商(偏差監控)
    ai_self_vote: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
