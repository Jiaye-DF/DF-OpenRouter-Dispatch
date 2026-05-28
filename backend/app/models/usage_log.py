from decimal import Decimal
from uuid import UUID

from sqlalchemy import BigInteger, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class UsageLog(Base, TimestampMixin):
    __tablename__ = "usage_logs"

    pid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    usage_log_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), unique=True, nullable=False
    )
    user_uid: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    department_uid: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    # v1.5 加入;允許 NULL 以容錯既有歷史紀錄(代理新呼叫一律必帶 X-Project-Id)
    project_uid: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    openrouter_key_uid: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    # V11 加入;允許 NULL 容錯既有歷史與白名單拒絕情境
    model_uid: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_content: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    response_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    openrouter_generation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
