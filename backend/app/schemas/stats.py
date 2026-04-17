from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class OverviewStats(BaseModel):
    total_requests: int
    total_tokens: int
    total_cost_usd: Decimal


class DepartmentStatItem(BaseModel):
    department_uid: UUID | None
    department_code: str | None
    department_name: str | None
    requests: int
    tokens: int
    cost_usd: Decimal


class ModelStatItem(BaseModel):
    model: str
    requests: int
    prompt_tokens: int
    completion_tokens: int
    tokens: int
    cost_usd: Decimal


class TimeseriesPoint(BaseModel):
    bucket: datetime
    requests: int
    tokens: int
    cost_usd: Decimal
