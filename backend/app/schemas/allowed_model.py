from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AllowedModelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    allowed_model_uid: UUID
    model_key: str
    note: str | None
    is_active: bool


class AllowedModelCreate(BaseModel):
    model_key: str = Field(min_length=1, max_length=256)
    note: str | None = Field(default=None, max_length=255)


class AllowedModelPatch(BaseModel):
    note: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None
