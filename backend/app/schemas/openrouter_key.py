from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OpenRouterKeyCreateRequest(BaseModel):
    department_uid: UUID
    name: str = Field(min_length=1, max_length=128)
    key: str = Field(min_length=16, max_length=512)


class OpenRouterKeyUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    is_active: bool | None = None


class OpenRouterKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    openrouter_key_uid: UUID
    department_uid: UUID
    name: str
    key_prefix: str
    key_last4: str
    is_active: bool
