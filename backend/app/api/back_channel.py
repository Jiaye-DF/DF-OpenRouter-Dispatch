"""DF-SSO back-channel logout 端點。

DF-SSO 中央寫死對 `<已註冊 origin>/api/auth/back-channel-logout` 發送廣播登出
（見 DF-SSO `backend/routes/sso.js` / `auth.js`），路徑不可調整,故此 router 直接
掛在 app 層的 `/api/auth`,不在專案其他 API 的 `/api/v1` 前綴之下。
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.deps import DbDep
from app.core.logging import get_logger
from app.schemas.sso import BackChannelLogoutRequest
from app.services import sso as sso_service

logger = get_logger(__name__)

router = APIRouter(prefix="/api/auth", tags=["sso"])


@router.post("/back-channel-logout", summary="DF-SSO 廣播登出(契約 #4)")
async def back_channel_logout(payload: BackChannelLogoutRequest, db: DbDep):
    """中央廣播登出:驗 HMAC + timestamp 後撤銷該使用者本地全部 refresh token。

    由 SSO 中央 server-to-server 呼叫,不套用專案統一回應格式;以原生 JSON 回應。
    """
    if not get_settings().sso_enabled:
        return JSONResponse(status_code=404, content={"error": "not_found"})
    ok, reason = sso_service.verify_back_channel_signature(
        payload.user_id, payload.timestamp, payload.signature
    )
    if not ok:
        logger.warning("SSO back-channel logout 簽章驗證失敗:%s", reason)
        return JSONResponse(status_code=401, content={"error": reason})
    await sso_service.back_channel_logout(db, user_id=payload.user_id)
    return JSONResponse(status_code=200, content={"success": True})
