from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DepartmentCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=32)  # 成本中心代碼
    org_code: str = Field(min_length=1, max_length=32)  # 組織代碼
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None


class DepartmentUpdateRequest(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=32)  # 成本中心代碼
    org_code: str | None = Field(default=None, min_length=1, max_length=32)  # 組織代碼
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    is_active: bool | None = None


class DepartmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    department_uid: UUID
    code: str
    org_code: str | None
    name: str
    description: str | None
    is_active: bool
