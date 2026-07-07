"""stats/by-project-model 端點測試(對齊 docs/Tasks/v2.1/tasks/task-420-stats-by-project-model.md Acceptance)。

沿用本專案 mock 風格(見 tests/api/test_ai_eval.py):
- FastAPI app + httpx.AsyncClient(ASGITransport)。
- dependency_overrides 覆寫 require_user(假 Actor)與 get_db(假 AsyncSession)。
- monkeypatch stats 模組內 UsageLogRepository 為可控假物件,捕捉傳入 repo 的篩選參數。
不連真 DB。
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

import app.api.v1.stats as stats
from app.core.database import get_db
from app.core.deps import require_user
from app.main import create_app
from app.schemas.actor import Actor

pytestmark = pytest.mark.asyncio


class _FakeRepo:
    """stats.UsageLogRepository 替身;捕捉呼叫參數、回傳預設列。"""

    last_kwargs: dict | None = None
    rows: list[tuple] = []

    def __init__(self, db) -> None:
        self.db = db

    async def by_project_model(self, **kwargs):
        type(self).last_kwargs = kwargs
        return type(self).rows


class _FakeDb:
    async def flush(self):
        return None

    async def commit(self):
        return None

    async def rollback(self):
        return None

    def add(self, row):
        return None


def _admin() -> Actor:
    return Actor(user_uid=uuid4(), account="admin", username="管理員", role="admin")


def _member(dept: UUID) -> Actor:
    return Actor(
        user_uid=uuid4(),
        account="u",
        username="一般使用者",
        role="user",
        department_uid=dept,
    )


def _make_client(monkeypatch, actor: Actor, rows: list[tuple]):
    _FakeRepo.rows = rows
    _FakeRepo.last_kwargs = None
    monkeypatch.setattr(stats, "UsageLogRepository", _FakeRepo)

    app = create_app()

    async def _fake_get_db():
        yield _FakeDb()

    app.dependency_overrides[get_db] = _fake_get_db
    app.dependency_overrides[require_user] = lambda: actor

    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


def _sample_rows() -> list[tuple]:
    p1 = uuid4()
    p2 = uuid4()
    return [
        (p1, "PRJ-A", "專案A", "openai/gpt-4o", 10, 1000, Decimal("1.500000")),
        (p1, "PRJ-A", "專案A", "anthropic/claude-3.5", 4, 400, Decimal("0.750000")),
        (p2, "PRJ-B", "專案B", "openai/gpt-4o", 2, 200, Decimal("0.250000")),
    ]


async def test_openapi_has_by_project_model_get(monkeypatch):
    async with _make_client(monkeypatch, _admin(), []) as client:
        resp = await client.get("/api/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    assert "/api/v1/stats/by-project-model" in paths
    assert "get" in paths["/api/v1/stats/by-project-model"]


async def test_admin_gets_all_no_dept_lock(monkeypatch):
    admin = _admin()
    rows = _sample_rows()
    async with _make_client(monkeypatch, admin, rows) as client:
        resp = await client.get("/api/v1/stats/by-project-model")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["code"] == 200
    assert len(body["data"]) == 3
    first = body["data"][0]
    assert set(first.keys()) == {
        "project_uid",
        "project_code",
        "project_name",
        "model",
        "total_requests",
        "total_tokens",
        "total_cost_usd",
    }
    assert first["project_code"] == "PRJ-A"
    assert first["total_cost_usd"] == "1.500000"
    # admin 不鎖部門:未傳 department_uid → repo 收到 None
    assert _FakeRepo.last_kwargs is not None
    assert _FakeRepo.last_kwargs["department_uid"] is None


async def test_non_admin_other_department_returns_403(monkeypatch):
    member = _member(uuid4())
    other_dept = uuid4()
    async with _make_client(monkeypatch, member, []) as client:
        resp = await client.get(
            f"/api/v1/stats/by-project-model?department_uid={other_dept}"
        )
    assert resp.status_code == 403


async def test_non_admin_no_department_locks_actor_dept(monkeypatch):
    dept = uuid4()
    member = _member(dept)
    async with _make_client(monkeypatch, member, _sample_rows()) as client:
        resp = await client.get("/api/v1/stats/by-project-model")
    assert resp.status_code == 200, resp.text
    # 非-admin 未傳部門 → 自動鎖 actor.department_uid
    assert _FakeRepo.last_kwargs is not None
    assert _FakeRepo.last_kwargs["department_uid"] == dept


async def test_no_data_returns_empty_list(monkeypatch):
    async with _make_client(monkeypatch, _admin(), []) as client:
        resp = await client.get("/api/v1/stats/by-project-model")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"] == []
