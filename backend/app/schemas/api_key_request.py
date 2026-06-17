from datetime import datetime
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# 允許的專案連結網域(host 全小寫後比對)。
# 子網域以 ".github.com" / ".replit.com" / ".replit.dev" 結尾判斷。
_ALLOWED_HOSTS = {"github.com", "www.github.com", "replit.com", "replit.dev"}
_ALLOWED_SUFFIXES = (".replit.com", ".replit.dev", ".github.com")


class ApiKeyRequestCreateRequest(BaseModel):
    department_name: str = Field(min_length=1, max_length=128)
    department_code: str = Field(min_length=1, max_length=32)
    project_name: str = Field(min_length=1, max_length=128)
    project_url: str = Field(min_length=1, max_length=512)
    owner_name: str = Field(min_length=1, max_length=64)
    owner_email: EmailStr

    @field_validator("project_url")
    @classmethod
    def _github_or_replit(cls, v: str) -> str:
        parts = urlsplit(v.strip())
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ValueError("project_url 須為 http/https 連結")
        host = parts.hostname.lower()
        if host in _ALLOWED_HOSTS or host.endswith(_ALLOWED_SUFFIXES):
            return v.strip()
        raise ValueError("project_url 須為 GitHub 或 Replit 連結")


class ApiKeyRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    request_uid: UUID
    applicant_user_uid: UUID
    department_name: str
    department_code: str
    project_name: str
    project_url: str
    owner_name: str
    owner_email: str
    status: str
    created_at: datetime
