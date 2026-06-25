"""task-106 dispatcher / 冪等守門測試。

不連 DB / Redis:以 monkeypatch 把 repo 方法、`SessionLocal`、`.kiq`、service
全部換成 in-memory stub,只驗證派發決策與冪等短路的「接線邏輯」。
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

import pytest

import app.core.database as db_mod
import app.tasks.ai_model_eval as mod

pytestmark = pytest.mark.asyncio

_UIDS = [
    UUID("00000000-0000-0000-0000-000000000001"),
    UUID("00000000-0000-0000-0000-000000000002"),
    UUID("00000000-0000-0000-0000-000000000003"),
]


class _DummySession:
    """async with SessionLocal() as db 用的最小 stub(不連 DB);記錄 commit/rollback 次數。"""

    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self) -> _DummySession:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


def _patch_session(monkeypatch: pytest.MonkeyPatch) -> list[_DummySession]:
    """patch SessionLocal;回傳「已建立的 session」清單供斷言 commit 行為。"""
    created: list[_DummySession] = []

    def _factory() -> _DummySession:
        session = _DummySession()
        created.append(session)
        return session

    # 函式內以 `from app.core.database import SessionLocal` 延遲 import,故 patch 來源模組。
    monkeypatch.setattr(db_mod, "SessionLocal", _factory)
    return created


def _patch_settings(monkeypatch: pytest.MonkeyPatch, *, enabled: bool, batch: int = 100) -> None:
    monkeypatch.setattr(
        mod,
        "get_settings",
        lambda: SimpleNamespace(
            AI_EVAL_ENABLED=enabled,
            AI_EVAL_DISPATCH_BATCH_SIZE=batch,
        ),
    )


def _patch_repo_fetch(monkeypatch: pytest.MonkeyPatch, uids: list[UUID]) -> dict[str, int]:
    """讓 repo.fetch_unevaluated_log_uids 回傳給定 uids;回記呼叫次數的 dict。"""
    calls = {"fetch": 0}

    async def _fetch(self: object, limit: int) -> list[UUID]:
        calls["fetch"] += 1
        return uids[:limit]

    monkeypatch.setattr(
        mod.AiModelEvaluationRepository, "fetch_unevaluated_log_uids", _fetch
    )
    return calls


def _patch_kiq(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """攔截 evaluate_usage_log_task.kiq,記錄每次被派發的 uid 字串。"""
    sent: list[str] = []

    async def _kiq(uid: str) -> None:
        sent.append(uid)

    monkeypatch.setattr(mod.evaluate_usage_log_task, "kiq", _kiq)
    return sent


async def test_dispatch_enabled_kiqs_n_times(monkeypatch: pytest.MonkeyPatch) -> None:
    """mock repo 回 N 筆 → .kiq 被呼叫 N 次,且 uid 為字串。"""
    _patch_settings(monkeypatch, enabled=True)
    _patch_session(monkeypatch)
    _patch_repo_fetch(monkeypatch, _UIDS)
    sent = _patch_kiq(monkeypatch)

    n = await mod.dispatch_unevaluated()

    assert n == len(_UIDS)
    assert sent == [str(u) for u in _UIDS]


async def test_dispatch_disabled_kiqs_zero_times(monkeypatch: pytest.MonkeyPatch) -> None:
    """AI_EVAL_ENABLED=false → 不撈不派,.kiq 0 次。"""
    _patch_settings(monkeypatch, enabled=False)
    _patch_session(monkeypatch)
    fetch_calls = _patch_repo_fetch(monkeypatch, _UIDS)
    sent = _patch_kiq(monkeypatch)

    n = await mod.dispatch_unevaluated()

    assert n == 0
    assert sent == []
    assert fetch_calls["fetch"] == 0  # 連撈都不該發生


async def test_dispatch_empty_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    """無待評審筆 → .kiq 0 次。"""
    _patch_settings(monkeypatch, enabled=True)
    _patch_session(monkeypatch)
    _patch_repo_fetch(monkeypatch, [])
    sent = _patch_kiq(monkeypatch)

    n = await mod.dispatch_unevaluated()

    assert n == 0
    assert sent == []


async def test_worker_idempotent_shortcircuit_when_parent_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """重複派發同一 uid:父表已存在 → 短路,不呼叫 evaluate_usage_log service。"""
    monkeypatch.setattr(
        mod,
        "get_settings",
        lambda: SimpleNamespace(
            OPENROUTER_API_TIMEOUT=60,
            OPENROUTER_API_BASE_URL="https://openrouter.test/api/v1",
        ),
    )
    _patch_session(monkeypatch)

    async def _existing(self: object, uid: UUID) -> object:
        return object()  # 父表已存在

    monkeypatch.setattr(
        mod.AiModelEvaluationRepository,
        "find_by_usage_log_uid_including_deleted",
        _existing,
    )

    service_calls = {"n": 0}

    async def _service(uid: UUID, *, db: object, client: object) -> None:
        service_calls["n"] += 1

    monkeypatch.setattr(mod, "evaluate_usage_log", _service)

    await mod.evaluate_usage_log_task(str(_UIDS[0]))

    assert service_calls["n"] == 0  # 短路:service 完全沒被呼叫


async def test_worker_calls_service_when_parent_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """父表不存在 → 呼叫 evaluate_usage_log service 一次(以 mock service 斷言)。"""
    monkeypatch.setattr(
        mod,
        "get_settings",
        lambda: SimpleNamespace(
            OPENROUTER_API_TIMEOUT=60,
            OPENROUTER_API_BASE_URL="https://openrouter.test/api/v1",
        ),
    )
    created = _patch_session(monkeypatch)

    async def _absent(self: object, uid: UUID) -> object | None:
        return None

    monkeypatch.setattr(
        mod.AiModelEvaluationRepository,
        "find_by_usage_log_uid_including_deleted",
        _absent,
    )

    seen: list[UUID] = []

    async def _service(uid: UUID, *, db: object, client: object) -> None:
        seen.append(uid)

    monkeypatch.setattr(mod, "evaluate_usage_log", _service)

    await mod.evaluate_usage_log_task(str(_UIDS[0]))

    assert seen == [_UIDS[0]]
    # 回歸守門:session 擁有者必須 commit,否則 service 的回寫不落地(rollback 流失)。
    assert len(created) == 1
    assert created[0].commits == 1
