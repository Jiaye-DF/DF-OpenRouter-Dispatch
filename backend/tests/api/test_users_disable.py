"""使用者停用/啟用(task-436)測試:停用即 revoke_tokens("user_disabled") + 不可停用自己。

沿用本專案 mock 風格(見 tests/api/test_usage_logs.py):
- FastAPI app + httpx.AsyncClient(ASGITransport),get_db 覆寫為假 AsyncSession。
- repository 層以共享 in-memory store 的替身取代(monkeypatch 到各使用點:
  api/service 模組層綁定 + repositories 模組供 require_user / resolve_sdk_caller 的區域 import)。
- service(user_token / auth)與驗證鏈(require_user / resolve_sdk_caller)走**真實程式碼**,
  驗證停用 → 雙表撤銷(user_tokens 標記 + user_tokens_revocations 浮水印)與 401 行為。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.sdk_auth import resolve_sdk_caller
from app.core.security import create_access_token, hash_password
from app.main import create_app
from app.models.audit_log import AuditLog
from app.models.user_token import UserToken
from app.models.user_token_revocation import UserTokenRevocation
from app.schemas.actor import SdkCallerContext
from app.services import user_token as user_token_service

pytestmark = pytest.mark.asyncio

_PASSWORD = "Member#Pass2026!"
_PASSWORD_HASH = hash_password(_PASSWORD)
_SDK_KEY_PREFIX = "ordsk_" + "a" * 12
_SDK_KEY_RAW = _SDK_KEY_PREFIX + "_" + "s" * 32
_SDK_KEY_HASH = hash_password(_SDK_KEY_RAW)  # argon2,與 sdk_auth 的 PasswordHasher 相容
_PROJECT_CODE = "PRJ-TEST"


# --- in-memory store(模擬兩張 token 表 + users / 稽核等) ---


@dataclass
class _Store:
    users: list[SimpleNamespace] = field(default_factory=list)
    tokens: list[UserToken] = field(default_factory=list)
    revocations: list[UserTokenRevocation] = field(default_factory=list)
    audits: list[AuditLog] = field(default_factory=list)
    refresh_tokens: list[object] = field(default_factory=list)
    departments: list[SimpleNamespace] = field(default_factory=list)
    sdk_keys: list[SimpleNamespace] = field(default_factory=list)
    projects: list[SimpleNamespace] = field(default_factory=list)


_store = _Store()


class _FakeDb:
    """假 AsyncSession:寫入面只需承接 write_audit 的 db.add(AuditLog)。"""

    def add(self, row: object) -> None:
        if isinstance(row, AuditLog):
            _store.audits.append(row)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


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

    async def list_for_dropdown(
        self, *, department_uid: UUID | None = None, limit: int = 2000
    ) -> list[SimpleNamespace]:
        """供 /users/dropdown(session 存活驗證用端點)。"""
        rows = [u for u in _store.users if not u.is_deleted and u.is_active]
        if department_uid is not None:
            rows = [u for u in rows if u.department_uid == department_uid]
        return rows[:limit]


class _FakeUserTokenRepo:
    def __init__(self, db: object) -> None:
        self.db = db

    async def get_active_by_user(self, user_uid: UUID) -> UserToken | None:
        rows = [
            r
            for r in _store.tokens
            if r.user_uid == user_uid and r.revoked_at is None and not r.is_deleted
        ]
        rows.sort(key=lambda r: r.issued_at, reverse=True)
        return rows[0] if rows else None

    async def get_by_user_and_token(self, user_uid: UUID, token: str) -> UserToken | None:
        for r in _store.tokens:
            if r.user_uid == user_uid and r.token == token and not r.is_deleted:
                return r
        return None

    def add(self, row: UserToken) -> None:
        _store.tokens.append(row)

    async def revoke_active_by_user(
        self, user_uid: UUID, now: datetime, reason: str | None
    ) -> None:
        for r in _store.tokens:
            if r.user_uid == user_uid and r.revoked_at is None and not r.is_deleted:
                r.revoked_at = now
                r.revoked_reason = reason
                r.is_active = False


class _FakeUserTokenRevocationRepo:
    def __init__(self, db: object) -> None:
        self.db = db

    async def latest_for_user(self, user_uid: UUID) -> UserTokenRevocation | None:
        rows = [r for r in _store.revocations if r.user_uid == user_uid and not r.is_deleted]
        rows.sort(key=lambda r: r.revoked_issued_at, reverse=True)
        return rows[0] if rows else None

    def add(self, row: UserTokenRevocation) -> None:
        _store.revocations.append(row)


class _FakeDepartmentRepo:
    def __init__(self, db: object) -> None:
        self.db = db

    async def get_by_uid(self, department_uid: UUID) -> SimpleNamespace | None:
        for d in _store.departments:
            if d.department_uid == department_uid and not d.is_deleted:
                return d
        return None


class _FakeSdkApiKeyRepo:
    def __init__(self, db: object) -> None:
        self.db = db

    async def list_active_by_prefix(self, prefix: str) -> list[SimpleNamespace]:
        return [k for k in _store.sdk_keys if k.key_prefix == prefix]


class _FakeProjectRepo:
    def __init__(self, db: object) -> None:
        self.db = db

    async def get_active_by_code_and_dept(
        self, code: str, department_uid: UUID
    ) -> SimpleNamespace | None:
        for p in _store.projects:
            if p.code == code and p.department_uid == department_uid:
                return p
        return None


class _FakeRefreshTokenRepo:
    def __init__(self, db: object) -> None:
        self.db = db

    def add(self, row: object) -> None:
        _store.refresh_tokens.append(row)


# --- fixtures / helpers ---


def _make_user(
    *,
    account: str,
    role: str = "user",
    department_uid: UUID | None = None,
    email: str | None = None,
    employee_id: str | None = None,
) -> SimpleNamespace:
    u = SimpleNamespace(
        pid=len(_store.users) + 1,
        user_uid=uuid4(),
        account=account,
        username=account,
        password_hash=_PASSWORD_HASH,
        role=role,
        department_uid=department_uid,
        employee_id=employee_id,
        email=email,
        sso_user_id=None,
        is_active=True,
        is_deleted=False,
        failed_login_count=0,
        locked_until=None,
        password_changed_at=None,
    )
    _store.users.append(u)
    return u


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    global _store
    _store = _Store()

    import app.api.v1.users as users_api
    import app.repositories.project as project_repo_mod
    import app.repositories.sdk_api_key as sdk_key_repo_mod
    import app.repositories.user as user_repo_mod
    import app.repositories.user_token as user_token_repo_mod
    import app.repositories.user_token_revocation as rev_repo_mod
    import app.services.auth as auth_service_mod

    # api / service 模組層已綁定的名稱
    monkeypatch.setattr(users_api, "UserRepository", _FakeUserRepo)
    monkeypatch.setattr(user_token_service, "UserRepository", _FakeUserRepo)
    monkeypatch.setattr(user_token_service, "DepartmentRepository", _FakeDepartmentRepo)
    monkeypatch.setattr(user_token_service, "UserTokenRepository", _FakeUserTokenRepo)
    monkeypatch.setattr(
        user_token_service, "UserTokenRevocationRepository", _FakeUserTokenRevocationRepo
    )
    monkeypatch.setattr(auth_service_mod, "UserRepository", _FakeUserRepo)
    monkeypatch.setattr(auth_service_mod, "RefreshTokenRepository", _FakeRefreshTokenRepo)
    # require_user / resolve_sdk_caller 於呼叫時才 import → 補 repositories 模組層
    monkeypatch.setattr(user_repo_mod, "UserRepository", _FakeUserRepo)
    monkeypatch.setattr(user_token_repo_mod, "UserTokenRepository", _FakeUserTokenRepo)
    monkeypatch.setattr(rev_repo_mod, "UserTokenRevocationRepository", _FakeUserTokenRevocationRepo)
    monkeypatch.setattr(sdk_key_repo_mod, "SdkApiKeyRepository", _FakeSdkApiKeyRepo)
    monkeypatch.setattr(project_repo_mod, "ProjectRepository", _FakeProjectRepo)

    dept_uid = uuid4()
    _store.departments.append(
        SimpleNamespace(department_uid=dept_uid, code="RD", is_deleted=False)
    )
    _store.sdk_keys.append(
        SimpleNamespace(
            sdk_api_key_uid=uuid4(),
            department_uid=dept_uid,
            key_prefix=_SDK_KEY_PREFIX,
            key_hash=_SDK_KEY_HASH,
        )
    )
    _store.projects.append(
        SimpleNamespace(project_uid=uuid4(), code=_PROJECT_CODE, department_uid=dept_uid)
    )
    admin = _make_user(account="admin.boss", role="admin", department_uid=dept_uid)
    member = _make_user(
        account="member.one",
        role="user",
        department_uid=dept_uid,
        email="member.one@df-recycle.com.tw",
        employee_id="E001",
    )
    return SimpleNamespace(dept_uid=dept_uid, admin=admin, member=member)


def _make_client() -> AsyncClient:
    app = create_app()

    async def _fake_get_db():
        yield _FakeDb()

    app.dependency_overrides[get_db] = _fake_get_db
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _session_headers(user_uid: UUID) -> dict[str, str]:
    cookie_name = get_settings().ACCESS_COOKIE_NAME
    return {"Cookie": f"{cookie_name}={create_access_token(user_uid)}"}


async def _issue_member_token(member: SimpleNamespace) -> str:
    token, _issued_at = await user_token_service.get_or_create_token(
        _FakeDb(),  # type: ignore[arg-type]
        user_uid=member.user_uid,
    )
    return token


async def _sdk_resolve(token: str) -> SdkCallerContext:
    return await resolve_sdk_caller(
        _FakeDb(),  # type: ignore[arg-type]
        _SDK_KEY_RAW,
        token,
        _PROJECT_CODE,
    )


async def _patch_is_active(
    client: AsyncClient, actor_uid: UUID, target_uid: UUID, value: bool
):
    return await client.patch(
        f"/api/v1/users/{target_uid}",
        json={"is_active": value},
        headers=_session_headers(actor_uid),
    )


# --- 停用 → 雙表撤銷 ---


async def test_disable_revokes_tokens_in_both_tables(world: SimpleNamespace):
    token = await _issue_member_token(world.member)
    async with _make_client() as client:
        resp = await _patch_is_active(
            client, world.admin.user_uid, world.member.user_uid, False
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["is_active"] is False
    assert body["data"]["tokens_revoked"] is True
    # user_tokens:落地 token 標記撤銷
    assert len(_store.tokens) == 1
    row = _store.tokens[0]
    assert row.token == token
    assert row.revoked_at is not None
    assert row.revoked_reason == "user_disabled"
    # user_tokens_revocations:新增浮水印
    assert len(_store.revocations) == 1
    rev = _store.revocations[0]
    assert rev.user_uid == world.member.user_uid
    assert rev.reason == "user_disabled"


async def test_disabled_user_sdk_call_returns_401(world: SimpleNamespace):
    token = await _issue_member_token(world.member)
    ctx = await _sdk_resolve(token)  # 停用前可正常通過驗證鏈
    assert ctx.user_uid == world.member.user_uid
    async with _make_client() as client:
        resp = await _patch_is_active(
            client, world.admin.user_uid, world.member.user_uid, False
        )
    assert resp.status_code == 200, resp.text
    with pytest.raises(AppError) as exc_info:
        await _sdk_resolve(token)
    assert exc_info.value.code == 401


# --- 停用 → 擋登入 / 既有 session 失效 ---


async def test_disabled_user_login_and_existing_session_401(world: SimpleNamespace):
    cookie_name = get_settings().ACCESS_COOKIE_NAME
    login_body = {"account": world.member.account, "password": _PASSWORD}
    async with _make_client() as member_client, _make_client() as admin_client:
        login = await member_client.post("/api/v1/auth/login", json=login_body)
        assert login.status_code == 200, login.text
        assert login.cookies.get(cookie_name)
        ok = await member_client.get("/api/v1/users/dropdown")
        assert ok.status_code == 200, ok.text

        resp = await _patch_is_active(
            admin_client, world.admin.user_uid, world.member.user_uid, False
        )
        assert resp.status_code == 200, resp.text

        # 既有 session 下一請求即被踢(require_user 檢查 is_active)
        kicked = await member_client.get("/api/v1/users/dropdown")
        assert kicked.status_code == 401
        # 停用後本地登入被擋
        relogin = await admin_client.post("/api/v1/auth/login", json=login_body)
        assert relogin.status_code == 401


# --- 重新啟用:不復活 token、可重發、可登入 ---


async def test_reenable_does_not_revive_tokens_but_allows_reissue(world: SimpleNamespace):
    stored_token = await _issue_member_token(world.member)
    # 已發出、未落地的舊 token(浮水印回退路徑)
    unstored_token, _ = await user_token_service.generate_token(
        _FakeDb(),  # type: ignore[arg-type]
        user_uid=world.member.user_uid,
    )
    assert (await _sdk_resolve(unstored_token)).user_uid == world.member.user_uid

    async with _make_client() as client:
        resp = await _patch_is_active(
            client, world.admin.user_uid, world.member.user_uid, False
        )
        assert resp.status_code == 200, resp.text

        resp = await _patch_is_active(
            client, world.admin.user_uid, world.member.user_uid, True
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["data"]["is_active"] is True
        # 重新啟用不觸發任何 token 動作
        assert body["data"]["tokens_revoked"] is False
        assert len(_store.revocations) == 1

        # 原 token(落地 / 未落地)皆不復活
        for old in (stored_token, unstored_token):
            with pytest.raises(AppError) as exc_info:
                await _sdk_resolve(old)
            assert exc_info.value.code == 401

        # get_or_create_token 可重發新 token,且新 token 通過驗證鏈
        reissue = await client.post(
            f"/api/v1/users/{world.member.user_uid}/tokens",
            headers=_session_headers(world.admin.user_uid),
        )
        assert reissue.status_code == 200, reissue.text
        new_token = reissue.json()["data"]["token"]
        assert new_token != stored_token
        ctx = await _sdk_resolve(new_token)
        assert ctx.user_uid == world.member.user_uid

        # 重新啟用後可登入
        relogin = await client.post(
            "/api/v1/auth/login",
            json={"account": world.member.account, "password": _PASSWORD},
        )
        assert relogin.status_code == 200, relogin.text


# --- 停用中產 token → 404(現況 generate_token 擋下) ---


async def test_disabled_user_generate_token_returns_404(world: SimpleNamespace):
    async with _make_client() as client:
        resp = await _patch_is_active(
            client, world.admin.user_uid, world.member.user_uid, False
        )
        assert resp.status_code == 200, resp.text
        gen = await client.post(
            f"/api/v1/users/{world.member.user_uid}/tokens",
            headers=_session_headers(world.admin.user_uid),
        )
    assert gen.status_code == 404
    assert gen.json() == {
        "success": False,
        "code": 404,
        "data": None,
        "detail": "not_found",
    }


# --- 不可停用自己(400)/ 不存在使用者(404) ---


async def test_admin_cannot_disable_self_returns_400(world: SimpleNamespace):
    async with _make_client() as client:
        resp = await _patch_is_active(
            client, world.admin.user_uid, world.admin.user_uid, False
        )
        assert resp.status_code == 400
        assert resp.json() == {
            "success": False,
            "code": 400,
            "data": None,
            "detail": "cannot_disable_self",
        }
        # 未觸發撤銷、未寫 update_user 稽核、admin 仍啟用
        assert _store.revocations == []
        assert [a for a in _store.audits if a.action == "update_user"] == []
        assert world.admin.is_active is True

        # 僅擋「停用」:對自己送 is_active=true 不受影響
        resp = await _patch_is_active(
            client, world.admin.user_uid, world.admin.user_uid, True
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["tokens_revoked"] is False


async def test_disable_missing_user_returns_404(world: SimpleNamespace):
    async with _make_client() as client:
        resp = await _patch_is_active(client, world.admin.user_uid, uuid4(), False)
    assert resp.status_code == 404


# --- 重複停用冪等 ---


async def test_repeat_disable_is_idempotent(world: SimpleNamespace):
    await _issue_member_token(world.member)
    async with _make_client() as client:
        first = await _patch_is_active(
            client, world.admin.user_uid, world.member.user_uid, False
        )
        assert first.status_code == 200, first.text
        assert first.json()["data"]["tokens_revoked"] is True
        revoked_at = _store.tokens[0].revoked_at
        assert len(_store.revocations) == 1

        second = await _patch_is_active(
            client, world.admin.user_uid, world.member.user_uid, False
        )
        assert second.status_code == 200, second.text
        body = second.json()
        assert body["data"]["is_active"] is False
        # 不重複撤銷:旗標 False、浮水印不增生、原標記不變
        assert body["data"]["tokens_revoked"] is False
        assert len(_store.revocations) == 1
        assert _store.tokens[0].revoked_at == revoked_at
        assert _store.tokens[0].revoked_reason == "user_disabled"


# --- 稽核:沿用 update_user,extra 含 is_active + tokens_revoked ---


async def test_audit_extra_reflects_disable_and_enable(world: SimpleNamespace):
    await _issue_member_token(world.member)
    async with _make_client() as client:
        resp = await _patch_is_active(
            client, world.admin.user_uid, world.member.user_uid, False
        )
        assert resp.status_code == 200, resp.text
        resp = await _patch_is_active(
            client, world.admin.user_uid, world.member.user_uid, True
        )
        assert resp.status_code == 200, resp.text

    audits = [a for a in _store.audits if a.action == "update_user"]
    assert len(audits) == 2
    disable_audit, enable_audit = audits
    for a in audits:
        assert a.actor_user_uid == world.admin.user_uid
        assert a.actor_role == "admin"
        assert a.target_type == "user"
        assert a.target_uid == world.member.user_uid
    assert disable_audit.extra == {"is_active": False, "tokens_revoked": True}
    assert enable_audit.extra == {"is_active": True, "tokens_revoked": False}


# --- NOT NULL 欄位顯式送 null:400,不可打穿 DB 約束變成 500 ---


@pytest.mark.parametrize("field", ["is_active", "username", "role"])
async def test_patch_explicit_null_on_not_null_field_returns_400(
    world: SimpleNamespace, field: str
):
    """回歸:`bool | None` 等 Optional 欄位的 None 語意是「未提供」,非「設為 NULL」。

    顯式 null 過去會被 exclude_unset 保留 → setattr(user, k, None) → flush 時
    IntegrityError → 500。應於 schema 層擋成 400。
    """
    async with _make_client() as client:
        resp = await client.patch(
            f"/api/v1/users/{world.member.user_uid}",
            json={field: None},
            headers=_session_headers(world.admin.user_uid),
        )
    assert resp.status_code == 400, resp.text
    assert resp.json()["success"] is False
    assert field in resp.json()["detail"]


async def test_patch_omitting_field_still_means_no_change(world: SimpleNamespace):
    """省略欄位(而非送 null)仍是「不更動」——擋 null 不得誤傷正常的部分更新。"""
    async with _make_client() as client:
        resp = await client.patch(
            f"/api/v1/users/{world.member.user_uid}",
            json={"employee_id": "E999"},
            headers=_session_headers(world.admin.user_uid),
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["is_active"] is True
    assert resp.json()["data"]["employee_id"] == "E999"
