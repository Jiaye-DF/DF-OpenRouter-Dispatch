"""task-406 重跑 dispatcher / 冪等守門測試。

不連 DB / Redis:以 monkeypatch 把 repo 方法、`SessionLocal`、`.kiq`、service
全部換成 in-memory stub,只驗證派發決策與冪等短路的「接線邏輯」。對齊既有
`tests/tasks/test_ai_model_eval_dispatch.py` 風格。
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
    """async with SessionLocal() as db 用的最小 stub(不連 DB);記錄 commit/rollback 次數。

    `execute` 回傳的物件帶 `scalar_one_or_none`,供 worker 短路查父評審用;預設回
    `_execute_result`(由各測試以 monkeypatch 注入 parent stub)。
    """

    def __init__(self, execute_result: object = None) -> None:
        self.commits = 0
        self.rollbacks = 0
        self._execute_result = execute_result

    async def __aenter__(self) -> _DummySession:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def execute(self, *args: object, **kwargs: object) -> object:
        return SimpleNamespace(scalar_one_or_none=lambda: self._execute_result)

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


def _patch_session(
    monkeypatch: pytest.MonkeyPatch, *, execute_result: object = None
) -> list[_DummySession]:
    """patch SessionLocal;回傳「已建立的 session」清單供斷言 commit 行為。"""
    created: list[_DummySession] = []

    def _factory() -> _DummySession:
        session = _DummySession(execute_result=execute_result)
        created.append(session)
        return session

    # 函式內以 `from app.core.database import SessionLocal` 延遲 import,故 patch 來源模組。
    monkeypatch.setattr(db_mod, "SessionLocal", _factory)
    return created


def _patch_settings(
    monkeypatch: pytest.MonkeyPatch, *, enabled: bool, batch: int = 100
) -> None:
    monkeypatch.setattr(
        mod,
        "get_settings",
        lambda: SimpleNamespace(
            AI_RERUN_ENABLED=enabled,
            AI_EVAL_DISPATCH_BATCH_SIZE=batch,
            ai_eval_start_at_dt=None,
        ),
    )


def _patch_repo_fetch(
    monkeypatch: pytest.MonkeyPatch, uids: list[UUID]
) -> dict[str, int]:
    """讓 repo.fetch_unreran_evaluation_uids 回傳給定 uids;回記呼叫次數的 dict。"""
    calls = {"fetch": 0}

    async def _fetch(self: object, limit: int, *, start_at: object = None) -> list[UUID]:
        calls["fetch"] += 1
        return uids[:limit]

    monkeypatch.setattr(
        mod.AiModelEvaluationRepository, "fetch_unreran_evaluation_uids", _fetch
    )
    return calls


def _patch_kiq(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """攔截 rerun_evaluation_task.kiq,記錄每次被派發的 uid 字串。"""
    sent: list[str] = []

    async def _kiq(uid: str) -> None:
        sent.append(uid)

    monkeypatch.setattr(mod.rerun_evaluation_task, "kiq", _kiq)
    return sent


async def test_dispatch_enabled_kiqs_n_times(monkeypatch: pytest.MonkeyPatch) -> None:
    """mock repo 回 N 筆 → .kiq 被呼叫 N 次,且 uid 為字串;回派發筆數。"""
    _patch_settings(monkeypatch, enabled=True)
    _patch_session(monkeypatch)
    _patch_repo_fetch(monkeypatch, _UIDS)
    sent = _patch_kiq(monkeypatch)

    n = await mod.dispatch_unrerun()

    assert n == len(_UIDS)
    assert sent == [str(u) for u in _UIDS]


async def test_dispatch_disabled_kiqs_zero_times(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AI_RERUN_ENABLED=false → 不撈不派,.kiq 0 次、回 0。"""
    _patch_settings(monkeypatch, enabled=False)
    _patch_session(monkeypatch)
    fetch_calls = _patch_repo_fetch(monkeypatch, _UIDS)
    sent = _patch_kiq(monkeypatch)

    n = await mod.dispatch_unrerun()

    assert n == 0
    assert sent == []
    assert fetch_calls["fetch"] == 0  # 連撈都不該發生


async def test_dispatch_empty_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    """無待重跑筆 → .kiq 0 次。"""
    _patch_settings(monkeypatch, enabled=True)
    _patch_session(monkeypatch)
    _patch_repo_fetch(monkeypatch, [])
    sent = _patch_kiq(monkeypatch)

    n = await mod.dispatch_unrerun()

    assert n == 0
    assert sent == []


async def test_worker_idempotent_shortcircuit_when_already_reran(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """父評審 ai_reran_at 非 NULL → 短路,不呼叫 rerun_evaluation service、不 commit。"""
    monkeypatch.setattr(
        mod,
        "get_settings",
        lambda: SimpleNamespace(
            OPENROUTER_API_TIMEOUT=60,
            OPENROUTER_API_BASE_URL="https://openrouter.test/api/v1",
        ),
    )
    # 父評審已重跑(ai_reran_at 非 NULL)。
    already_reran = SimpleNamespace(ai_reran_at=object())
    created = _patch_session(monkeypatch, execute_result=already_reran)

    service_calls = {"n": 0}

    async def _service(uid: UUID, *, db: object, client: object) -> None:
        service_calls["n"] += 1

    monkeypatch.setattr(mod, "rerun_evaluation", _service)

    await mod.rerun_evaluation_task(str(_UIDS[0]))

    assert service_calls["n"] == 0  # 短路:service 完全沒被呼叫
    assert created[0].commits == 0  # 短路不 commit


async def test_worker_calls_service_when_not_yet_reran(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """父評審尚未重跑(ai_reran_at 為 NULL)→ 呼叫 rerun_evaluation service 一次並 commit。"""
    monkeypatch.setattr(
        mod,
        "get_settings",
        lambda: SimpleNamespace(
            OPENROUTER_API_TIMEOUT=60,
            OPENROUTER_API_BASE_URL="https://openrouter.test/api/v1",
        ),
    )
    not_reran = SimpleNamespace(ai_reran_at=None)
    created = _patch_session(monkeypatch, execute_result=not_reran)

    seen: list[UUID] = []

    async def _service(uid: UUID, *, db: object, client: object) -> None:
        seen.append(uid)

    monkeypatch.setattr(mod, "rerun_evaluation", _service)

    await mod.rerun_evaluation_task(str(_UIDS[0]))

    assert seen == [_UIDS[0]]
    # 回歸守門:session 擁有者必須 commit,否則 service 的回寫不落地(rollback 流失)。
    assert len(created) == 1
    assert created[0].commits == 1
