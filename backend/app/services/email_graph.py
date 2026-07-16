"""Microsoft Graph(app-only client credentials)寄信 service(v1.9.2 / v2.2.0)。

開通完成後以 Graph `sendMail` 寄憑證通知信給專案負責人;v2.2.0 起另提供
`send_admin_notify_email` 寄申請單判決通知信給系統管理員。兩者共用內部
`_send_mail` 底層(M365 token 取得 + Graph `sendMail` POST + best-effort 錯誤處理)。

best-effort:降級 / 失敗皆回 `EmailResult(ok=False, error=...)`,由呼叫端決定是否
視為錯誤;M365 未配置回 `EmailResult(ok=False, error="m365_not_configured")`,**不 raise**。

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

# 申請單判決 status → 中文語意(對映 api_key_requests 五種終態);未知值原樣顯示。
_STATUS_ZH = {
    "manual_pending": "轉人工待處理",
    "agent_done": "已自動開通",
    "done": "已完成",
    "revoked": "已撤銷",
    "cancelled": "已取消",
}


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


async def _send_mail(
    *,
    to_email: str,
    subject: str,
    html: str,
    text: str,
) -> EmailResult:
    """共用 M365 Graph 寄信底層(收件人 / 主旨 / 內文可指定)。

    Graph `sendMail` 單一 message body,以 HTML 版寄出;`text` 為純文字版本,
    保留於簽章供呼叫端渲染純文字內容(Graph 僅送單一 HTML body,故不併入 payload)。
    best-effort:M365 未配置 → `EmailResult(ok=False, error="m365_not_configured")`,不 raise。
    """
    _ = text  # Graph sendMail 單一 body,純文字版本目前不併入 payload(保留簽章對稱)。
    settings = get_settings()
    if not settings.m365_mail_enabled:
        return EmailResult(ok=False, error="m365_not_configured")

    to_domain = _domain(to_email)

    body = {
        "message": {
            "subject": subject,
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


async def send_provision_email(
    *,
    to_email: str,
    owner_name: str,
    project_name: str,
    secrets: dict,
) -> EmailResult:
    """寄送開通完成憑證信給專案負責人(收件人 = 申請人)。

    `secrets` 為 v1.9.1 的 provisioned_secrets:
        { "sdk_key": str|None, "user_token": str|None, "project_code": str|None }
    回 `EmailResult`;m365 未設定 → ok=False/error="m365_not_configured"(呼叫端不視為錯誤)。
    """
    html = render_email(
        "provision.html",
        owner_name=owner_name,
        project_name=project_name,
        project_code=secrets.get("project_code") or "",
        sdk_key=secrets.get("sdk_key") or "",
        user_token=secrets.get("user_token") or "",
    )

    return await _send_mail(
        to_email=to_email,
        subject="Agent 代發: OpenRouter API Key 平台申請已開通",
        html=html,
        text="",
    )


async def send_admin_notify_email(
    *,
    to_email: str,
    applicant_name: str,
    department: str,
    project_name: str,
    status: str,
    reason: str | None,
    request_uid: str,
) -> EmailResult:
    """寄送申請單判決通知信給系統管理員(收件人 = 管理員)。

    內容含申請人 / 部門 / 專案、判決 status(中文語意)、reason(若有)、申請單對外
    `request_uid`;**不含**一次性密鑰、內部 pid、收件人以外 PII。
    best-effort:m365 未配置 → ok=False/error="m365_not_configured",不 raise。
    """
    status_zh = _STATUS_ZH.get(status, status)
    ctx = {
        "applicant_name": applicant_name,
        "department": department,
        "project_name": project_name,
        "status": status,
        "status_zh": status_zh,
        "reason": reason,
        "request_uid": request_uid,
    }
    html = render_email("admin_apireq_verdict.html", **ctx)
    text = render_email("admin_apireq_verdict.txt", **ctx)

    return await _send_mail(
        to_email=to_email,
        subject=f"申請單判決通知: {project_name}({status_zh})",
        html=html,
        text=text,
    )
