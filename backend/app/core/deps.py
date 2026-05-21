from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated

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

    return Actor(
        user_uid=user.user_uid,
        account=user.account,
        username=user.username,
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
    return await resolve_sdk_caller(db, sdk_key, user_token)


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
