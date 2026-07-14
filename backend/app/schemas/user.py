import re
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

_ACCOUNT_RE = re.compile(r"^[A-Za-z0-9._-]+$")

# users 表的 NOT NULL 欄位(models/user.py + models/base.py TimestampMixin):
# PATCH 時顯式送 null 會打穿 DB 約束,於 schema 層先擋(見 UserUpdateRequest)。
_NOT_NULL_FIELDS = ("username", "role", "is_active")


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
    """PATCH /users/{uid} 的部分更新 body。

    各欄 `None` 的語意是「**未提供、不更動**」(update_user 以 `exclude_unset` 取差集),
    並非「設為 NULL」。但 `username` / `role` / `is_active` 在 DB 為 NOT NULL,若呼叫端
    顯式送 `null`,exclude_unset 仍會保留該鍵並 setattr 成 None → flush 時 IntegrityError
    → 500。故於此擋下:顯式 null 這三欄一律 400,不落到 DB。
    """

    username: str | None = Field(default=None, min_length=1, max_length=128)
    role: Literal["admin", "user"] | None = None
    department_uid: UUID | None = None
    employee_id: str | None = Field(default=None, max_length=32)
    email: EmailStr | None = None
    is_active: bool | None = None

    @model_validator(mode="before")
    @classmethod
    def _reject_explicit_nulls(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for field in _NOT_NULL_FIELDS:
                if field in data and data[field] is None:
                    raise ValueError(f"{field} 不可為 null(欲不更動請省略此欄)")
        return data


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


class UserOwnerOption(BaseModel):
    """供申請表單『專案負責人』下拉:名稱 + 信箱(選取後前端自動帶入信箱)。"""

    model_config = ConfigDict(from_attributes=True)

    username: str
    email: str
