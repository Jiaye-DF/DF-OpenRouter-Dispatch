from datetime import datetime

from pydantic import BaseModel


class UserTokenGenerateResponse(BaseModel):
    token: str
    issued_at: datetime


class UserTokenRevokeRequest(BaseModel):
    reason: str | None = None
