"""DF-SSO 整合相關 Schema。

對應 DF-SSO INTEGRATION.md「用戶資料格式」與「Back-channel Logout 端點」契約。
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SsoUserInfo(BaseModel):
    """中央 /api/auth/me 回應的 user 物件。

    中央以 camelCase 回傳,故用 alias 對應;erpData 可能為 null(AD 有但 ERP 找不到員工)。
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    user_id: str = Field(alias="userId")
    email: str = Field(default="")
    name: str = Field(default="")
    erp_data: dict[str, Any] | None = Field(default=None, alias="erpData")
    login_at: str | None = Field(default=None, alias="loginAt")


class BackChannelLogoutRequest(BaseModel):
    """SSO 廣播登出 POST body(契約 #4)。"""

    user_id: str
    timestamp: int
    signature: str
