from datetime import datetime
from urllib.parse import quote, urlencode

from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse

from app.clients import sso as sso_client
from app.clients.sso import SsoError
from app.core.config import get_settings
from app.core.deps import SSO_DISPLAY_COOKIE, ClientIpDep, DbDep, UserDep
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.core.response import success_response
from app.schemas.actor import Actor
from app.schemas.auth import LoginRequest
from app.services import auth as auth_service
from app.services import sso as sso_service

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# 存放 SSO token 的 cookie;掛 /api/v1/auth 路徑,使其僅隨 refresh / logout 上行。
_SSO_COOKIE_NAME = "sso_token"


def _set_access_cookie(resp: Response, token: str) -> None:
    settings = get_settings()
    resp.set_cookie(
        key=settings.ACCESS_COOKIE_NAME,
        value=token,
        max_age=settings.ACCESS_TOKEN_EXPIRES_MINUTES * 60,
        httponly=True,
        secure=settings.is_prod,
        samesite="lax",
        path="/",
    )


def _set_refresh_cookie(resp: Response, value: str, expires_at: datetime) -> None:
    settings = get_settings()
    max_age = settings.REFRESH_TOKEN_EXPIRES_DAYS * 86400
    resp.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=value,
        max_age=max_age,
        httponly=True,
        secure=settings.is_prod,
        samesite="strict",
        path="/api/v1/auth",
    )


def _set_sso_cookie(resp: Response, token: str) -> None:
    settings = get_settings()
    resp.set_cookie(
        key=_SSO_COOKIE_NAME,
        value=token,
        max_age=settings.REFRESH_TOKEN_EXPIRES_DAYS * 86400,
        httponly=True,
        secure=settings.is_prod,
        samesite="lax",
        path="/api/v1/auth",
    )


def _set_display_name_cookie(resp: Response, encoded_name: str) -> None:
    """設定 SSO 顯示姓名 cookie(值須為已 URL-encode 的字串)。

    掛 path `/` 使所有受保護端點的 require_user 都讀得到,確保 Actor 顯示一致。
    """
    settings = get_settings()
    resp.set_cookie(
        key=SSO_DISPLAY_COOKIE,
        value=encoded_name,
        max_age=settings.REFRESH_TOKEN_EXPIRES_DAYS * 86400,
        httponly=True,
        secure=settings.is_prod,
        samesite="lax",
        path="/",
    )


def _clear_cookies(resp: Response) -> None:
    settings = get_settings()
    resp.delete_cookie(settings.ACCESS_COOKIE_NAME, path="/")
    resp.delete_cookie(settings.REFRESH_COOKIE_NAME, path="/api/v1/auth")
    resp.delete_cookie(_SSO_COOKIE_NAME, path="/api/v1/auth")
    resp.delete_cookie(SSO_DISPLAY_COOKIE, path="/")


@router.post("/login", summary="登入")
async def login(
    body: LoginRequest,
    request: Request,
    db: DbDep,
    ip: ClientIpDep,
):
    ua = request.headers.get("user-agent")
    user, access, refresh_cookie, expires_at = await auth_service.login(
        db,
        account=body.account,
        password=body.password,
        user_agent=ua,
        ip=ip,
    )
    actor = Actor.model_validate(user)
    resp = success_response(data=actor.model_dump(mode="json"), detail="success")
    _set_access_cookie(resp, access)
    _set_refresh_cookie(resp, refresh_cookie, expires_at)
    # 帳號密碼登入:清除可能殘留的 SSO 顯示姓名,確保顯示本地 username。
    resp.delete_cookie(SSO_DISPLAY_COOKIE, path="/")
    return resp


@router.post("/refresh", summary="Refresh Access + Refresh（rotation）")
async def refresh(
    request: Request,
    db: DbDep,
    ip: ClientIpDep,
):
    settings = get_settings()
    cookie = request.cookies.get(settings.REFRESH_COOKIE_NAME, "")
    ua = request.headers.get("user-agent")
    user, access, refresh_cookie, expires_at = await auth_service.refresh(
        db,
        refresh_cookie=cookie,
        user_agent=ua,
        ip=ip,
    )
    actor = Actor.model_validate(user)
    resp = success_response(data=actor.model_dump(mode="json"), detail="success")
    _set_access_cookie(resp, access)
    _set_refresh_cookie(resp, refresh_cookie, expires_at)
    # SSO session:沿用並延長顯示姓名 cookie(值已為 encoded 形式,原樣回寫)。
    display = request.cookies.get(SSO_DISPLAY_COOKIE)
    if display:
        _set_display_name_cookie(resp, display)
    return resp


@router.post("/logout", summary="登出")
async def logout(request: Request, db: DbDep):
    settings = get_settings()
    cookie = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    await auth_service.logout(db, refresh_cookie=cookie)
    # SSO 登入者:通知中央撤銷 SSO session(契約 #2);best-effort,失敗不阻斷本地登出。
    sso_token = request.cookies.get(_SSO_COOKIE_NAME)
    if sso_token and settings.sso_enabled:
        fallback = f"{settings.FRONTEND_URL}/login?logged_out=1"
        await sso_client.notify_logout(sso_token, fallback)
    resp = success_response(detail="success")
    _clear_cookies(resp)
    return resp


@router.get("/me", summary="回傳當前登入 Actor")
async def me(actor: UserDep):
    return success_response(data=actor.model_dump(mode="json"), detail="success")


# --- DF-SSO 登入整合 -------------------------------------------------------
# 設計見 docs/Design-Base/70-auth.md § 18:SSO 作為登入閘道,通過後對應本地
# admin 帳號並沿用既有 Access + Refresh JWT session。


@router.get("/sso/login", summary="導向 DF-SSO 登入頁")
async def sso_login_redirect():
    """組出 SSO authorize URL 並 302 過去;前端登入按鈕直接連到此端點。

    未設定 SSO 時導回登入頁顯示提示(使用者可改用帳號密碼登入)。
    """
    settings = get_settings()
    if not settings.sso_enabled:
        if settings.FRONTEND_URL:
            return RedirectResponse(
                url=f"{settings.FRONTEND_URL}/login?error=sso_not_configured",
                status_code=302,
            )
        raise AppError("sso_not_configured", code=503)
    redirect_uri = f"{settings.BACKEND_URL}/api/v1/auth/sso/callback"
    query = urlencode({"client_id": settings.SSO_APP_ID, "redirect_uri": redirect_uri})
    return RedirectResponse(
        url=f"{settings.SSO_URL}/api/auth/sso/authorize?{query}",
        status_code=302,
    )


@router.get("/sso/callback", summary="DF-SSO 登入 callback")
async def sso_callback(
    request: Request,
    db: DbDep,
    ip: ClientIpDep,
    code: str | None = None,
):
    """SSO 驗證完成後的落點:換 token、對應本地 admin、簽發本地 session,導回前端。"""
    settings = get_settings()
    login_url = f"{settings.FRONTEND_URL}/login"
    if not settings.sso_enabled:
        return RedirectResponse(url=f"{login_url}?error=sso_not_configured", status_code=302)
    if not code:
        return RedirectResponse(url=f"{login_url}?error=no_code", status_code=302)

    ua = request.headers.get("user-agent")
    try:
        result = await sso_service.sso_login(db, code=code, user_agent=ua, ip=ip)
    except SsoError as exc:
        logger.info("SSO 登入失敗:%s", exc.reason)
        return RedirectResponse(url=f"{login_url}?error={exc.reason}", status_code=302)

    resp = RedirectResponse(url=f"{settings.FRONTEND_URL}/dashboard", status_code=302)
    _set_access_cookie(resp, result.access_token)
    _set_refresh_cookie(resp, result.refresh_cookie, result.refresh_expires_at)
    _set_sso_cookie(resp, result.sso_token)
    # 帶 SSO 本人姓名,使 /me 回傳的 Actor 顯示該姓名而非本地 username。
    if result.display_name:
        _set_display_name_cookie(resp, quote(result.display_name, safe=""))
    return resp


# back-channel logout 端點路徑由 SSO 中央寫死(`/api/auth/back-channel-logout`),
# 不在 /api/v1 之下,改由 app.api.back_channel 提供。
