import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

_ACCOUNT_RE = re.compile(r"^[A-Za-z0-9._-]+$")


class UserCreateRequest(BaseModel):
    # 一般使用者（role="user"）不在平台登入，account/password 由後端自動產生；
    # 僅 role="admin" 需要 admin 指定 account + password。
    account: str | None = Field(default=None, min_length=4, max_length=64)
    username: str = Field(min_length=1, max_length=128)
    password: str | None = Field(default=None, min_length=10, max_length=128)
    role: Literal["admin", "user"] = "user"
    department_uid: UUID | None = None
    employee_id: str | None = Field(default=None, max_length=32)
    email: EmailStr | None = None

    @field_validator("account")
    @classmethod
    def _account_pattern(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not _ACCOUNT_RE.fullmatch(v):
            raise ValueError("account 只能包含英數字與 . _ -")
        return v


class UserUpdateRequest(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=128)
    role: Literal["admin", "user"] | None = None
    department_uid: UUID | None = None
    employee_id: str | None = Field(default=None, max_length=32)
    email: EmailStr | None = None
    is_active: bool | None = None


class UserPasswordResetRequest(BaseModel):
    new_password: str = Field(min_length=10, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_uid: UUID
    account: str
    username: str
    role: str
    department_uid: UUID | None
    employee_id: str | None
    email: str | None
    is_active: bool


class UserDropdownItem(BaseModel):
    """供儀表板下拉用的精簡欄位(v1.5)。"""
    model_config = ConfigDict(from_attributes=True)

    user_uid: UUID
    username: str
    employee_id: str | None
    department_uid: UUID | None
