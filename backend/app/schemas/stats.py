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
    total_requests: int
    total_tokens: int
    total_cost_usd: Decimal


class ModelStatItem(BaseModel):
    model: str
    total_requests: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    total_cost_usd: Decimal


class ProjectStatItem(BaseModel):
    project_uid: UUID
    project_code: str
    project_name: str
    total_requests: int
    total_tokens: int
    total_cost_usd: Decimal


class UserStatItem(BaseModel):
    user_uid: UUID | None
    username: str | None
    employee_id: str | None
    total_requests: int
    total_tokens: int
    total_cost_usd: Decimal


class TimeseriesPoint(BaseModel):
    bucket: datetime
    total_requests: int
    total_tokens: int
    total_cost_usd: Decimal
