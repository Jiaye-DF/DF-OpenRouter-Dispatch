from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OpenRouterKeyCreateRequest(BaseModel):
    department_uid: UUID
    name: str = Field(min_length=1, max_length=128)
    key: str = Field(min_length=16, max_length=512)
    rpm_limit: int = Field(default=0, ge=0)
    min_request_interval_ms: int = Field(default=0, ge=0)


class OpenRouterKeyUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    is_active: bool | None = None
    rpm_limit: int | None = Field(default=None, ge=0)
    min_request_interval_ms: int | None = Field(default=None, ge=0)


class OpenRouterKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    openrouter_key_uid: UUID
    department_uid: UUID
    name: str
    key_prefix: str
    key_last4: str
    is_active: bool

    # 餘額 4 欄 — 僅 admin 可見;router 對非 admin 須剔除(目前列表/單筆皆走 AdminDep)。
    credits_used_usd: Decimal | None = None
    credits_limit_usd: Decimal | None = None
    credits_is_free_tier: bool | None = None
    credits_synced_at: datetime | None = None

    # v1.2 速率限制(0 = 不限)
    rpm_limit: int
    min_request_interval_ms: int
