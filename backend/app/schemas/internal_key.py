from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InternalKeyCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    base_url: str = Field(min_length=1, max_length=512)
    api_key: str | None = Field(default=None, max_length=512)  # 內網信任時可空
    rpm_limit: int = Field(default=0, ge=0)
    min_request_interval_ms: int = Field(default=0, ge=0)


class InternalKeyUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    base_url: str | None = Field(default=None, min_length=1, max_length=512)
    api_key: str | None = Field(default=None, max_length=512)  # 傳值 = 換 Key;omit = 不動
    is_active: bool | None = None
    rpm_limit: int | None = Field(default=None, ge=0)
    min_request_interval_ms: int | None = Field(default=None, ge=0)


class InternalKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    internal_key_uid: UUID
    name: str
    base_url: str
    has_api_key: bool                # 是否設置了 api_key(明文與 hash 都不外洩)
    key_last4: str | None = None     # 若有 api_key 才有值
    rpm_limit: int
    min_request_interval_ms: int
    is_active: bool
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
