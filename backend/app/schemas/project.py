from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreateRequest(BaseModel):
    department_uid: UUID
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None


class ProjectUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    is_active: bool | None = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_uid: UUID
    department_uid: UUID
    code: str
    name: str
    description: str | None
    is_active: bool
