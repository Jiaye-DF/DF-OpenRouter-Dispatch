"""申請單各終態觸發管理員通知整合測試(task-512;propose §B.2 / §D.4 / §D.5 / §D.6)。

沿用本專案 API 測試 mock 風格(見 tests/api/test_users_disable.py):
- FastAPI app + httpx.AsyncClient(ASGITransport),get_db 覆寫為假 AsyncSession。
- repository / service 以替身取代:`ApiKeyRequestRepository` / `UserRepository` 走 in-memory
  store 假件;`router_svc.route` / `provision.provision` 以假件替代(不觸 AI / 不建資源)。
- `send_admin_notify_email` / `send_provision_email` 以 spy 攔截,驗證「是否寄、寄給誰、帶何 status」。
- 驗證鏈(require_user)走真實程式碼;`notify_admin_on_verdict` 走真實程式碼。

涵蓋 Acceptance:❶ 開啟+admin 有 email → 建立判出終態後 send_admin_notify_email 被呼叫(收件=admin);
❷ 關閉 → 不呼叫;❸ admin 無 email → 不呼叫、不報錯、主流程正常;
❹ send_admin_notify_email 拋例外 → 主流程仍成功、申請人通知不受影響;
❺ 人工 process / cancel / revoke 終態亦各觸發一次。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

import app.api.v1.api_key_requests as apikey_api
import app.repositories.user as user_repo_mod
from app.clients.openrouter.client import get_openrouter_client
from app.core.config import get_settings as real_get_settings
from app.core.database import get_db
from app.core.security import create_access_token
from app.main import create_app
from app.models.api_key_request import ApiKeyRequest
from app.models.audit_log import AuditLog
from app.services.email_graph import EmailResult

pytestmark = pytest.mark.asyncio

_CREATE_BODY = {
    "department_name": "資訊部",
    "department_code": "IT",
    "project_name": "智慧客服",
    "project_url": "https://github.com/df/demo",
    "owner_name": "王小明",
    "owner_email": "owner@df-recycle.com.tw",
}


# --- in-memory store ---------------------------------------------------------


@dataclass
class _Store:
    users: list[SimpleNamespace] = field(default_factory=list)
    requests: dict[str, ApiKeyRequest] = field(default_factory=dict)
    audits: list[AuditLog] = field(default_factory=list)
    admin_notify_calls: list[dict] = field(default_factory=list)
    owner_notify_calls: list[dict] = field(default_factory=list)


_store = _Store()


# --- fake db / repositories --------------------------------------------------


class _FakeNested:
    async def __aenter__(self) -> _FakeNested:
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False


class _FakeDb:
    """假 AsyncSession:承接 write_audit 的 db.add(AuditLog)、advisory lock 的 execute 等。"""

    def add(self, row: object) -> None:
        if isinstance(row, AuditLog):
            _store.audits.append(row)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None

    async def execute(self, *args: object, **kwargs: object) -> SimpleNamespace:
        # _lock_dedup_key 的 pg_advisory_xact_lock,回傳值不被使用。
        return SimpleNamespace()

    def begin_nested(self) -> _FakeNested:
        return _FakeNested()


class _FakeApiKeyRequestRepo:
    def __init__(self, db: object) -> None:
        self.db = db

    def add(self, row: ApiKeyRequest) -> None:
        # 未落地的 transient row 無 server_default,補 created_at 供 response 序列化。
        if getattr(row, "created_at", None) is None:
            row.created_at = datetime.now(tz=UTC)
        _store.requests[str(row.request_uid)] = row

    async def get_by_uid(self, uid: UUID) -> ApiKeyRequest | None:
        return _store.requests.get(str(uid))


class _FakeUserRepo:
    def __init__(self, db: object) -> None:
        self.db = db

    async def get_by_uid(self, user_uid: UUID | str) -> SimpleNamespace | None:
        uid = str(user_uid)
        for u in _store.users:
            if str(u.user_uid) == uid and not u.is_deleted:
                return u
        return None

    async def get_by_account(self, account: str) -> SimpleNamespace | None:
        for u in _store.users:
            if u.account.lower() == account.lower() and not u.is_deleted:
                return u
        return None


# --- fake services -----------------------------------------------------------


async def _admin_spy(**kwargs: object) -> EmailResult:
    _store.admin_notify_calls.append(kwargs)
    return EmailResult(ok=True)


async def _admin_raise(**kwargs: object) -> EmailResult:
    _store.admin_notify_calls.append(kwargs)
    raise RuntimeError("boom")


async def _owner_spy(**kwargs: object) -> EmailResult:
    _store.owner_notify_calls.append(kwargs)
    return EmailResult(ok=True)


async def _route_system_cancel(db: object, row: object) -> SimpleNamespace:
    return SimpleNamespace(
        decision="system_cancel", reason="系統自動取消", matched_department=None
    )


async def _route_ai_matched(db: object, row: object) -> SimpleNamespace:
    return SimpleNamespace(
        decision="ai",
        reason=None,
        matched_department=SimpleNamespace(department_uid=uuid4()),
    )


async def _provision_ok(
    db: object, row: object, route: object, *, actor: object
) -> SimpleNamespace:
    return SimpleNamespace(
        ok=True,
        error=None,
        matched_department_uid=uuid4(),
        created_project_uid=uuid4(),
        created_user_uid=uuid4(),
        created_sdk_key_uid=uuid4(),
        provisioned_secrets={"sdk_key": "x", "user_token": "y", "project_code": "z"},
    )


def _fake_settings(enabled: bool) -> SimpleNamespace:
    return SimpleNamespace(
        APIREQ_ADMIN_NOTIFY_ENABLED=enabled, INITIAL_ADMIN_ACCOUNT="admin"
    )


# --- wiring / helpers --------------------------------------------------------


def _wire(
    monkeypatch: pytest.MonkeyPatch,
    *,
    enabled: bool,
    admin_email: str | None,
    admin_notify=_admin_spy,
) -> SimpleNamespace:
    global _store
    _store = _Store()

    admin = SimpleNamespace(
        pid=1,
        user_uid=uuid4(),
        account="admin",
        username="admin",
        email=admin_email,
        role="admin",
        department_uid=None,
        is_active=True,
        is_deleted=False,
        password_changed_at=None,
        sso_user_id=None,
    )
    _store.users.append(admin)

    # notify_admin_on_verdict 於 api 模組層綁定 UserRepository / get_settings / send_*;
    # require_user 於呼叫時 import app.repositories.user.UserRepository → 一併補上。
    monkeypatch.setattr(apikey_api, "UserRepository", _FakeUserRepo)
    monkeypatch.setattr(user_repo_mod, "UserRepository", _FakeUserRepo)
    monkeypatch.setattr(apikey_api, "ApiKeyRequestRepository", _FakeApiKeyRequestRepo)
    monkeypatch.setattr(apikey_api, "send_admin_notify_email", admin_notify)
    monkeypatch.setattr(apikey_api, "send_provision_email", _owner_spy)
    monkeypatch.setattr(apikey_api, "get_settings", lambda: _fake_settings(enabled))
    return admin


def _make_request(*, applicant_uid: UUID, status: str = "manual_pending") -> ApiKeyRequest:
    req = ApiKeyRequest(
        request_uid=uuid4(),
        applicant_user_uid=applicant_uid,
        department_name="資訊部",
        department_code="IT",
        project_name="智慧客服",
        project_url="https://github.com/df/demo",
        owner_name="王小明",
        owner_email="owner@df-recycle.com.tw",
        status=status,
    )
    req.created_at = datetime.now(tz=UTC)
    _store.requests[str(req.request_uid)] = req
    return req


def _make_client() -> AsyncClient:
    app = create_app()

    async def _fake_get_db() -> AsyncIterator[_FakeDb]:
        yield _FakeDb()

    app.dependency_overrides[get_db] = _fake_get_db
    app.dependency_overrides[get_openrouter_client] = lambda: SimpleNamespace()
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _session_headers(user_uid: UUID) -> dict[str, str]:
    cookie_name = real_get_settings().ACCESS_COOKIE_NAME
    return {"Cookie": f"{cookie_name}={create_access_token(user_uid)}"}


# --- ❶ 開啟 + admin 有 email → 建立判出終態後寄管理員信,收件為 admin ---------------


async def test_create_terminal_notifies_admin_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = _wire(monkeypatch, enabled=True, admin_email="admin@df-recycle.com.tw")
    monkeypatch.setattr(apikey_api.router_svc, "route", _route_system_cancel)

    async with _make_client() as client:
        resp = await client.post(
            "/api/v1/api-key-requests",
            json=_CREATE_BODY,
            headers=_session_headers(admin.user_uid),
        )

    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "cancelled"
    assert len(_store.admin_notify_calls) == 1
    call = _store.admin_notify_calls[0]
    assert call["to_email"] == "admin@df-recycle.com.tw"
    assert call["status"] == "cancelled"
    # 帶入的申請人 / 部門 / 專案取自申請單欄位
    assert call["applicant_name"] == "王小明"
    assert call["department"] == "資訊部"
    assert call["project_name"] == "智慧客服"


# --- ❷ 關閉 → 不呼叫 ----------------------------------------------------------


async def test_disabled_does_not_notify(monkeypatch: pytest.MonkeyPatch) -> None:
    admin = _wire(monkeypatch, enabled=False, admin_email="admin@df-recycle.com.tw")
    monkeypatch.setattr(apikey_api.router_svc, "route", _route_system_cancel)

    async with _make_client() as client:
        resp = await client.post(
            "/api/v1/api-key-requests",
            json=_CREATE_BODY,
            headers=_session_headers(admin.user_uid),
        )

    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "cancelled"
    assert _store.admin_notify_calls == []


# --- ❸ admin 無 email → 不呼叫、不報錯、主流程正常 ----------------------------


async def test_admin_without_email_no_notify_no_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = _wire(monkeypatch, enabled=True, admin_email=None)
    monkeypatch.setattr(apikey_api.router_svc, "route", _route_system_cancel)

    async with _make_client() as client:
        resp = await client.post(
            "/api/v1/api-key-requests",
            json=_CREATE_BODY,
            headers=_session_headers(admin.user_uid),
        )

    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "cancelled"
    assert _store.admin_notify_calls == []


# --- ❹ send_admin_notify_email 拋例外 → 主流程仍成功、申請人通知不受影響 -------


async def test_admin_notify_raises_still_succeeds_owner_unaffected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = _wire(
        monkeypatch,
        enabled=True,
        admin_email="admin@df-recycle.com.tw",
        admin_notify=_admin_raise,
    )
    monkeypatch.setattr(apikey_api.router_svc, "route", _route_ai_matched)
    monkeypatch.setattr(apikey_api.provision, "provision", _provision_ok)
    req = _make_request(applicant_uid=admin.user_uid)

    async with _make_client() as client:
        resp = await client.post(
            f"/api/v1/api-key-requests/{req.request_uid}/process",
            headers=_session_headers(admin.user_uid),
        )

    # best-effort:管理員通知拋例外被吞掉,主流程仍 200 且達 done
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "done"
    # 管理員通知確實被嘗試(且拋例外)
    assert len(_store.admin_notify_calls) == 1
    # 申請人通知不受影響:仍寄一次
    assert len(_store.owner_notify_calls) == 1


# --- ❺ 人工 process / cancel / revoke 終態各觸發一次 --------------------------


async def test_process_terminal_notifies_once(monkeypatch: pytest.MonkeyPatch) -> None:
    admin = _wire(monkeypatch, enabled=True, admin_email="admin@df-recycle.com.tw")
    monkeypatch.setattr(apikey_api.router_svc, "route", _route_ai_matched)
    monkeypatch.setattr(apikey_api.provision, "provision", _provision_ok)
    req = _make_request(applicant_uid=admin.user_uid)

    async with _make_client() as client:
        resp = await client.post(
            f"/api/v1/api-key-requests/{req.request_uid}/process",
            headers=_session_headers(admin.user_uid),
        )

    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "done"
    assert len(_store.admin_notify_calls) == 1
    assert _store.admin_notify_calls[0]["status"] == "done"


async def test_cancel_terminal_notifies_once(monkeypatch: pytest.MonkeyPatch) -> None:
    admin = _wire(monkeypatch, enabled=True, admin_email="admin@df-recycle.com.tw")
    req = _make_request(applicant_uid=admin.user_uid)

    async with _make_client() as client:
        resp = await client.post(
            f"/api/v1/api-key-requests/{req.request_uid}/cancel",
            json={"reason": "不需要了"},
            headers=_session_headers(admin.user_uid),
        )

    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "cancelled"
    assert len(_store.admin_notify_calls) == 1
    assert _store.admin_notify_calls[0]["status"] == "cancelled"


async def test_revoke_terminal_notifies_once(monkeypatch: pytest.MonkeyPatch) -> None:
    admin = _wire(monkeypatch, enabled=True, admin_email="admin@df-recycle.com.tw")
    req = _make_request(applicant_uid=admin.user_uid)

    async with _make_client() as client:
        resp = await client.post(
            f"/api/v1/api-key-requests/{req.request_uid}/revoke",
            json={"reason": "重複申請"},
            headers=_session_headers(admin.user_uid),
        )

    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "revoked"
    assert len(_store.admin_notify_calls) == 1
    assert _store.admin_notify_calls[0]["status"] == "revoked"
