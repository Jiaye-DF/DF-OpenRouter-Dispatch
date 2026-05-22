from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils import uuid7

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.security import (
    create_access_token,
    generate_refresh_secret,
    hash_password,
    hash_refresh_secret,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.user import UserRepository
from app.services.password_policy import validate_password

_MAX_FAILED = 5
_LOCK_MINUTES = 15


async def issue_session(
    db: AsyncSession,
    *,
    user: User,
    user_agent: str | None,
    ip: str | None,
) -> tuple[str, str, datetime]:
    """為已完成身分驗證的使用者簽發 Access + Refresh Token。

    回傳 (access_token, refresh_cookie_value, refresh_expires_at);僅 flush 不 commit,
    由呼叫端負責 commit。供本地帳密登入與 DF-SSO 登入共用。
    """
    settings = get_settings()
    now = datetime.now(tz=UTC)
    rt_repo = RefreshTokenRepository(db)

    access_token = create_access_token(user.user_uid)
    refresh_uid = UUID(str(uuid7()))
    family_uid = UUID(str(uuid7()))
    secret = generate_refresh_secret()
    expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRES_DAYS)
    row = RefreshToken(
        refresh_token_uid=refresh_uid,
        user_uid=user.user_uid,
        family_uid=family_uid,
        token_hash=hash_refresh_secret(secret),
        issued_at=now,
        expires_at=expires_at,
        user_agent=(user_agent or "")[:512] or None,
        ip=ip or None,
    )
    rt_repo.add(row)
    await db.flush()
    return access_token, f"{refresh_uid}.{secret}", expires_at


async def login(
    db: AsyncSession,
    *,
    account: str,
    password: str,
    user_agent: str | None,
    ip: str | None,
) -> tuple[User, str, str, datetime]:
    """回傳 (user, access_token, refresh_cookie_value, refresh_expires_at)。"""
    repo = UserRepository(db)
    user = await repo.get_by_account(account)
    now = datetime.now(tz=UTC)

    if user is None or user.is_deleted:
        raise AppError("invalid_credentials", code=401)

    if user.locked_until is not None and user.locked_until > now:
        raise AppError("account_locked", code=423)

    if not user.is_active:
        raise AppError("invalid_credentials", code=401)

    if not verify_password(password, user.password_hash):
        user.failed_login_count += 1
        if user.failed_login_count >= _MAX_FAILED:
            user.locked_until = now + timedelta(minutes=_LOCK_MINUTES)
        await db.flush()
        await db.commit()
        raise AppError("invalid_credentials", code=401)

    # 僅 admin 可登入平台；一般使用者只作為 SDK 代理呼叫的身分識別。
    if user.role != "admin":
        raise AppError("invalid_credentials", code=401)

    user.failed_login_count = 0
    user.locked_until = None

    access_token, refresh_cookie, expires_at = await issue_session(
        db, user=user, user_agent=user_agent, ip=ip
    )
    await db.commit()
    return user, access_token, refresh_cookie, expires_at


async def refresh(
    db: AsyncSession,
    *,
    refresh_cookie: str,
    user_agent: str | None,
    ip: str | None,
) -> tuple[User, str, str, datetime]:
    if not refresh_cookie or "." not in refresh_cookie:
        raise AppError("unauthorized", code=401)
    uid_str, secret = refresh_cookie.split(".", 1)
    try:
        refresh_uid = UUID(uid_str)
    except ValueError as exc:
        raise AppError("unauthorized", code=401) from exc

    rt_repo = RefreshTokenRepository(db)
    user_repo = UserRepository(db)
    row = await rt_repo.get_by_uid(refresh_uid)
    if row is None:
        raise AppError("unauthorized", code=401)

    if not _constant_eq(row.token_hash, hash_refresh_secret(secret)):
        raise AppError("unauthorized", code=401)

    now = datetime.now(tz=UTC)
    if row.expires_at <= now:
        raise AppError("unauthorized", code=401)

    if row.revoked_at is not None:
        # Reuse detection
        if row.replaced_by_uid is not None:
            await rt_repo.revoke_family(row.family_uid, now=now)
            await db.commit()
            raise AppError("refresh_reuse_detected", code=401)
        raise AppError("unauthorized", code=401)

    user = await user_repo.get_by_uid(row.user_uid)
    if user is None or user.is_deleted or not user.is_active:
        raise AppError("unauthorized", code=401)

    settings = get_settings()
    new_uid = UUID(str(uuid7()))
    new_secret = generate_refresh_secret()
    expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRES_DAYS)
    new_row = RefreshToken(
        refresh_token_uid=new_uid,
        user_uid=user.user_uid,
        family_uid=row.family_uid,
        token_hash=hash_refresh_secret(new_secret),
        issued_at=now,
        expires_at=expires_at,
        user_agent=(user_agent or "")[:512] or None,
        ip=ip or None,
    )
    rt_repo.add(new_row)
    await rt_repo.revoke(row, now=now, replaced_by_uid=new_uid)
    await db.commit()

    access_token = create_access_token(user.user_uid)
    refresh_cookie_new = f"{new_uid}.{new_secret}"
    return user, access_token, refresh_cookie_new, expires_at


async def logout(db: AsyncSession, *, refresh_cookie: str | None) -> None:
    if not refresh_cookie or "." not in refresh_cookie:
        return
    uid_str, _secret = refresh_cookie.split(".", 1)
    try:
        refresh_uid = UUID(uid_str)
    except ValueError:
        return
    rt_repo = RefreshTokenRepository(db)
    row = await rt_repo.get_by_uid(refresh_uid)
    if row is None or row.revoked_at is not None:
        return
    await rt_repo.revoke(row, now=datetime.now(tz=UTC))
    await db.commit()


async def admin_reset_password(
    db: AsyncSession,
    *,
    target_user_uid: UUID,
    new_password: str,
) -> None:
    repo = UserRepository(db)
    rt_repo = RefreshTokenRepository(db)
    user = await repo.get_by_uid(target_user_uid)
    if user is None or user.is_deleted:
        raise AppError("not_found", code=404)
    validate_password(new_password)
    now = datetime.now(tz=UTC)
    user.password_hash = hash_password(new_password)
    user.password_changed_at = now
    user.failed_login_count = 0
    user.locked_until = None
    await rt_repo.revoke_all_for_user(user.user_uid, now=now)
    await db.flush()


def _constant_eq(a: str, b: str) -> bool:
    import hmac

    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
