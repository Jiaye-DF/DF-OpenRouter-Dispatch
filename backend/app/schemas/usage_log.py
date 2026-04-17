from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UsageLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    usage_log_uid: UUID
    user_uid: UUID | None
    department_uid: UUID | None
    openrouter_key_uid: UUID | None
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: Decimal
    latency_ms: int
    status: str
    error_code: str | None
    request_content: dict[str, Any] | None
    response_summary: dict[str, Any] | None
    openrouter_generation_id: str | None
    created_at: datetime
