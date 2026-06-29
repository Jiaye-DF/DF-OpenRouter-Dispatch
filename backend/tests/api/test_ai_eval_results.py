"""評審結果讀取 API 測試(task-304;對齊 propose §4.1–4.3、決議 #1/#6)。

沿用本專案既有 API 測風格(見 tests/api/test_ai_eval.py):
- FastAPI app + httpx.AsyncClient(ASGITransport),不連真 DB。
- dependency_overrides 覆寫 require_admin(假 admin Actor)與 get_db(假 AsyncSession)。
- monkeypatch ai_eval_results 模組內的 build_evaluation_result(service,task-303)為
  可控假物件,以脫離真 DB 直接驗 endpoint 包裝行為(200 外殼 / evaluation=null / 權限)。

說明:本任務唯讀,endpoint 僅薄薄包 service 結果,故以 stub service 覆蓋三條路徑
(無評審 → null、有評審 → 完整結構、非 admin/未認證 → 403/401)。
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

import app.api.v1.ai_eval_results as ai_eval_results
from app.core.database import get_db
from app.core.deps import require_admin
from app.main import create_app
from app.schemas.actor import Actor
from app.schemas.ai_model_eval_result import (
    EvalCandidate,
    EvaluationResult,
    EvaluationSummary,
    RecommendConsensus,
    TaskAnalysis,
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


def _make_client(monkeypatch, *, service_result, admin_actor: Actor | None):
    """建 app + client。

    - service_result:build_evaluation_result 的回傳值(EvaluationResult | None)。
    - admin_actor=None 表示不覆寫 require_admin(走真實鑑權,用於 401/403)。
    """

    async def _fake_build(usage_log_uid, *, db):  # 簽章對齊 service
        return service_result

    monkeypatch.setattr(ai_eval_results, "build_evaluation_result", _fake_build)

    app = create_app()

    async def _fake_get_db():
        yield _FakeDb()

    app.dependency_overrides[get_db] = _fake_get_db
    if admin_actor is not None:
        app.dependency_overrides[require_admin] = lambda: admin_actor

    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


def _full_evaluation() -> EvaluationResult:
    """組一筆「有評審」的完整 EvaluationResult(父 + 任務分析 + 彙總 + 候選)。"""
    judge_uid = uuid4()
    return EvaluationResult(
        ai_evaluation_uid=uuid4(),
        usage_log_uid=uuid4(),
        ai_original_model="openai/gpt-4o",
        status="evaluated",
        ai_evaluated_at=datetime(2026, 6, 26, tzinfo=UTC),
        task_analysis=TaskAnalysis(
            summary="使用者想生成一段程式碼",
            intent="code_generation",
            complexity="medium",
        ),
        summary=EvaluationSummary(
            judge_count=3,
            succeeded_count=3,
            avg_fit_score="0.800",
            min_fit_score="0.700",
            max_fit_score="0.900",
            recommend_consensus=RecommendConsensus(
                model="anthropic/claude-3.5",
                tier="balanced",
                votes=2,
                is_split=False,
            ),
            self_vote_count=1,
        ),
        candidates=[
            EvalCandidate(
                ai_candidate_uid=uuid4(),
                judge_model_uid=judge_uid,
                judge_model_key="anthropic/claude-3.5",
                judge_model_name="Claude 3.5",
                ai_recommend_model="anthropic/claude-3.5",
                ai_recommend_tier="balanced",
                ai_recommend_reason="最佳吻合",
                ai_fit_score="0.900",
                ai_self_vote=True,
            ),
        ],
    )


async def test_no_evaluation_returns_200_null(monkeypatch, admin_actor):
    """無評審列(service 回 None)→ 200 + data.evaluation == null(決議 #6,非 404)。"""
    async with _make_client(
        monkeypatch, service_result=None, admin_actor=admin_actor
    ) as client:
        resp = await client.get(
            f"/api/v1/ai-eval/evaluations/by-usage-log/{uuid4()}"
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["code"] == 200
    assert body["detail"] == "success"
    assert body["data"]["evaluation"] is None


async def test_with_evaluation_returns_full_structure(monkeypatch, admin_actor):
    """有評審 → 200,evaluation 含 summary / candidates / task_analysis,fit_score 為字串。"""
    result = _full_evaluation()
    async with _make_client(
        monkeypatch, service_result=result, admin_actor=admin_actor
    ) as client:
        resp = await client.get(
            f"/api/v1/ai-eval/evaluations/by-usage-log/{result.usage_log_uid}"
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    evaluation = body["data"]["evaluation"]
    assert evaluation is not None
    # 任務分析:intent 傳原始枚舉字串
    assert evaluation["task_analysis"]["intent"] == "code_generation"
    # 彙總存在且 fit_score 一律字串(避免 JS 浮點誤差)
    summary = evaluation["summary"]
    assert summary["succeeded_count"] == 3
    assert isinstance(summary["avg_fit_score"], str)
    assert summary["recommend_consensus"]["is_split"] is False
    # 候選:fit_score 為字串
    assert len(evaluation["candidates"]) == 1
    cand = evaluation["candidates"][0]
    assert isinstance(cand["ai_fit_score"], str)
    assert cand["ai_self_vote"] is True


async def test_unauthenticated_returns_401(monkeypatch):
    """不覆寫 require_admin、不帶 cookie → 401(對齊既有保護端點)。"""
    async with _make_client(
        monkeypatch, service_result=None, admin_actor=None
    ) as client:
        resp = await client.get(
            f"/api/v1/ai-eval/evaluations/by-usage-log/{uuid4()}"
        )
    assert resp.status_code == 401


async def test_non_admin_returns_403(monkeypatch):
    """登入但非 admin → 403(覆寫 require_user 回 user 角色,require_admin 走真實判斷)。"""
    from app.core.deps import require_user

    async def _fake_build(usage_log_uid, *, db):
        return None

    monkeypatch.setattr(ai_eval_results, "build_evaluation_result", _fake_build)
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
            f"/api/v1/ai-eval/evaluations/by-usage-log/{uuid4()}"
        )
    assert resp.status_code == 403
