"""評審結果彙總服務測試(task-303;對齊 docs/Design-Base/03-backend/07-testing.md)。

兩層:
1. **純函式單測**(無需 DB,涵蓋全邊界):`_compute_summary` / `_compute_recommend_consensus`
   / `_fit_to_str` —— avg/min/max(含全 null)、眾數(2:1 不分歧 / 1:1:1 分歧 / 1:1 分歧 /
   單票不分歧 / 全 null)、self_vote_count(None 不計)、四捨五入 3 位、Decimal→str 格式。
   直接構造 `CandidateWithJudge` 列表餵入,不碰 DB。
2. **DB 整合測**(對齊 repo 測風格:真 DB + 外層 transaction rollback;DB 不可用 skip):
   無父列回 None、有父+候選回 EvaluationResult、部分成功 succeeded < judge。
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from decimal import Decimal
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import func
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from uuid_utils import uuid7

from app.models.model import Model
from app.models.usage_log import UsageLog
from app.repositories.ai_model_evaluation import (
    AiModelEvaluationRepository,
    CandidateInput,
    CandidateWithJudge,
)
from app.services.ai_model_eval_result import (
    _compute_recommend_consensus,
    _compute_summary,
    _fit_to_str,
    build_evaluation_result,
)

# ---------------------------------------------------------------------------
# 純函式測試輔助
# ---------------------------------------------------------------------------


def _new_uid() -> UUID:
    return UUID(str(uuid7()))


def _cand(
    *,
    recommend_model: str | None = None,
    recommend_tier: str | None = None,
    fit_score: Decimal | None = None,
    self_vote: bool | None = None,
) -> CandidateWithJudge:
    """構造一筆 `CandidateWithJudge`(只填彙總會用到的欄位,其餘給佔位值)。"""
    return CandidateWithJudge(
        ai_candidate_uid=_new_uid(),
        model_uid=_new_uid(),
        ai_recommend_model=recommend_model,
        ai_recommend_tier=recommend_tier,
        ai_recommend_reason=None,
        ai_fit_score=fit_score,
        ai_self_vote=self_vote,
        judge_model_key=None,
        judge_model_name=None,
    )


# ---------------------------------------------------------------------------
# _fit_to_str:Decimal → 3 位字串
# ---------------------------------------------------------------------------


def test_fit_to_str_none_stays_none() -> None:
    assert _fit_to_str(None) is None


def test_fit_to_str_keeps_three_decimals() -> None:
    assert _fit_to_str(Decimal("0.7")) == "0.700"
    assert _fit_to_str(Decimal("0.812")) == "0.812"


def test_fit_to_str_rounds_half_up() -> None:
    # 0.7005 → 第 4 位 5 進位 → 0.701(ROUND_HALF_UP)
    assert _fit_to_str(Decimal("0.7005")) == "0.701"
    assert _fit_to_str(Decimal("0.7004")) == "0.700"


# ---------------------------------------------------------------------------
# _compute_summary:avg / min / max / succeeded / self_vote
# ---------------------------------------------------------------------------


def test_summary_avg_min_max_three_scores() -> None:
    cands = [
        _cand(fit_score=Decimal("0.600")),
        _cand(fit_score=Decimal("0.700")),
        _cand(fit_score=Decimal("0.900")),
    ]
    s = _compute_summary(cands)
    assert s.judge_count == 3
    assert s.succeeded_count == 3
    # (0.6+0.7+0.9)/3 = 0.7333... → 四捨五入 3 位 → 0.733
    assert s.avg_fit_score == "0.733"
    assert s.min_fit_score == "0.600"
    assert s.max_fit_score == "0.900"


def test_summary_avg_rounds_half_up() -> None:
    # (0.700 + 0.701) / 2 = 0.7005 → ROUND_HALF_UP → 0.701
    cands = [_cand(fit_score=Decimal("0.700")), _cand(fit_score=Decimal("0.701"))]
    s = _compute_summary(cands)
    assert s.avg_fit_score == "0.701"


def test_summary_all_null_scores_yield_none() -> None:
    cands = [_cand(), _cand(), _cand()]
    s = _compute_summary(cands)
    assert s.judge_count == 3
    assert s.succeeded_count == 0
    assert s.avg_fit_score is None
    assert s.min_fit_score is None
    assert s.max_fit_score is None


def test_summary_partial_success_counts() -> None:
    cands = [
        _cand(fit_score=Decimal("0.500")),
        _cand(),  # 失敗裁判:fit_score=None
        _cand(fit_score=Decimal("0.900")),
    ]
    s = _compute_summary(cands)
    assert s.judge_count == 3
    assert s.succeeded_count == 2
    assert s.min_fit_score == "0.500"
    assert s.max_fit_score == "0.900"
    # avg = (0.5 + 0.9)/2 = 0.700
    assert s.avg_fit_score == "0.700"


def test_summary_empty_candidates() -> None:
    s = _compute_summary([])
    assert s.judge_count == 0
    assert s.succeeded_count == 0
    assert s.avg_fit_score is None
    assert s.recommend_consensus.model is None
    assert s.recommend_consensus.votes == 0
    assert s.recommend_consensus.is_split is False
    assert s.self_vote_count == 0


def test_summary_self_vote_count_excludes_none() -> None:
    cands = [
        _cand(self_vote=True),
        _cand(self_vote=False),
        _cand(self_vote=None),  # None 不計入
        _cand(self_vote=True),
    ]
    s = _compute_summary(cands)
    assert s.self_vote_count == 2


# ---------------------------------------------------------------------------
# _compute_recommend_consensus:眾數 + is_split(分母 = 有效推薦票數)
# ---------------------------------------------------------------------------


def test_consensus_two_one_not_split() -> None:
    # 2:1 → top_votes=2, valid=3 → 2*2<=3? False → 不分歧
    cands = [
        _cand(recommend_model="openai/gpt-4o-mini", recommend_tier="fast"),
        _cand(recommend_model="openai/gpt-4o-mini", recommend_tier="fast"),
        _cand(recommend_model="anthropic/claude", recommend_tier="mid"),
    ]
    c = _compute_recommend_consensus(cands)
    assert c.model == "openai/gpt-4o-mini"
    assert c.votes == 2
    assert c.tier == "fast"
    assert c.is_split is False


def test_consensus_one_one_one_split() -> None:
    # 1:1:1 → top_votes=1, valid=3 → 1*2<=3? True 且 valid>1 → 分歧
    cands = [
        _cand(recommend_model="a/x"),
        _cand(recommend_model="b/y"),
        _cand(recommend_model="c/z"),
    ]
    c = _compute_recommend_consensus(cands)
    assert c.votes == 1
    assert c.is_split is True


def test_consensus_one_one_split() -> None:
    # 1:1 → top_votes=1, valid=2 → 1*2<=2? True 且 valid>1 → 分歧
    cands = [_cand(recommend_model="a/x"), _cand(recommend_model="b/y")]
    c = _compute_recommend_consensus(cands)
    assert c.votes == 1
    assert c.is_split is True


def test_consensus_single_vote_not_split() -> None:
    # 單票 → valid=1 → valid>1 False → 不分歧
    cands = [
        _cand(recommend_model="a/x", recommend_tier="fast"),
        _cand(),  # recommend_model=None,不計入分母
        _cand(),
    ]
    c = _compute_recommend_consensus(cands)
    assert c.model == "a/x"
    assert c.votes == 1
    assert c.tier == "fast"
    assert c.is_split is False


def test_consensus_all_null_model_none_votes_zero() -> None:
    cands = [_cand(), _cand(), _cand()]
    c = _compute_recommend_consensus(cands)
    assert c.model is None
    assert c.tier is None
    assert c.votes == 0
    assert c.is_split is False


def test_consensus_tie_picks_some_top_and_split() -> None:
    # 2:2 → top_votes=2, valid=4 → 2*2<=4 True → 分歧;model 為任一最高票
    cands = [
        _cand(recommend_model="a/x"),
        _cand(recommend_model="a/x"),
        _cand(recommend_model="b/y"),
        _cand(recommend_model="b/y"),
    ]
    c = _compute_recommend_consensus(cands)
    assert c.model in {"a/x", "b/y"}
    assert c.votes == 2
    assert c.is_split is True


# ---------------------------------------------------------------------------
# DB 整合測試(對齊 repositories/test_ai_model_evaluation.py 的 fixture)
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://ord:ord_dev_pass_change_me@localhost:5533/ord",
)


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """外層 transaction + 加入式 session;測試結束整批 rollback(不污染 dev DB)。"""
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=None)
    try:
        conn = await engine.connect()
    except (OSError, OperationalError) as exc:  # pragma: no cover - 環境相依
        await engine.dispose()
        pytest.skip(f"測試 DB 無法連線({TEST_DATABASE_URL}):{exc}")

    trans = await conn.begin()
    session = AsyncSession(bind=conn, expire_on_commit=False)
    try:
        yield session
    finally:
        await session.close()
        if trans.is_active:
            await trans.rollback()
        await conn.close()
        await engine.dispose()


async def _insert_usage_log(session: AsyncSession) -> UUID:
    uid = _new_uid()
    session.add(UsageLog(usage_log_uid=uid, model="openai/gpt-4o", status="success"))
    await session.flush()
    return uid


async def _insert_model(session: AsyncSession, *, key: str, name: str) -> UUID:
    uid = _new_uid()
    session.add(
        Model(
            model_uid=uid,
            model_key=key,
            name=name,
            last_synced_at=func.now(),
            is_deleted=False,
        )
    )
    await session.flush()
    return uid


async def test_build_returns_none_when_no_parent(db_session: AsyncSession) -> None:
    """無評審父列 → build_evaluation_result 回 None(對應 endpoint evaluation=null)。"""
    log_uid = await _insert_usage_log(db_session)
    result = await build_evaluation_result(log_uid, db=db_session)
    assert result is None


async def test_build_full_result_three_candidates(db_session: AsyncSession) -> None:
    """有父 + 3 候選 + 3 models → 回 EvaluationResult,欄位與彙總正確、fit_score 為 str。"""
    repo = AiModelEvaluationRepository(db_session)
    log_uid = await _insert_usage_log(db_session)

    suffix = uuid7()
    m1 = await _insert_model(db_session, key=f"anthropic/claude-{suffix}", name="Claude")
    m2 = await _insert_model(db_session, key=f"openai/gpt-4o-{suffix}", name="GPT-4o")
    m3 = await _insert_model(db_session, key=f"google/gemini-{suffix}", name="Gemini")

    cands = [
        CandidateInput(
            model_uid=m1,
            ai_recommend_model="openai/gpt-4o-mini",
            ai_recommend_tier="fast",
            ai_fit_score=Decimal("0.600"),
            ai_self_vote=False,
        ),
        CandidateInput(
            model_uid=m2,
            ai_recommend_model="openai/gpt-4o-mini",
            ai_recommend_tier="fast",
            ai_fit_score=Decimal("0.900"),
            ai_self_vote=True,
        ),
        CandidateInput(
            model_uid=m3,
            ai_recommend_model="anthropic/claude-3.5",
            ai_recommend_tier="mid",
            ai_fit_score=Decimal("0.700"),
            ai_self_vote=False,
        ),
    ]
    await repo.create_evaluation_with_candidates(
        usage_log_uid=log_uid,
        ai_original_model="openai/gpt-4o",
        candidates=cands,
        ai_task_summary="整理會議記錄",
        ai_task_intent="summarize",
        ai_task_complexity="low",
    )

    result = await build_evaluation_result(log_uid, db=db_session)
    assert result is not None
    assert result.usage_log_uid == log_uid
    assert result.status == "evaluated"
    assert result.ai_original_model == "openai/gpt-4o"

    # task_analysis 三欄皆有 → 提供
    assert result.task_analysis is not None
    assert result.task_analysis.summary == "整理會議記錄"
    assert result.task_analysis.intent == "summarize"
    assert result.task_analysis.complexity == "low"

    # summary 正確
    assert result.summary is not None
    assert result.summary.judge_count == 3
    assert result.summary.succeeded_count == 3
    assert result.summary.avg_fit_score == "0.733"  # (0.6+0.9+0.7)/3
    assert result.summary.min_fit_score == "0.600"
    assert result.summary.max_fit_score == "0.900"
    assert result.summary.self_vote_count == 1
    # 推薦共識:gpt-4o-mini 2 票 vs claude 1 票 → 2:1 不分歧
    assert result.summary.recommend_consensus.model == "openai/gpt-4o-mini"
    assert result.summary.recommend_consensus.votes == 2
    assert result.summary.recommend_consensus.tier == "fast"
    assert result.summary.recommend_consensus.is_split is False

    # candidates:fit_score 為 str、judge_model_uid ← model_uid、補上 key/name
    assert len(result.candidates) == 3
    by_uid = {c.judge_model_uid: c for c in result.candidates}
    assert by_uid[m1].judge_model_key == f"anthropic/claude-{suffix}"
    assert by_uid[m1].judge_model_name == "Claude"
    assert by_uid[m1].ai_fit_score == "0.600"
    assert isinstance(by_uid[m2].ai_fit_score, str)
    assert by_uid[m2].ai_fit_score == "0.900"


async def test_build_partial_success(db_session: AsyncSession) -> None:
    """部分成功(1 候選 AI 欄位 null)→ succeeded_count < judge_count,fit 全 None 不入平均。"""
    repo = AiModelEvaluationRepository(db_session)
    log_uid = await _insert_usage_log(db_session)

    suffix = uuid7()
    m1 = await _insert_model(db_session, key=f"a/x-{suffix}", name="X")
    m2 = await _insert_model(db_session, key=f"b/y-{suffix}", name="Y")
    m3 = await _insert_model(db_session, key=f"c/z-{suffix}", name="Z")

    cands = [
        CandidateInput(
            model_uid=m1,
            ai_recommend_model="openai/gpt-4o-mini",
            ai_fit_score=Decimal("0.800"),
            ai_self_vote=False,
        ),
        # 失敗裁判:全 None
        CandidateInput(model_uid=m2),
        CandidateInput(
            model_uid=m3,
            ai_recommend_model="openai/gpt-4o-mini",
            ai_fit_score=Decimal("0.600"),
            ai_self_vote=False,
        ),
    ]
    await repo.create_evaluation_with_candidates(
        usage_log_uid=log_uid,
        ai_original_model="openai/gpt-4o",
        candidates=cands,
    )

    result = await build_evaluation_result(log_uid, db=db_session)
    assert result is not None
    assert result.summary is not None
    assert result.summary.judge_count == 3
    assert result.summary.succeeded_count == 2
    assert result.summary.avg_fit_score == "0.700"  # (0.8+0.6)/2
    # 只有 2 票有效推薦,皆 gpt-4o-mini → top_votes=2, valid=2 → 不分歧
    assert result.summary.recommend_consensus.votes == 2
    assert result.summary.recommend_consensus.is_split is False
