"""usage-logs 列表 + 明細授權放寬/部門鎖/專案欄位測試(對齊 task-421 Acceptance)。

沿用本專案 mock 風格(見 tests/api/test_stats.py):
- FastAPI app + httpx.AsyncClient(ASGITransport)。
- dependency_overrides 覆寫 require_user(假 Actor)與 get_db(假 AsyncSession)。
- monkeypatch usage_logs 模組內 UsageLogRepository 為可控假物件,捕捉傳入的篩選參數。
不連真 DB(repo 回傳 (UsageLog-like, project_code, project_name) tuple 由 router 組 schema)。
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

import app.api.v1.usage_logs as usage_logs
from app.core.database import get_db
from app.core.deps import require_user
from app.main import create_app
from app.schemas.actor import Actor
from app.schemas.usage_log import UsageLogListItem

pytestmark = pytest.mark.asyncio


class _FakeRepo:
    """usage_logs.UsageLogRepository 替身;捕捉 list 參數、回傳預設列 / 明細。"""

    list_rows: list[tuple] = []
    list_total: int = 0
    detail_row: tuple | None = None
    last_list_kwargs: dict | None = None

    def __init__(self, db) -> None:
        self.db = db

    async def list(self, **kwargs):
        type(self).last_list_kwargs = kwargs
        return type(self).list_rows, type(self).list_total

    async def get_by_uid_with_project(self, uid):
        return type(self).detail_row


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


def _fake_log(*, department_uid: UUID | None, project_uid: UUID | None = None, **over):
    """回傳有 UsageLog 全欄位的 SimpleNamespace,供 model_validate(from_attributes) 讀。"""
    base = dict(
        pid=1,
        usage_log_uid=uuid4(),
        user_uid=uuid4(),
        department_uid=department_uid,
        project_uid=project_uid,
        openrouter_key_uid=None,
        model="openai/gpt-4o",
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        cost_usd=Decimal("0.001500"),
        latency_ms=123,
        status="success",
        error_code=None,
        used_tools=False,
        openrouter_generation_id=None,
        created_at=datetime(2026, 7, 7, 12, 0, 0, tzinfo=UTC),
        request_content={"messages": []},
        response_summary={"text": "ok"},
    )
    base.update(over)
    return SimpleNamespace(**base)


def _make_client(
    monkeypatch,
    actor: Actor,
    *,
    list_rows: list[tuple] | None = None,
    list_total: int = 0,
    detail_row: tuple | None = None,
):
    _FakeRepo.list_rows = list_rows or []
    _FakeRepo.list_total = list_total
    _FakeRepo.detail_row = detail_row
    _FakeRepo.last_list_kwargs = None
    monkeypatch.setattr(usage_logs, "UsageLogRepository", _FakeRepo)

    app = create_app()

    async def _fake_get_db():
        yield _FakeDb()

    app.dependency_overrides[get_db] = _fake_get_db
    app.dependency_overrides[require_user] = lambda: actor

    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


# --- OpenAPI / schema 契約 ---


async def test_openapi_list_has_project_uid_query_param(monkeypatch):
    async with _make_client(monkeypatch, _admin()) as client:
        resp = await client.get("/api/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    assert "/api/v1/usage-logs" in paths
    get_op = paths["/api/v1/usage-logs"]["get"]
    param_names = {p["name"] for p in get_op.get("parameters", [])}
    assert "project_uid" in param_names


async def test_response_schema_has_project_code():
    # endpoint 以 success_response 回統一殼、無 response_model,故對 schema 本體斷言:
    # 回應列項 UsageLogListItem 含 project_code / project_name / project_uid。
    assert "project_code" in UsageLogListItem.model_fields
    assert "project_name" in UsageLogListItem.model_fields
    assert "project_uid" in UsageLogListItem.model_fields


# --- 列表 ---


async def test_admin_list_unchanged_and_includes_project_columns(monkeypatch):
    admin = _admin()
    p1 = uuid4()
    rows = [
        (_fake_log(department_uid=uuid4(), project_uid=p1), "PRJ-A", "專案A"),
        # 歷史 project_uid IS NULL 的列:仍出現,專案三欄皆 None。
        (_fake_log(department_uid=uuid4(), project_uid=None), None, None),
    ]
    async with _make_client(monkeypatch, admin, list_rows=rows, list_total=2) as client:
        resp = await client.get("/api/v1/usage-logs")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["code"] == 200
    items = body["data"]["items"]
    assert len(items) == 2
    # 第一列帶專案三欄
    assert items[0]["project_uid"] == str(p1)
    assert items[0]["project_code"] == "PRJ-A"
    assert items[0]["project_name"] == "專案A"
    # NULL 專案列仍現、三欄為 null
    assert items[1]["project_uid"] is None
    assert items[1]["project_code"] is None
    assert items[1]["project_name"] is None
    # admin 不鎖部門:未傳 department_uid → repo 收到 None
    assert _FakeRepo.last_list_kwargs is not None
    assert _FakeRepo.last_list_kwargs["department_uid"] is None


async def test_non_admin_list_locks_own_department(monkeypatch):
    dept = uuid4()
    member = _member(dept)
    rows = [(_fake_log(department_uid=dept, project_uid=uuid4()), "PRJ-X", "專案X")]
    async with _make_client(monkeypatch, member, list_rows=rows, list_total=1) as client:
        resp = await client.get("/api/v1/usage-logs")
    assert resp.status_code == 200, resp.text
    # 非-admin 未傳部門 → 自動鎖 actor.department_uid
    assert _FakeRepo.last_list_kwargs is not None
    assert _FakeRepo.last_list_kwargs["department_uid"] == dept


async def test_non_admin_list_project_uid_filter_passthrough(monkeypatch):
    dept = uuid4()
    member = _member(dept)
    proj = uuid4()
    async with _make_client(monkeypatch, member, list_rows=[], list_total=0) as client:
        resp = await client.get(f"/api/v1/usage-logs?project_uid={proj}")
    assert resp.status_code == 200, resp.text
    assert _FakeRepo.last_list_kwargs is not None
    # 部門鎖自身 + project_uid 下傳 repo
    assert _FakeRepo.last_list_kwargs["department_uid"] == dept
    assert _FakeRepo.last_list_kwargs["project_uid"] == proj


async def test_non_admin_list_other_department_returns_403(monkeypatch):
    member = _member(uuid4())
    other_dept = uuid4()
    async with _make_client(monkeypatch, member) as client:
        resp = await client.get(f"/api/v1/usage-logs?department_uid={other_dept}")
    assert resp.status_code == 403


# --- 明細 ---


async def test_admin_detail_includes_project(monkeypatch):
    admin = _admin()
    proj = uuid4()
    row = (_fake_log(department_uid=uuid4(), project_uid=proj), "PRJ-D", "專案D")
    async with _make_client(monkeypatch, admin, detail_row=row) as client:
        resp = await client.get(f"/api/v1/usage-logs/{uuid4()}")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["project_uid"] == str(proj)
    assert data["project_code"] == "PRJ-D"
    assert data["project_name"] == "專案D"
    # 明細含完整輸入輸出
    assert "request_content" in data
    assert "response_summary" in data


async def test_non_admin_detail_own_department_ok(monkeypatch):
    dept = uuid4()
    member = _member(dept)
    row = (_fake_log(department_uid=dept, project_uid=uuid4()), "PRJ-M", "專案M")
    async with _make_client(monkeypatch, member, detail_row=row) as client:
        resp = await client.get(f"/api/v1/usage-logs/{uuid4()}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["project_code"] == "PRJ-M"


async def test_non_admin_detail_other_department_returns_404(monkeypatch):
    member = _member(uuid4())
    other_dept = uuid4()
    row = (_fake_log(department_uid=other_dept, project_uid=uuid4()), "PRJ-O", "專案O")
    async with _make_client(monkeypatch, member, detail_row=row) as client:
        resp = await client.get(f"/api/v1/usage-logs/{uuid4()}")
    assert resp.status_code == 404


async def test_detail_not_found_returns_404(monkeypatch):
    async with _make_client(monkeypatch, _admin(), detail_row=None) as client:
        resp = await client.get(f"/api/v1/usage-logs/{uuid4()}")
    assert resp.status_code == 404
