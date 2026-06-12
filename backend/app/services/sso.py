"""DF-SSO 登入整合：SSO 作為身分驗證閘道,對應本地 `users` 取得 role / department。

設計（對應使用者選定的「SSO 登入 + 本地角色對應」模式）：
- SSO 僅在「登入時」驗證身分;通過後沿用本平台既有的 Access + Refresh JWT session。
- 以 SSO 回傳的 Email 對應本地 `users`;與本地帳密登入一致,admin 與一般使用者皆可登入,
  頁面/API 權限再依 role 由前端 RouteGuard 與後端 AdminDep 控管。
- SSO 端 session 撤銷透過 back-channel logout 端點傳達(見 `api/v1/auth.py`);
  本地以 `users.sso_user_id`（azure oid）對應後撤銷該使用者全部 refresh token。
"""

import hashlib
import hmac
import time
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients import sso as sso_client
from app.clients.sso import SsoError
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.user import User
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.user import UserRepository
from app.services import auth as auth_service

logger = get_logger(__name__)

# Back-channel logout timestamp 容許誤差（雙向 abs,毫秒）
_BACK_CHANNEL_MAX_DRIFT_MS = 30_000


@dataclass(slots=True)
class SsoLoginResult:
    user: User
    access_token: str
    refresh_cookie: str
    refresh_expires_at: datetime
    sso_token: str
    display_name: str  # SSO 回傳的本人姓名,供前端顯示(可能為空字串)


async def sso_login(
    db: AsyncSession,
    *,
    code: str,
    user_agent: str | None,
    ip: str | None,
) -> SsoLoginResult:
    """完成 SSO callback：換 token + 使用者資料 → 對應本地使用者 → 簽發本地 session。

    任一步失敗擲 `SsoError`;callback 端點據 `reason` 導回登入頁顯示訊息。
    """
    sso_token, info = await sso_client.exchange(code)

    email = (info.email or "").strip().lower()
    if not email:
        raise SsoError("sso_no_email")

    repo = UserRepository(db)
    user = await repo.get_by_email(email)
    if user is None or user.is_deleted:
        raise SsoError("sso_no_account")
    if not user.is_active:
        raise SsoError("sso_inactive")

    # 記錄 SSO userId(azure oid),供 back-channel logout 反查本地帳號。
    if info.user_id and user.sso_user_id != info.user_id:
        user.sso_user_id = info.user_id

    access_token, refresh_cookie, expires_at = await auth_service.issue_session(
        db, user=user, user_agent=user_agent, ip=ip
    )
    await db.commit()
    logger.info("SSO 登入成功 account=%s email=%s", user.account, email)
    return SsoLoginResult(
        user=user,
        access_token=access_token,
        refresh_cookie=refresh_cookie,
        refresh_expires_at=expires_at,
        sso_token=sso_token,
        display_name=(info.name or "").strip(),
    )


def verify_back_channel_signature(
    user_id: str,
    timestamp: int,
    signature: str,
) -> tuple[bool, str | None]:
    """驗 back-channel logout 的 HMAC-SHA256 簽章（契約 #4）。

    訊息字串 `"{user_id}:{timestamp}"`、密鑰 `SSO_APP_SECRET`、30 秒雙向 drift;
    以 `hmac.compare_digest` 做 constant-time 比對。
    回傳 `(is_valid, reason)`,`reason ∈ {"timestamp_expired", "invalid_signature", None}`。
    """
    settings = get_settings()
    now_ms = int(time.time() * 1000)
    if abs(now_ms - timestamp) > _BACK_CHANNEL_MAX_DRIFT_MS:
        return False, "timestamp_expired"

    expected = hmac.new(
        settings.SSO_APP_SECRET.encode("utf-8"),
        f"{user_id}:{timestamp}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if len(signature) != len(expected) or not hmac.compare_digest(signature, expected):
        return False, "invalid_signature"
    return True, None


async def back_channel_logout(db: AsyncSession, *, user_id: str) -> None:
    """SSO 廣播登出:撤銷對應使用者本地全部 refresh token,強制下次重新登入。

    `user_id` 為 SSO azure oid;查無對應本地帳號則靜默結束（屬正常情形）。
    """
    repo = UserRepository(db)
    user = await repo.get_by_sso_user_id(user_id)
    if user is None:
        return
    rt_repo = RefreshTokenRepository(db)
    await rt_repo.revoke_all_for_user(user.user_uid, now=datetime.now(tz=UTC))
    await db.commit()
    logger.info("SSO back-channel logout：已撤銷 account=%s 的本地 session", user.account)
