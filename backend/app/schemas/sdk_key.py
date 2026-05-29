from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SdkKeyCreateRequest(BaseModel):
    department_uid: UUID
    name: str = Field(min_length=1, max_length=128)


class SdkKeyUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    is_active: bool | None = None


class SdkKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sdk_api_key_uid: UUID
    department_uid: UUID
    name: str
    key_prefix: str
    is_active: bool
    # 完整明文(admin 後台可隨時檢視;舊資料未填 → None)
    key_values: str | None = None


class SdkKeyCreateResponse(SdkKeyResponse):
    """建立時一次性回明文 key(向後相容欄位)。"""

    key: str
