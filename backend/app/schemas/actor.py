from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

Role = Literal["admin", "user"]


class Actor(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_uid: UUID
    account: str
    username: str
    email: str | None = None
    role: Role
    department_uid: UUID | None = None

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


class SdkCallerContext(BaseModel):
    sdk_api_key_uid: UUID
    department_uid: UUID
    department_code: str
    user_uid: UUID
    employee_id: str | None = None
    email: str | None = None
