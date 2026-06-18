"""Microsoft Graph(app-only client credentials)寄信 service(v1.9.2)。

開通完成後以 Graph `sendMail` 寄憑證通知信給專案負責人;best-effort,
降級 / 失敗皆回 `EmailResult(ok=False, error=...)` 由呼叫端決定是否視為錯誤。

安全:log 一律不含憑證明文 / token / 完整收件 email,僅記收件網域與狀態碼。
"""

from dataclasses import dataclass

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.email_render import render_email

logger = get_logger(__name__)

# Graph 無專屬 timeout 設定,沿用 sso.py 的獨立 AsyncClient 風格,固定 10s。
_TIMEOUT = httpx.Timeout(10.0)

_TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
_SENDMAIL_URL = "https://graph.microsoft.com/v1.0/users/{sender}/sendMail"


@dataclass
class EmailResult:
    ok: bool
    error: str | None = None


def _domain(email: str) -> str:
    """取收件 email 的網域部分供 log 用(避免記錄完整 email)。"""
    return email.split("@")[-1]


async def _fetch_token(client: httpx.AsyncClient, to_domain: str) -> str | None:
    settings = get_settings()
    try:
        resp = await client.post(
            _TOKEN_URL.format(tenant=settings.M365_TENANT_ID),
            data={
                "grant_type": "client_credentials",
                "scope": "https://graph.microsoft.com/.default",
                "client_id": settings.M365_CLIENT_ID,
                "client_secret": settings.M365_CLIENT_SECRET,
            },
        )
    except httpx.HTTPError as exc:
        logger.warning("M365 取 token 連線失敗 domain=%s: %s", to_domain, exc)
        return None

    if resp.status_code // 100 != 2:
        logger.warning("M365 取 token 失敗 domain=%s status=%s", to_domain, resp.status_code)
        return None
    try:
        token = resp.json().get("access_token")
    except Exception:  # noqa: BLE001
        token = None
    if not token or not isinstance(token, str):
        logger.warning("M365 取 token 回應無 access_token domain=%s", to_domain)
        return None
    return token


async def send_provision_email(
    *,
    to_email: str,
    owner_name: str,
    project_name: str,
    secrets: dict,
) -> EmailResult:
    """寄送開通完成憑證信。

    `secrets` 為 v1.9.1 的 provisioned_secrets:
        { "sdk_key": str|None, "user_token": str|None, "project_code": str|None }
    回 `EmailResult`;m365 未設定 → ok=False/error="m365_not_configured"(呼叫端不視為錯誤)。
    """
    settings = get_settings()
    if not settings.m365_mail_enabled:
        return EmailResult(ok=False, error="m365_not_configured")

    to_domain = _domain(to_email)

    html = render_email(
        "provision.html",
        owner_name=owner_name,
        project_name=project_name,
        project_code=secrets.get("project_code") or "",
        sdk_key=secrets.get("sdk_key") or "",
        user_token=secrets.get("user_token") or "",
    )

    body = {
        "message": {
            "subject": "Agent 代發: OpenRouter API Key 平台申請已開通",
            "body": {"contentType": "HTML", "content": html},
            "toRecipients": [{"emailAddress": {"address": to_email}}],
        },
        "saveToSentItems": False,
    }

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        token = await _fetch_token(client, to_domain)
        if token is None:
            return EmailResult(ok=False, error="m365_token_error")

        try:
            resp = await client.post(
                _SENDMAIL_URL.format(sender=settings.M365_MAIL_SENDER),
                headers={"Authorization": f"Bearer {token}"},
                json=body,
            )
        except httpx.HTTPError as exc:
            logger.warning("M365 sendMail 連線失敗 domain=%s: %s", to_domain, exc)
            return EmailResult(ok=False, error="m365_send_error")

    if resp.status_code // 100 != 2:
        logger.warning("M365 sendMail 失敗 domain=%s status=%s", to_domain, resp.status_code)
        return EmailResult(ok=False, error=f"m365_sendmail_{resp.status_code}")

    logger.info("M365 sendMail 成功 domain=%s status=%s", to_domain, resp.status_code)
    return EmailResult(ok=True)
