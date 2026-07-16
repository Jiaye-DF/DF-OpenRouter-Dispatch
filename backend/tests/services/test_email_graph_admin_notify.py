"""email_graph 管理員通知函式 + 共用底層測試(task-511;對齊 03-backend/07-testing.md)。

策略:
- **M365 走 respx / monkeypatch**:以 `respx` 攔截 Graph token / sendMail 端點,
  以 monkeypatch 注入 `get_settings`(不依賴真實 M365 設定)。
- **模板渲染直接斷言**:`render_email` 為純函式,直接 render `admin_apireq_verdict.html`
  斷言內容含判決語意 / 申請人 / request_uid,且不含一次性密鑰字串。
- 全程不觸網、不落 DB。
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest
import respx

import app.services.email_graph as svc
from app.services.email_render import render_email

_TENANT = "tenant-abc"
_SENDER = "notifier@corp.test"
_TOKEN_URL = f"https://login.microsoftonline.com/{_TENANT}/oauth2/v2.0/token"
_SENDMAIL_URL = f"https://graph.microsoft.com/v1.0/users/{_SENDER}/sendMail"


def _enabled_settings() -> SimpleNamespace:
    """M365 已配置的假 settings。"""
    return SimpleNamespace(
        m365_mail_enabled=True,
        M365_TENANT_ID=_TENANT,
        M365_CLIENT_ID="client-id",
        M365_CLIENT_SECRET="client-secret",
        M365_MAIL_SENDER=_SENDER,
    )


def _disabled_settings() -> SimpleNamespace:
    return SimpleNamespace(
        m365_mail_enabled=False,
        M365_TENANT_ID="",
        M365_CLIENT_ID="",
        M365_CLIENT_SECRET="",
        M365_MAIL_SENDER="",
    )


# ---------------------------------------------------------------------------
# ❶ M365 未配置 → send_admin_notify_email 回 m365_not_configured 且不 raise
# ---------------------------------------------------------------------------
async def test_admin_notify_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(svc, "get_settings", _disabled_settings)

    result = await svc.send_admin_notify_email(
        to_email="admin@corp.test",
        applicant_name="王小明",
        department="資訊部",
        project_name="智慧客服",
        status="manual_pending",
        reason=None,
        request_uid="req-uid-0001",
    )

    assert result.ok is False
    assert result.error == "m365_not_configured"


# ---------------------------------------------------------------------------
# ❷ 模板渲染:含判決語意 / 申請人 / request_uid;不含一次性密鑰字串
# ---------------------------------------------------------------------------
def test_admin_notify_template_content_and_no_secrets() -> None:
    ctx = {
        "applicant_name": "王小明",
        "department": "資訊部",
        "project_name": "智慧客服",
        "status": "agent_done",
        "status_zh": "已自動開通",
        "reason": "AI 欄位驗證通過",
        "request_uid": "req-uid-abcdef",
    }
    html = render_email("admin_apireq_verdict.html", **ctx)
    text = render_email("admin_apireq_verdict.txt", **ctx)

    for rendered in (html, text):
        # 判決 status(中文語意)/ 申請人 / request_uid 皆須出現
        assert "已自動開通" in rendered
        assert "王小明" in rendered
        assert "req-uid-abcdef" in rendered
        # 部門 / 專案 / reason 也應呈現
        assert "資訊部" in rendered
        assert "智慧客服" in rendered
        assert "AI 欄位驗證通過" in rendered
        # 禁含一次性密鑰欄位字串
        assert "sdk_key" not in rendered
        assert "user_token" not in rendered


def test_admin_notify_template_reason_optional() -> None:
    """reason 為 None 時模板不應噴錯,也不硬塞空原因欄。"""
    html = render_email(
        "admin_apireq_verdict.html",
        applicant_name="李小華",
        department="研發部",
        project_name="推薦引擎",
        status="cancelled",
        status_zh="已取消",
        reason=None,
        request_uid="req-uid-9999",
    )
    assert "已取消" in html
    assert "req-uid-9999" in html


# ---------------------------------------------------------------------------
# ❷b send_admin_notify_email 未知 status 原樣帶入(中文對映 fallback)
# ---------------------------------------------------------------------------
@respx.mock
async def test_admin_notify_send_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(svc, "get_settings", _enabled_settings)
    respx.post(_TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "tok-123"})
    )
    send_route = respx.post(_SENDMAIL_URL).mock(return_value=httpx.Response(202))

    result = await svc.send_admin_notify_email(
        to_email="admin@corp.test",
        applicant_name="王小明",
        department="資訊部",
        project_name="智慧客服",
        status="revoked",
        reason="管理員撤銷",
        request_uid="req-uid-0002",
    )

    assert result.ok is True
    assert send_route.called
    sent = json.loads(send_route.calls.last.request.content)
    # 收件人 = 傳入的管理員信箱
    assert sent["message"]["toRecipients"][0]["emailAddress"]["address"] == "admin@corp.test"
    # 送出的 HTML body 不含一次性密鑰欄位字串
    body = sent["message"]["body"]["content"]
    assert "sdk_key" not in body
    assert "user_token" not in body
    assert "已撤銷" in body


# ---------------------------------------------------------------------------
# ❸ send_provision_email 回歸:仍寄申請人、走共用 _send_mail
# ---------------------------------------------------------------------------
async def test_provision_email_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """M365 未配置時 send_provision_email 沿舊行為回 m365_not_configured。"""
    monkeypatch.setattr(svc, "get_settings", _disabled_settings)

    result = await svc.send_provision_email(
        to_email="owner@corp.test",
        owner_name="陳負責",
        project_name="智慧客服",
        secrets={"sdk_key": "SK-XYZ", "user_token": "UT-XYZ", "project_code": "PC-1"},
    )

    assert result.ok is False
    assert result.error == "m365_not_configured"


@respx.mock
async def test_provision_email_goes_through_send_mail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(svc, "get_settings", _enabled_settings)
    respx.post(_TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "tok-123"})
    )
    send_route = respx.post(_SENDMAIL_URL).mock(return_value=httpx.Response(202))

    # spy:確認確實走共用 _send_mail 底層
    calls: list[dict] = []
    orig_send_mail = svc._send_mail

    async def _spy(**kwargs: object) -> svc.EmailResult:
        calls.append(kwargs)
        return await orig_send_mail(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(svc, "_send_mail", _spy)

    result = await svc.send_provision_email(
        to_email="owner@corp.test",
        owner_name="陳負責",
        project_name="智慧客服",
        secrets={"sdk_key": "SK-XYZ", "user_token": "UT-XYZ", "project_code": "PC-1"},
    )

    assert result.ok is True
    # 走共用底層,且收件人 = 申請人(owner)
    assert len(calls) == 1
    assert calls[0]["to_email"] == "owner@corp.test"
    assert send_route.called
    sent = json.loads(send_route.calls.last.request.content)
    assert sent["message"]["toRecipients"][0]["emailAddress"]["address"] == "owner@corp.test"
