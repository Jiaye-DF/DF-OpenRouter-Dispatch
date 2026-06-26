"""challenger 重跑結果讀取服務測試(task-407;對齊 docs/Design-Base/03-backend/07-testing.md)。

兩層:
1. **純函式單測**(無需 DB):`_decimal_to_str` —— None 保留、金額 6 位 / 分數 3 位補零。
2. **DB 整合測**(對齊 repo 測風格:真 DB + 外層 transaction rollback;DB 不可用 skip):
   (a) 有重跑列 → 回對應筆數、金額 / compare_score 為字串;
   (b) 無列 → 回空 list `[]`;
   (c) `compare_*` 為 NULL 的列(子開關停用)→ 對應欄 None 不爆。
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from uuid_utils import uuid7

from app.models.usage_log import UsageLog
from app.repositories.ai_model_eval_rerun import (
    AiModelEvalRerunRepository,
    RerunInput,
)
from app.services.ai_model_eval_rerun_result import (
    _decimal_to_str,
    build_rerun_results,
)

# ---------------------------------------------------------------------------
# 純函式測試輔助
# ---------------------------------------------------------------------------

_COST_QUANT = Decimal("0.000001")
_SCORE_QUANT = Decimal("0.001")


def _new_uid() -> UUID:
    return UUID(str(uuid7()))


# ---------------------------------------------------------------------------
# _decimal_to_str:Decimal → 字串(None 保留、補零位數)
# ---------------------------------------------------------------------------


def test_decimal_to_str_none_stays_none() -> None:
    assert _decimal_to_str(None, _COST_QUANT) is None
    assert _decimal_to_str(None, _SCORE_QUANT) is None


def test_decimal_to_str_cost_keeps_six_decimals() -> None:
    assert _decimal_to_str(Decimal("0.003"), _COST_QUANT) == "0.003000"
    assert _decimal_to_str(Decimal("0.000123"), _COST_QUANT) == "0.000123"


def test_decimal_to_str_score_keeps_three_decimals() -> None:
    assert _decimal_to_str(Decimal("0.8"), _SCORE_QUANT) == "0.800"
    assert _decimal_to_str(Decimal("0.812"), _SCORE_QUANT) == "0.812"


# ---------------------------------------------------------------------------
# DB 整合測試(對齊 test_ai_model_eval_result.py 的 fixture)
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


def _now() -> datetime:
    return datetime.now(UTC)


async def test_build_returns_empty_list_when_no_reruns(
    db_session: AsyncSession,
) -> None:
    """無重跑列 → build_rerun_results 回空 list `[]`(非 None)。"""
    log_uid = await _insert_usage_log(db_session)
    result = await build_rerun_results(log_uid, db=db_session)
    assert result == []


async def test_build_returns_reruns_with_str_fields(
    db_session: AsyncSession,
) -> None:
    """有重跑列 → 回對應筆數;金額 / compare_score 為字串(6 / 3 位補零)。"""
    repo = AiModelEvalRerunRepository(db_session)
    log_uid = await _insert_usage_log(db_session)
    eval_uid = _new_uid()
    model_uid = _new_uid()

    await repo.create_rerun(
        RerunInput(
            ai_evaluation_uid=eval_uid,
            usage_log_uid=log_uid,
            original_model="openai/gpt-4o",
            rerun_model="anthropic/claude-3.5",
            triggered_at=_now(),
            status="success",
            model_uid=model_uid,
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost_usd=Decimal("0.003000"),
            original_cost_usd=Decimal("0.005000"),
            cost_delta_usd=Decimal("-0.002000"),
            latency_ms=1234,
            compare_winner="challenger",
            compare_score=Decimal("0.800"),
            compare_reason="challenger 更準確",
            compare_judge_model="openai/gpt-4o",
        )
    )

    result = await build_rerun_results(log_uid, db=db_session)
    assert len(result) == 1
    r = result[0]
    assert r.rerun_model == "anthropic/claude-3.5"
    assert r.model_uid == model_uid
    assert r.prompt_tokens == 100
    assert r.total_tokens == 150
    assert r.latency_ms == 1234
    assert r.status == "success"
    # 金額:Numeric(12,6) → 6 位字串
    assert isinstance(r.cost_usd, str)
    assert r.cost_usd == "0.003000"
    assert r.original_cost_usd == "0.005000"
    assert r.cost_delta_usd == "-0.002000"
    # 信心分數:Numeric(4,3) → 3 位字串
    assert isinstance(r.compare_score, str)
    assert r.compare_score == "0.800"
    assert r.compare_winner == "challenger"
    assert r.compare_judge_model == "openai/gpt-4o"


async def test_build_handles_null_compare_and_cost(
    db_session: AsyncSession,
) -> None:
    """compare_* / 金額為 NULL 的列(子開關停用 / 失敗列)→ 對應欄 None 不爆。"""
    repo = AiModelEvalRerunRepository(db_session)
    log_uid = await _insert_usage_log(db_session)
    eval_uid = _new_uid()

    await repo.create_rerun(
        RerunInput(
            ai_evaluation_uid=eval_uid,
            usage_log_uid=log_uid,
            original_model="openai/gpt-4o",
            rerun_model="google/gemini-pro",
            triggered_at=_now(),
            status="error",
            error_code="upstream_timeout",
            # 金額 / token / compare_* 全留 None(子開關關 / 重跑失敗)
        )
    )

    result = await build_rerun_results(log_uid, db=db_session)
    assert len(result) == 1
    r = result[0]
    assert r.rerun_model == "google/gemini-pro"
    assert r.status == "error"
    assert r.error_code == "upstream_timeout"
    assert r.model_uid is None
    assert r.prompt_tokens is None
    assert r.cost_usd is None
    assert r.original_cost_usd is None
    assert r.cost_delta_usd is None
    assert r.compare_winner is None
    assert r.compare_score is None
    assert r.compare_reason is None
    assert r.compare_judge_model is None


async def test_build_returns_multiple_reruns(db_session: AsyncSession) -> None:
    """多 challenger → 回對應筆數。"""
    repo = AiModelEvalRerunRepository(db_session)
    log_uid = await _insert_usage_log(db_session)
    eval_uid = _new_uid()

    for model in ("anthropic/claude-3.5", "google/gemini-pro", "openai/gpt-4o-mini"):
        await repo.create_rerun(
            RerunInput(
                ai_evaluation_uid=eval_uid,
                usage_log_uid=log_uid,
                original_model="openai/gpt-4o",
                rerun_model=model,
                triggered_at=_now(),
                status="success",
                cost_usd=Decimal("0.001000"),
                compare_score=Decimal("0.700"),
            )
        )

    result = await build_rerun_results(log_uid, db=db_session)
    assert len(result) == 3
    assert {r.rerun_model for r in result} == {
        "anthropic/claude-3.5",
        "google/gemini-pro",
        "openai/gpt-4o-mini",
    }
