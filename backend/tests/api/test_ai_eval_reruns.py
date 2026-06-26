"""challenger 重跑結果讀取 API 測試(task-408;對齊 propose §5.4、無資料 200+空陣列)。

沿用本專案既有 API 測風格(見 tests/api/test_ai_eval_results.py):
- FastAPI app + httpx.AsyncClient(ASGITransport),不連真 DB。
- dependency_overrides 覆寫 require_admin(假 admin Actor)與 get_db(假 AsyncSession)。
- monkeypatch ai_eval_reruns 模組內的 build_rerun_results(service,task-407)為可控假物件,
  以脫離真 DB 直接驗 endpoint 包裝行為(200 外殼 / reruns=[] / 完整結構 / 權限)。

說明:本任務唯讀,endpoint 僅薄薄包 service 結果,故以 stub service 覆蓋路徑
(無重跑 → []、有重跑 → 完整結構、非 admin → 403、未認證 → 401)。
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

import app.api.v1.ai_eval_reruns as ai_eval_reruns
from app.core.database import get_db
from app.core.deps import require_admin
from app.main import create_app
from app.schemas.actor import Actor
from app.schemas.ai_model_eval_rerun_result import RerunResult


class _FakeDb:
    async def flush(self):
        return None

    async def commit(self):
        return None

    async def rollback(self):
        return None


@pytest.fixture
def admin_actor() -> Actor:
    return Actor(
        user_uid=uuid4(),
        account="admin",
        username="系統管理員",
        role="admin",
    )


def _make_client(monkeypatch, *, service_result, admin_actor: Actor | None):
    """建 app + client。

    - service_result:build_rerun_results 的回傳值(list[RerunResult])。
    - admin_actor=None 表示不覆寫 require_admin(走真實鑑權,用於 401/403)。
    """

    async def _fake_build(usage_log_uid, *, db):  # 簽章對齊 service
        return service_result

    monkeypatch.setattr(ai_eval_reruns, "build_rerun_results", _fake_build)

    app = create_app()

    async def _fake_get_db():
        yield _FakeDb()

    app.dependency_overrides[get_db] = _fake_get_db
    if admin_actor is not None:
        app.dependency_overrides[require_admin] = lambda: admin_actor

    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


def _full_rerun() -> RerunResult:
    """組一筆「有重跑 + 對比裁決」的完整 RerunResult(金額 / 分數皆字串)。"""
    return RerunResult(
        rerun_model="anthropic/claude-3.5",
        model_uid=uuid4(),
        prompt_tokens=120,
        completion_tokens=80,
        total_tokens=200,
        cost_usd="0.001500",
        original_cost_usd="0.002000",
        cost_delta_usd="-0.000500",
        latency_ms=1234,
        status="success",
        error_code=None,
        compare_winner="challenger",
        compare_score="0.850",
        compare_reason="challenger 輸出更貼合任務",
        compare_judge_model="anthropic/claude-3.5",
        triggered_at=datetime(2026, 6, 26, tzinfo=UTC),
    )


async def test_no_reruns_returns_200_empty_list(monkeypatch, admin_actor):
    """無重跑列(service 回 [])→ 200 + data.reruns == [](對齊對外承諾,非 404)。"""
    async with _make_client(
        monkeypatch, service_result=[], admin_actor=admin_actor
    ) as client:
        resp = await client.get(
            f"/api/v1/ai-eval/reruns/by-usage-log/{uuid4()}"
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["code"] == 200
    assert body["detail"] == "success"
    assert body["data"]["reruns"] == []


async def test_with_reruns_returns_array(monkeypatch, admin_actor):
    """有重跑 → 200,data.reruns 為陣列且元素含對比裁決,金額 / 分數為字串。"""
    result = [_full_rerun()]
    async with _make_client(
        monkeypatch, service_result=result, admin_actor=admin_actor
    ) as client:
        resp = await client.get(
            f"/api/v1/ai-eval/reruns/by-usage-log/{uuid4()}"
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    reruns = body["data"]["reruns"]
    assert isinstance(reruns, list)
    assert len(reruns) == 1
    row = reruns[0]
    assert row["rerun_model"] == "anthropic/claude-3.5"
    assert row["status"] == "success"
    # 金額 / 分數一律字串(避免 JS 浮點誤差)
    assert isinstance(row["cost_usd"], str)
    assert isinstance(row["cost_delta_usd"], str)
    assert isinstance(row["compare_score"], str)
    # 對比裁決
    assert row["compare_winner"] == "challenger"
    assert row["compare_judge_model"] == "anthropic/claude-3.5"


async def test_unauthenticated_returns_401(monkeypatch):
    """不覆寫 require_admin、不帶 cookie → 401(對齊既有保護端點)。"""
    async with _make_client(
        monkeypatch, service_result=[], admin_actor=None
    ) as client:
        resp = await client.get(
            f"/api/v1/ai-eval/reruns/by-usage-log/{uuid4()}"
        )
    assert resp.status_code == 401


async def test_non_admin_returns_403(monkeypatch):
    """登入但非 admin → 403(覆寫 require_user 回 user 角色,require_admin 走真實判斷)。"""
    from app.core.deps import require_user

    async def _fake_build(usage_log_uid, *, db):
        return []

    monkeypatch.setattr(ai_eval_reruns, "build_rerun_results", _fake_build)
    app = create_app()

    async def _fake_get_db():
        yield _FakeDb()

    user_actor = Actor(
        user_uid=uuid4(), account="u", username="一般使用者", role="user"
    )
    app.dependency_overrides[get_db] = _fake_get_db
    app.dependency_overrides[require_user] = lambda: user_actor

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/ai-eval/reruns/by-usage-log/{uuid4()}"
        )
    assert resp.status_code == 403
