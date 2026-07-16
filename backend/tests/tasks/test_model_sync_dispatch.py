"""task-502 排程同步派發 / 短路測試。

不連 DB / Redis / OpenRouter:以 monkeypatch 把 `SessionLocal`、
`UserRepository.get_by_account`、`sync_models_and_credits` 全部換成 in-memory
stub,只驗證「啟用短路 / 系統 actor 解析 / 節流靜默略過」的接線邏輯。
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

import pytest

import app.core.database as db_mod
import app.tasks.model_sync as mod
from app.core.exceptions import AppError

pytestmark = pytest.mark.asyncio

_ADMIN_UID = UUID("00000000-0000-0000-0000-0000000000aa")


class _DummySession:
    """async with SessionLocal() as db 用的最小 stub(不連 DB)。"""

    def __init__(self) -> None:
        self.commits = 0

    async def __aenter__(self) -> _DummySession:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1


def _patch_session(monkeypatch: pytest.MonkeyPatch) -> list[_DummySession]:
    created: list[_DummySession] = []

    def _factory() -> _DummySession:
        session = _DummySession()
        created.append(session)
        return session

    # 函式內以 `from app.core.database import SessionLocal` 延遲 import,故 patch 來源模組。
    monkeypatch.setattr(db_mod, "SessionLocal", _factory)
    return created


def _patch_settings(monkeypatch: pytest.MonkeyPatch, *, enabled: bool) -> None:
    monkeypatch.setattr(
        mod,
        "get_settings",
        lambda: SimpleNamespace(
            MODEL_SYNC_SCHEDULE_ENABLED=enabled,
            INITIAL_ADMIN_ACCOUNT="admin",
            OPENROUTER_API_TIMEOUT=60,
            OPENROUTER_API_BASE_URL="https://openrouter.test/api/v1",
        ),
    )


def _patch_admin(monkeypatch: pytest.MonkeyPatch, *, found: bool) -> None:
    """讓 UserRepository.get_by_account 回傳 admin(或 None)。"""
    admin = (
        SimpleNamespace(user_uid=_ADMIN_UID, role="admin", email="a@b.c") if found else None
    )

    async def _get(self: object, account: str) -> object | None:
        return admin

    monkeypatch.setattr(mod.UserRepository, "get_by_account", _get)


def _patch_sync(
    monkeypatch: pytest.MonkeyPatch, *, raises: Exception | None = None
) -> list[dict[str, object]]:
    """攔截 sync_models_and_credits;記錄每次被呼叫的 kwargs。"""
    calls: list[dict[str, object]] = []

    async def _sync(db: object, client: object, **kwargs: object) -> object:
        calls.append(kwargs)
        if raises is not None:
            raise raises
        return object()

    monkeypatch.setattr(mod, "sync_models_and_credits", _sync)
    return calls


async def test_disabled_does_not_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    """MODEL_SYNC_SCHEDULE_ENABLED=false → 不建 session、不呼叫同步。"""
    _patch_settings(monkeypatch, enabled=False)
    created = _patch_session(monkeypatch)
    _patch_admin(monkeypatch, found=True)
    calls = _patch_sync(monkeypatch)

    await mod.scheduled_sync_models()

    assert calls == []
    assert created == []  # 短路發生在建 session 之前


async def test_enabled_with_admin_syncs_once_with_trigger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """enable=true 且 admin 存在 → 呼叫一次,帶 audit_meta={"trigger":"scheduler"}。"""
    _patch_settings(monkeypatch, enabled=True)
    _patch_session(monkeypatch)
    _patch_admin(monkeypatch, found=True)
    calls = _patch_sync(monkeypatch)

    await mod.scheduled_sync_models()

    assert len(calls) == 1
    kwargs = calls[0]
    assert kwargs["actor_user_uid"] == _ADMIN_UID
    assert kwargs["actor_role"] == "admin"
    assert kwargs["ip"] is None
    assert kwargs["audit_meta"] == {"trigger": "scheduler"}


async def test_sync_throttled_is_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    """sync 拋 AppError('sync_throttled') → 任務不 re-raise(靜默略過)。"""
    _patch_settings(monkeypatch, enabled=True)
    _patch_session(monkeypatch)
    _patch_admin(monkeypatch, found=True)
    calls = _patch_sync(monkeypatch, raises=AppError("sync_throttled", code=425))

    # 不應冒出例外
    await mod.scheduled_sync_models()

    assert len(calls) == 1  # 有嘗試同步,但節流被靜默吞掉


async def test_missing_admin_does_not_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    """admin 查無 → 不呼叫同步。"""
    _patch_settings(monkeypatch, enabled=True)
    _patch_session(monkeypatch)
    _patch_admin(monkeypatch, found=False)
    calls = _patch_sync(monkeypatch)

    await mod.scheduled_sync_models()

    assert calls == []
