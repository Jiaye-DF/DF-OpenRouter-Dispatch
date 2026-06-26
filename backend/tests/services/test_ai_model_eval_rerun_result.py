"""AI 推薦模型重跑「依用量紀錄分組」讀取服務測試(task-407;對齊 03-backend/07-testing.md)。

兩層:
1. **純函式單測**(無需 DB):`_decimal_to_str`(None 保留 / 補零位數)、
   `_output_text_of`(取 response_summary.output_text;缺 / 空 / 非字串 → None)、
   `_compute_stats`(裁決分布計數)。
2. **DB 整合測**(真 DB + 外層 transaction rollback;DB 不可用 skip):
   (a) 無重跑 → items=[] / total=0 / stats 全 0;
   (b) 同 usage_log 多推薦 → 併入同一 RerunGroup;金額 / 分數為字串;補原模型輸出原文;
   (c) compare_* / 金額 NULL 列 → 對應欄 None 不爆;
   (d) stats 計數正確;
   (e) 分頁以「組」為單位、total = 分組組數。
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

from app.models.ai_model_eval_rerun import AiModelEvalRerun
from app.models.usage_log import UsageLog
from app.repositories.ai_model_eval_rerun import (
    AiModelEvalRerunRepository,
    RerunInput,
)
from app.services.ai_model_eval_rerun_result import (
    _compute_stats,
    _decimal_to_str,
    _output_text_of,
    build_rerun_overview,
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
# _output_text_of:取 response_summary.output_text
# ---------------------------------------------------------------------------


def test_output_text_of_returns_text() -> None:
    assert _output_text_of({"output_text": "hello"}) == "hello"


def test_output_text_of_none_or_missing_or_empty() -> None:
    assert _output_text_of(None) is None
    assert _output_text_of({}) is None
    assert _output_text_of({"output_text": ""}) is None  # 空字串 → None
    assert _output_text_of({"output_text": 123}) is None  # 非字串 → None


# ---------------------------------------------------------------------------
# _compute_stats:裁決分布計數
# ---------------------------------------------------------------------------


def _row(*, status: str = "success", compare_winner: str | None = None) -> AiModelEvalRerun:
    """組一個僅帶 stats 所需欄位的 ORM 列(不落 DB,純函式測試用)。"""
    return AiModelEvalRerun(status=status, compare_winner=compare_winner)


def test_compute_stats_counts_each_bucket() -> None:
    rows = [
        _row(compare_winner="original"),  # keep
        _row(compare_winner="original"),  # keep
        _row(compare_winner="challenger"),  # swap
        _row(compare_winner="tie"),  # tie
        _row(status="success", compare_winner=None),  # unjudged
        _row(status="error", compare_winner=None),  # failed
        _row(status="error", compare_winner="original"),  # failed 優先於 winner
    ]
    stats = _compute_stats(rows)
    assert stats.total_recommendations == 7
    assert stats.keep_count == 2
    assert stats.swap_count == 1
    assert stats.tie_count == 1
    assert stats.unjudged_count == 1
    assert stats.failed_count == 2


def test_compute_stats_empty() -> None:
    stats = _compute_stats([])
    assert stats.total_recommendations == 0
    assert stats.keep_count == 0
    assert stats.failed_count == 0


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


async def _insert_usage_log(
    session: AsyncSession, *, response_summary: dict | None = None
) -> UUID:
    uid = _new_uid()
    session.add(
        UsageLog(
            usage_log_uid=uid,
            model="openai/gpt-4o",
            status="success",
            response_summary=response_summary,
        )
    )
    await session.flush()
    return uid


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# build_rerun_overview:依用量紀錄分組分頁
# 注意:此為「全表」查詢,非以 usage_log_uid 隔離 → transaction 內可見 dev DB 既有
# committed 列。故用遠未來時戳(2099)保證自插組排最前、total/len 用相對(>=)斷言。
# ---------------------------------------------------------------------------


async def test_overview_empty_when_no_reruns(db_session: AsyncSession) -> None:
    """全表可能有既有列,但自插 0 列 → 不對 total 絕對值斷言;只驗回傳結構健全。

    新建一筆「無重跑」的 usage_log,確認它不會出現在任何分組(無重跑列即無組)。
    """
    log_uid = await _insert_usage_log(db_session)
    page = await build_rerun_overview(db=db_session, page=1, size=20)
    assert page.page == 1
    assert page.size == 20
    assert page.total >= 0
    assert isinstance(page.items, list)
    assert log_uid not in {g.usage_log_uid for g in page.items}


async def test_overview_groups_multiple_recommendations_same_log(
    db_session: AsyncSession,
) -> None:
    """同一 usage_log 的多個推薦模型 → 併入同一個 RerunGroup;金額 / 分數為字串;補原輸出。"""
    repo = AiModelEvalRerunRepository(db_session)
    # 原模型輸出原文存於 usage_logs.response_summary.output_text
    log_uid = await _insert_usage_log(
        db_session, response_summary={"output_text": "原模型輸出"}
    )
    eval_uid = _new_uid()

    base = datetime(2099, 1, 1, 12, 0, 0, tzinfo=UTC)
    for i, model in enumerate(("rec/a", "rec/b", "rec/c")):
        await repo.create_rerun(
            RerunInput(
                ai_evaluation_uid=eval_uid,
                usage_log_uid=log_uid,
                original_model="openai/gpt-4o",
                rerun_model=model,
                triggered_at=base.replace(minute=i),
                status="success",
                response_summary={"output_text": f"推薦輸出-{model}"},
                cost_usd=Decimal("0.001000"),
                original_cost_usd=Decimal("0.002000"),
                cost_delta_usd=Decimal("-0.001000"),
                compare_winner="challenger",
                compare_score=Decimal("0.900"),
                compare_reason="更好",
                compare_judge_model="judge/x",
            )
        )

    page = await build_rerun_overview(db=db_session, page=1, size=20)
    # 2099 時戳保證自插組排最前
    group = page.items[0]
    assert group.usage_log_uid == log_uid
    assert group.original_model == "openai/gpt-4o"
    # 三個推薦模型併入同一組
    assert len(group.recommendations) == 3
    assert {r.rerun_model for r in group.recommendations} == {"rec/a", "rec/b", "rec/c"}
    # 原模型輸出原文反查補上
    assert group.original_output_text == "原模型輸出"
    # 推薦模型各自帶真實輸出原文
    rec = next(r for r in group.recommendations if r.rerun_model == "rec/a")
    assert rec.output_text == "推薦輸出-rec/a"
    # 金額 / 分數為字串
    assert isinstance(rec.cost_usd, str)
    assert rec.cost_usd == "0.001000"
    assert rec.cost_delta_usd == "-0.001000"
    assert isinstance(rec.compare_score, str)
    assert rec.compare_score == "0.900"
    assert isinstance(group.original_cost_usd, str)
    assert group.original_cost_usd == "0.002000"


async def test_overview_handles_null_compare_cost_and_output(
    db_session: AsyncSession,
) -> None:
    """compare_* / 金額 / 輸出為 NULL 的列 → 對應欄 None 不爆;原 log 無快照 → original_output_text None。"""
    repo = AiModelEvalRerunRepository(db_session)
    log_uid = await _insert_usage_log(db_session, response_summary=None)
    eval_uid = _new_uid()

    await repo.create_rerun(
        RerunInput(
            ai_evaluation_uid=eval_uid,
            usage_log_uid=log_uid,
            original_model="openai/gpt-4o",
            rerun_model="rec/fail",
            triggered_at=datetime(2099, 1, 1, 13, 0, 0, tzinfo=UTC),
            status="error",
            error_code="upstream_timeout",
            # 金額 / token / compare_* / response_summary 全留 None
        )
    )

    page = await build_rerun_overview(db=db_session, page=1, size=20)
    group = next(g for g in page.items if g.usage_log_uid == log_uid)
    assert group.original_output_text is None  # 原 log 無 response_summary
    assert group.original_cost_usd is None
    assert len(group.recommendations) == 1
    rec = group.recommendations[0]
    assert rec.status == "error"
    assert rec.error_code == "upstream_timeout"
    assert rec.output_text is None
    assert rec.cost_usd is None
    assert rec.cost_delta_usd is None
    assert rec.compare_winner is None
    assert rec.compare_score is None


async def test_overview_stats_counts(db_session: AsyncSession) -> None:
    """stats 對「當頁分組內全部推薦模型」計數正確(keep/swap/tie/unjudged/failed)。

    用單組(一個 usage_log)各種裁決狀態 → 因 2099 時戳排最前、size=1 → 當頁只此組,
    stats 即此組計數,排除 dev DB 既有列干擾。
    """
    repo = AiModelEvalRerunRepository(db_session)
    log_uid = await _insert_usage_log(db_session)
    eval_uid = _new_uid()
    base = datetime(2099, 1, 1, 14, 0, 0, tzinfo=UTC)
    specs = [
        ("rec/keep", "success", "original"),
        ("rec/swap", "success", "challenger"),
        ("rec/tie", "success", "tie"),
        ("rec/unjudged", "success", None),
        ("rec/failed", "error", None),
    ]
    for i, (model, status, winner) in enumerate(specs):
        await repo.create_rerun(
            RerunInput(
                ai_evaluation_uid=eval_uid,
                usage_log_uid=log_uid,
                original_model="openai/gpt-4o",
                rerun_model=model,
                triggered_at=base.replace(minute=i),
                status=status,
                compare_winner=winner,
            )
        )

    # size=1 → 當頁只含 2099 自插組(排最前),stats 即此組 5 筆推薦的計數。
    page = await build_rerun_overview(db=db_session, page=1, size=1)
    assert page.items[0].usage_log_uid == log_uid
    assert page.stats.total_recommendations == 5
    assert page.stats.keep_count == 1
    assert page.stats.swap_count == 1
    assert page.stats.tie_count == 1
    assert page.stats.unjudged_count == 1
    assert page.stats.failed_count == 1


async def test_overview_pagination_counts_groups_not_rows(
    db_session: AsyncSession,
) -> None:
    """分頁以「組」為單位:2 個 usage_log 各 2 推薦 → size=1 當頁 1 組、該組含 2 推薦;total = 組數。"""
    repo = AiModelEvalRerunRepository(db_session)
    base = datetime(2099, 1, 1, 15, 0, 0, tzinfo=UTC)
    log_uids = []
    for g in range(2):
        log_uid = await _insert_usage_log(db_session)
        log_uids.append(log_uid)
        eval_uid = _new_uid()
        for i in range(2):
            await repo.create_rerun(
                RerunInput(
                    ai_evaluation_uid=eval_uid,
                    usage_log_uid=log_uid,
                    original_model="openai/gpt-4o",
                    rerun_model=f"rec/{g}-{i}",
                    # g 越大時戳越新 → g=1 組排最前
                    triggered_at=base.replace(hour=15 + g, minute=i),
                    status="success",
                )
            )

    page1 = await build_rerun_overview(db=db_session, page=1, size=1)
    # total = distinct usage_log 組數(含 dev DB 既有),至少 2
    assert page1.total >= 2
    # size=1 → 當頁僅 1 組,且該組(2099 最新)為自插的 g=1 組,含 2 推薦
    assert len(page1.items) == 1
    top = page1.items[0]
    assert top.usage_log_uid == log_uids[1]
    assert len(top.recommendations) == 2
