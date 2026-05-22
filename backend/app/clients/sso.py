"""DF-SSO 中央伺服器 server-to-server 呼叫。

對應 DF-SSO INTEGRATION.md：所有呼叫一律 `Cache-Control: no-store` 且套用 ≤8s timeout。
`SSO_APP_SECRET` 僅於此後端使用,絕不外流前端。
"""

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.sso import SsoUserInfo

logger = get_logger(__name__)


class SsoError(Exception):
    """SSO 流程失敗;`reason` 會帶到前端登入頁 `?error=` 供顯示。"""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _no_store(extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {"Cache-Control": "no-store"}
    if extra:
        headers.update(extra)
    return headers


async def exchange(code: str) -> tuple[str, SsoUserInfo]:
    """以 auth code 換 SSO token + 使用者資料(帶 client_secret,server-to-server)。

    DF-SSO `/api/auth/sso/exchange` 同時回傳 `token` 與 `user`,故登入時毋須再打 `/me`。
    成功回傳 `(sso_token, SsoUserInfo)`;失敗擲 `SsoError`。
    """
    settings = get_settings()
    timeout = httpx.Timeout(settings.SSO_TIMEOUT_SECONDS)
    try:
        async with httpx.AsyncClient(base_url=settings.SSO_URL, timeout=timeout) as client:
            resp = await client.post(
                "/api/auth/sso/exchange",
                json={
                    "code": code,
                    "client_id": settings.SSO_APP_ID,
                    "client_secret": settings.SSO_APP_SECRET,
                },
                headers=_no_store(),
            )
    except httpx.HTTPError as exc:
        logger.warning("SSO exchange 連線失敗: %s", exc)
        raise SsoError("exchange_error") from exc

    if resp.status_code != 200:
        logger.warning("SSO exchange 失敗 status=%s", resp.status_code)
        raise SsoError("exchange_failed")
    try:
        body = resp.json()
    except Exception as exc:  # noqa: BLE001
        raise SsoError("exchange_failed") from exc
    if not isinstance(body, dict):
        raise SsoError("exchange_failed")
    token = body.get("token")
    user = body.get("user")
    if not token or not isinstance(token, str) or not isinstance(user, dict):
        raise SsoError("exchange_failed")
    return token, SsoUserInfo.model_validate(user)


async def notify_logout(token: str, redirect: str) -> None:
    """通知中央登出（契約 #2）;best-effort,失敗僅記錄不阻斷本地登出。"""
    settings = get_settings()
    timeout = httpx.Timeout(settings.SSO_TIMEOUT_SECONDS)
    try:
        async with httpx.AsyncClient(base_url=settings.SSO_URL, timeout=timeout) as client:
            await client.post(
                "/api/auth/logout",
                json={"redirect": redirect},
                headers=_no_store({"Authorization": f"Bearer {token}"}),
            )
    except httpx.HTTPError as exc:
        logger.warning("SSO logout 通知失敗(已忽略): %s", exc)
