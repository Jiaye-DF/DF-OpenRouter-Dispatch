from datetime import datetime

from fastapi import APIRouter, Request, Response

from app.core.config import get_settings
from app.core.deps import ClientIpDep, DbDep, UserDep
from app.core.response import success_response
from app.schemas.actor import Actor
from app.schemas.auth import LoginRequest
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


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


def _clear_cookies(resp: Response) -> None:
    settings = get_settings()
    resp.delete_cookie(settings.ACCESS_COOKIE_NAME, path="/")
    resp.delete_cookie(settings.REFRESH_COOKIE_NAME, path="/api/v1/auth")


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
    return resp


@router.post("/logout", summary="登出")
async def logout(request: Request, db: DbDep):
    settings = get_settings()
    cookie = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    await auth_service.logout(db, refresh_cookie=cookie)
    resp = success_response(detail="success")
    _clear_cookies(resp)
    return resp


@router.get("/me", summary="回傳當前登入 Actor")
async def me(actor: UserDep):
    return success_response(data=actor.model_dump(mode="json"), detail="success")
