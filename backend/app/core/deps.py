from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import unquote

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.sdk_auth import resolve_sdk_caller
from app.core.security import decode_access_token
from app.schemas.actor import Actor, SdkCallerContext


SettingsDep = Annotated[Settings, Depends(get_settings)]
DbDep = Annotated[AsyncSession, Depends(get_db)]

# DF-SSO 登入的 session 會帶此 cookie(值為 URL-encoded 的 SSO 本人姓名);
# 用以讓 Actor 顯示 SSO 使用者姓名而非本地 username。帳號密碼登入不帶此 cookie。
SSO_DISPLAY_COOKIE = "sso_display_name"


async def require_user(
    request: Request,
    db: DbDep,
    settings: SettingsDep,
) -> Actor:
    # Import locally to avoid circular imports at module load.
    from app.repositories.user import UserRepository

    token = request.cookies.get(settings.ACCESS_COOKIE_NAME)
    if not token:
        raise AppError("unauthorized", code=401)
    try:
        payload = decode_access_token(token)
    except Exception as exc:  # noqa: BLE001
        raise AppError("unauthorized", code=401) from exc
    if payload.get("type") != "access":
        raise AppError("unauthorized", code=401)
    user_uid_raw = payload.get("sub")
    iat = payload.get("iat", 0)
    if not user_uid_raw:
        raise AppError("unauthorized", code=401)

    repo = UserRepository(db)
    user = await repo.get_by_uid(user_uid_raw)
    if user is None or user.is_deleted or not user.is_active:
        raise AppError("unauthorized", code=401)

    # 密碼變更後簽的舊 Access 失效
    if user.password_changed_at and user.password_changed_at > datetime.fromtimestamp(iat, tz=UTC):
        raise AppError("unauthorized", code=401)

    # SSO 登入的 session 帶 sso_display_name cookie → 顯示 SSO 本人姓名;
    # 帳號密碼登入無此 cookie,沿用本地 users.username(例:系統管理員)。
    raw_display = request.cookies.get(SSO_DISPLAY_COOKIE)
    display_name = unquote(raw_display)[:128] if raw_display else user.username

    return Actor(
        user_uid=user.user_uid,
        account=user.account,
        username=display_name,
        email=user.email,
        role=user.role,  # type: ignore[arg-type]
        department_uid=user.department_uid,
    )


def require_admin(
    actor: Annotated[Actor, Depends(require_user)],
) -> Actor:
    if not actor.is_admin:
        raise AppError("forbidden", code=403)
    return actor


async def optional_user(
    request: Request,
    db: DbDep,
    settings: SettingsDep,
) -> Actor | None:
    """有有效登入態則回 Actor,否則回 None(不擲錯)。

    供「公開可呼叫、但登入後可享進階行為」的端點使用,例如公開模型列表
    需辨識 admin 才開放 include_inactive。
    """
    try:
        return await require_user(request, db, settings)
    except AppError:
        return None


async def require_sdk_caller(
    request: Request,
    db: DbDep,
) -> SdkCallerContext:
    sdk_key = request.headers.get("x-sdk-key")
    user_token = request.headers.get("x-user-token")
    if not sdk_key or not user_token:
        raise AppError("unauthorized", code=401)
    project_code = request.headers.get("x-project-code")
    if not project_code:
        raise AppError("project_code_required", code=400)
    return await resolve_sdk_caller(db, sdk_key, user_token, project_code.strip())


UserDep = Annotated[Actor, Depends(require_user)]
AdminDep = Annotated[Actor, Depends(require_admin)]
OptionalUserDep = Annotated[Actor | None, Depends(optional_user)]
SdkCallerDep = Annotated[SdkCallerContext, Depends(require_sdk_caller)]


async def get_client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    if request.client:
        return request.client.host
    return ""


ClientIpDep = Annotated[str, Depends(get_client_ip)]
