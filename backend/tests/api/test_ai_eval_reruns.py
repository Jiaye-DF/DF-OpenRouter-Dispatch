"""AI 判決總覽讀取 API 測試(task-408;對齊 propose §5.4 / §6.1、無資料 200+空陣列)。

沿用本專案既有 API 測風格(見 tests/api/test_ai_eval_results.py):
- FastAPI app + httpx.AsyncClient(ASGITransport),不連真 DB。
- dependency_overrides 覆寫 require_admin(假 admin Actor)與 get_db(假 AsyncSession)。
- monkeypatch ai_eval_reruns 模組內的 build_rerun_overview(service,task-407)為可控假物件,
  以脫離真 DB 直接驗 endpoint 包裝行為(200 外殼 / items=[] / 完整分組結構 / 權限)。

說明:本任務唯讀,endpoint 僅薄薄包 service 結果,故以 stub service 覆蓋路徑
(無重跑 → items=[]、有重跑 → 完整分組結構、非 admin → 403、未認證 → 401)。
另含 OpenAPI 斷言:單一分組端點存在、舊 by-usage-log 端點已移除。
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
from app.schemas.ai_model_eval_rerun_result import (
    RerunGroup,
    RerunOverviewPage,
    RerunRecommendation,
    RerunStats,
    RerunUsageLogInfo,
)


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


def _empty_page(*, page: int = 1, size: int = 20) -> RerunOverviewPage:
    """無資料總覽頁:items=[]、total=0、stats 全 0(對齊對外承諾,非 404)。"""
    return RerunOverviewPage(
        items=[],
        total=0,
        page=page,
        size=size,
        stats=RerunStats(
            total_recommendations=0,
            keep_count=0,
            swap_count=0,
            tie_count=0,
            unjudged_count=0,
            failed_count=0,
        ),
    )


def _full_page(*, page: int = 1, size: int = 20) -> RerunOverviewPage:
    """組一頁「一組 = 一筆原始呼叫 + 一個 AI 推薦模型真實重跑 + 對比裁決」的完整總覽頁。

    金額 / 分數皆字串(避免 JS 浮點誤差);原模型與推薦模型皆帶輸出原文。
    """
    recommendation = RerunRecommendation(
        rerun_model="anthropic/claude-3.5",
        model_uid=uuid4(),
        output_text="推薦模型的真實輸出原文",
        prompt_tokens=120,
        completion_tokens=80,
        total_tokens=200,
        cost_usd="0.001500",
        cost_delta_usd="-0.000500",
        latency_ms=1234,
        status="success",
        error_code=None,
        compare_winner="challenger",
        compare_score="0.850",
        compare_reason="推薦模型輸出更貼合任務",
        compare_judge_model="anthropic/claude-3.5",
        recommended_by="anthropic/claude-3.5",
        triggered_at=datetime(2026, 6, 26, tzinfo=UTC),
    )
    group = RerunGroup(
        usage_log_uid=uuid4(),
        original_model="openai/gpt-4o",
        original_output_text="原模型的真實輸出原文",
        original_input_text="使用者原始輸入內容",
        original_cost_usd="0.002000",
        evaluated_at=datetime(2026, 6, 26, tzinfo=UTC),
        usage_log_info=RerunUsageLogInfo(
            pid=12345,
            created_at=datetime(2026, 6, 26, tzinfo=UTC),
            model="openai/gpt-4o",
            status="success",
            prompt_tokens=120,
            completion_tokens=80,
            total_tokens=200,
            cost_usd="0.002000",
            latency_ms=900,
            used_tools=False,
            error_code=None,
        ),
        recommendations=[recommendation],
    )
    return RerunOverviewPage(
        items=[group],
        total=1,
        page=page,
        size=size,
        stats=RerunStats(
            total_recommendations=1,
            keep_count=0,
            swap_count=1,
            tie_count=0,
            unjudged_count=0,
            failed_count=0,
        ),
    )


def _make_client(monkeypatch, *, service_result, admin_actor: Actor | None):
    """建 app + client。

    - service_result:build_rerun_overview 的回傳值(RerunOverviewPage)。
    - admin_actor=None 表示不覆寫 require_admin(走真實鑑權,用於 401/403)。
    """

    async def _fake_build(*, db, page, size, order="desc", pid=None):  # 簽章對齊 service
        return service_result

    monkeypatch.setattr(ai_eval_reruns, "build_rerun_overview", _fake_build)

    app = create_app()

    async def _fake_get_db():
        yield _FakeDb()

    app.dependency_overrides[get_db] = _fake_get_db
    if admin_actor is not None:
        app.dependency_overrides[require_admin] = lambda: admin_actor

    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


async def test_no_reruns_returns_200_empty_items(monkeypatch, admin_actor):
    """無分組(service 回 items=[])→ 200 + data.items == [](對齊對外承諾,非 404)。"""
    async with _make_client(
        monkeypatch, service_result=_empty_page(), admin_actor=admin_actor
    ) as client:
        resp = await client.get("/api/v1/ai-eval/reruns")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["code"] == 200
    assert body["detail"] == "success"
    data = body["data"]
    assert data["items"] == []
    assert data["total"] == 0
    # 無資料時 stats 仍存在且全 0
    assert data["stats"]["total_recommendations"] == 0


async def test_with_reruns_returns_grouped_structure(monkeypatch, admin_actor):
    """有重跑 → 200,data.items 為分組結構:每組含原模型輸出原文 + 推薦模型輸出原文 + stats。"""
    async with _make_client(
        monkeypatch, service_result=_full_page(), admin_actor=admin_actor
    ) as client:
        resp = await client.get("/api/v1/ai-eval/reruns")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    data = body["data"]

    # 分頁外殼:items / total / page / size / stats
    assert data["total"] == 1
    assert data["page"] == 1
    assert data["size"] == 20
    assert "stats" in data

    # 分組:每組帶原模型 + 原模型真實輸出原文 + 原成本(字串)
    items = data["items"]
    assert isinstance(items, list)
    assert len(items) == 1
    group = items[0]
    assert group["original_model"] == "openai/gpt-4o"
    assert group["original_output_text"] == "原模型的真實輸出原文"
    assert isinstance(group["original_cost_usd"], str)

    # 每組 recommendations[]:含推薦模型輸出原文 + 對比裁決,金額 / 分數為字串
    recommendations = group["recommendations"]
    assert isinstance(recommendations, list)
    assert len(recommendations) == 1
    rec = recommendations[0]
    assert rec["rerun_model"] == "anthropic/claude-3.5"
    assert rec["output_text"] == "推薦模型的真實輸出原文"
    assert rec["status"] == "success"
    # 金額 / 分數一律字串(避免 JS 浮點誤差)
    assert isinstance(rec["cost_usd"], str)
    assert isinstance(rec["cost_delta_usd"], str)
    assert isinstance(rec["compare_score"], str)
    # 對比裁決
    assert rec["compare_winner"] == "challenger"
    assert rec["compare_judge_model"] == "anthropic/claude-3.5"

    # 裁決分布統計
    stats = data["stats"]
    assert stats["total_recommendations"] == 1
    assert stats["swap_count"] == 1


async def test_unauthenticated_returns_401(monkeypatch):
    """不覆寫 require_admin、不帶 cookie → 401(對齊既有保護端點)。"""
    async with _make_client(
        monkeypatch, service_result=_empty_page(), admin_actor=None
    ) as client:
        resp = await client.get("/api/v1/ai-eval/reruns")
    assert resp.status_code == 401


async def test_non_admin_returns_403(monkeypatch):
    """登入但非 admin → 403(覆寫 require_user 回 user 角色,require_admin 走真實判斷)。"""
    from app.core.deps import require_user

    async def _fake_build(*, db, page, size):
        return _empty_page()

    monkeypatch.setattr(ai_eval_reruns, "build_rerun_overview", _fake_build)
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
        resp = await client.get("/api/v1/ai-eval/reruns")
    assert resp.status_code == 403


async def test_by_usage_log_route_removed_returns_404(monkeypatch, admin_actor):
    """舊 by-usage-log 端點已移除 → 即使是 admin 打也 404(route 不存在)。"""
    async with _make_client(
        monkeypatch, service_result=_empty_page(), admin_actor=admin_actor
    ) as client:
        resp = await client.get(
            f"/api/v1/ai-eval/reruns/by-usage-log/{uuid4()}"
        )
    assert resp.status_code == 404


def test_openapi_has_overview_route_and_no_by_usage_log():
    """OpenAPI 斷言:單一分組總覽端點存在;舊 by-usage-log 端點不存在。"""
    app = create_app()
    schema = app.openapi()
    paths = schema["paths"]

    # 單一分組總覽端點存在且有 GET
    assert "/api/v1/ai-eval/reruns" in paths
    assert "get" in paths["/api/v1/ai-eval/reruns"]

    # 舊 by-usage-log 端點已移除:無任何 path 帶該前綴
    assert all("reruns/by-usage-log" not in path for path in paths)
