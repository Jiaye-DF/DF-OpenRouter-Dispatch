"""ai_model_eval_rerun repository 真 DB 整合測試(對齊 03-backend/07-testing.md)。

禁 mock SQL:連真實測試 DB,每個測試包在外層 connection-level transaction,結束
一律 rollback → 不污染既有 dev DB 資料。連線位址以 `TEST_DATABASE_URL` 覆寫;
未設時 fallback 本機 compose 暴露的 postgres(host port 5533)。DB 不可用整模組 skip。

涵蓋:(a) create_rerun 冪等(同 (eval_uid, rerun_model) → 僅一列);
(b) fetch_unreran_evaluation_uids 條件 + FIFO；(c) mark_reran 終局值;
(d) list_by_usage_log_uid / list_by_evaluation_uid 過濾軟刪。
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from uuid_utils import uuid7

from app.models.ai_model_eval_rerun import AiModelEvalRerun
from app.models.ai_model_evaluation import AiModelEvaluation
from app.models.usage_log import UsageLog
from app.repositories.ai_model_eval_rerun import (
    AiModelEvalRerunRepository,
    RerunInput,
)
from app.repositories.ai_model_evaluation import AiModelEvaluationRepository

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://ord:ord_dev_pass_change_me@localhost:5533/ord",
)

_TPE = timezone(timedelta(hours=8))


def _new_uid() -> UUID:
    return UUID(str(uuid7()))


def _now() -> datetime:
    return datetime.now(tz=_TPE)


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """外層 transaction + 加入式 session;測試結束整批 rollback,不落地。"""
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


async def _insert_evaluation(
    session: AsyncSession,
    *,
    status: str = "evaluated",
    ai_reran_at: datetime | None = None,
    created_at: datetime | None = None,
    is_deleted: bool = False,
) -> tuple[UUID, UUID]:
    """直接插一筆父評審(繞過 service,精準控制 status/ai_reran_at/created_at)。

    回 `(ai_evaluation_uid, usage_log_uid)`。
    """
    log_uid = await _insert_usage_log(session)
    eval_uid = _new_uid()
    parent = AiModelEvaluation(
        ai_evaluation_uid=eval_uid,
        usage_log_uid=log_uid,
        ai_original_model="openai/gpt-4o",
        status=status,
        ai_reran_at=ai_reran_at,
        is_deleted=is_deleted,
    )
    if created_at is not None:
        parent.created_at = created_at
    session.add(parent)
    await session.flush()
    return eval_uid, log_uid


def _rerun_input(
    *,
    ai_evaluation_uid: UUID,
    usage_log_uid: UUID,
    rerun_model: str = "anthropic/claude-3.5",
    status: str = "success",
) -> RerunInput:
    return RerunInput(
        ai_evaluation_uid=ai_evaluation_uid,
        usage_log_uid=usage_log_uid,
        original_model="openai/gpt-4o",
        rerun_model=rerun_model,
        triggered_at=_now(),
        status=status,
        model_uid=_new_uid(),
        prompt_tokens=120,
        completion_tokens=80,
        total_tokens=200,
        cost_usd=Decimal("0.001234"),
        original_cost_usd=Decimal("0.002000"),
        cost_delta_usd=Decimal("-0.000766"),
        latency_ms=850,
        compare_winner="challenger",
        compare_score=Decimal("0.875"),
        compare_reason="便宜且品質相當",
        compare_judge_model="anthropic/claude-opus",
    )


async def _count_reruns(
    session: AsyncSession, ai_evaluation_uid: UUID, rerun_model: str
) -> int:
    rows = (
        (
            await session.execute(
                select(AiModelEvalRerun).where(
                    AiModelEvalRerun.ai_evaluation_uid == ai_evaluation_uid,
                    AiModelEvalRerun.rerun_model == rerun_model,
                )
            )
        )
        .scalars()
        .all()
    )
    return len(rows)


# ── (a) create_rerun 冪等 ──────────────────────────────────────────────


async def test_create_rerun_writes_row(db_session: AsyncSession) -> None:
    repo = AiModelEvalRerunRepository(db_session)
    eval_uid, log_uid = await _insert_evaluation(db_session)

    row = await repo.create_rerun(
        _rerun_input(ai_evaluation_uid=eval_uid, usage_log_uid=log_uid)
    )

    assert row.pid is not None
    assert row.ai_eval_rerun_uid is not None
    assert row.ai_evaluation_uid == eval_uid
    assert row.rerun_model == "anthropic/claude-3.5"
    assert row.compare_winner == "challenger"
    assert row.compare_score == Decimal("0.875")
    assert await _count_reruns(db_session, eval_uid, "anthropic/claude-3.5") == 1


async def test_create_rerun_is_idempotent_on_eval_uid_and_model(
    db_session: AsyncSession,
) -> None:
    """二次同 (ai_evaluation_uid, rerun_model) → DB 僅一列,回既有列。"""
    repo = AiModelEvalRerunRepository(db_session)
    eval_uid, log_uid = await _insert_evaluation(db_session)

    first = await repo.create_rerun(
        _rerun_input(ai_evaluation_uid=eval_uid, usage_log_uid=log_uid)
    )
    second = await repo.create_rerun(
        _rerun_input(ai_evaluation_uid=eval_uid, usage_log_uid=log_uid)
    )

    assert second.ai_eval_rerun_uid == first.ai_eval_rerun_uid
    assert await _count_reruns(db_session, eval_uid, "anthropic/claude-3.5") == 1


async def test_create_rerun_different_model_writes_second_row(
    db_session: AsyncSession,
) -> None:
    """同 evaluation 不同 rerun_model → 各一列(冪等鍵含 model)。"""
    repo = AiModelEvalRerunRepository(db_session)
    eval_uid, log_uid = await _insert_evaluation(db_session)

    await repo.create_rerun(
        _rerun_input(
            ai_evaluation_uid=eval_uid,
            usage_log_uid=log_uid,
            rerun_model="anthropic/claude-3.5",
        )
    )
    await repo.create_rerun(
        _rerun_input(
            ai_evaluation_uid=eval_uid,
            usage_log_uid=log_uid,
            rerun_model="google/gemini-flash",
        )
    )

    assert await _count_reruns(db_session, eval_uid, "anthropic/claude-3.5") == 1
    assert await _count_reruns(db_session, eval_uid, "google/gemini-flash") == 1


async def test_create_rerun_idempotent_even_when_soft_deleted(
    db_session: AsyncSession,
) -> None:
    """已軟刪列仍命中冪等(UNIQUE 不分軟刪)→ 不重插、回既有軟刪列。"""
    repo = AiModelEvalRerunRepository(db_session)
    eval_uid, log_uid = await _insert_evaluation(db_session)

    first = await repo.create_rerun(
        _rerun_input(ai_evaluation_uid=eval_uid, usage_log_uid=log_uid)
    )
    await db_session.execute(
        update(AiModelEvalRerun)
        .where(AiModelEvalRerun.ai_eval_rerun_uid == first.ai_eval_rerun_uid)
        .values(is_deleted=True)
    )
    await db_session.flush()

    second = await repo.create_rerun(
        _rerun_input(ai_evaluation_uid=eval_uid, usage_log_uid=log_uid)
    )
    assert second.ai_eval_rerun_uid == first.ai_eval_rerun_uid
    assert await _count_reruns(db_session, eval_uid, "anthropic/claude-3.5") == 1


# ── (b) fetch_unreran_evaluation_uids 條件 + FIFO ──────────────────────


async def test_fetch_unreran_returns_only_unreran_evaluated(
    db_session: AsyncSession,
) -> None:
    """只回 ai_reran_at IS NULL 且 status='evaluated' 且未軟刪。"""
    repo = AiModelEvaluationRepository(db_session)

    pending_uid, _ = await _insert_evaluation(db_session, status="evaluated")
    reran_uid, _ = await _insert_evaluation(
        db_session, status="evaluated", ai_reran_at=_now()
    )
    error_uid, _ = await _insert_evaluation(db_session, status="error")
    deleted_uid, _ = await _insert_evaluation(
        db_session, status="evaluated", is_deleted=True
    )

    uids = await repo.fetch_unreran_evaluation_uids(limit=1000)
    assert pending_uid in uids
    assert reran_uid not in uids  # 已重跑
    assert error_uid not in uids  # 非 evaluated
    assert deleted_uid not in uids  # 軟刪


async def test_fetch_unreran_respects_limit(db_session: AsyncSession) -> None:
    repo = AiModelEvaluationRepository(db_session)
    for _ in range(3):
        await _insert_evaluation(db_session, status="evaluated")

    uids = await repo.fetch_unreran_evaluation_uids(limit=2)
    assert len(uids) == 2


async def test_fetch_unreran_is_oldest_first(db_session: AsyncSession) -> None:
    """FIFO(created_at ASC):backlog 公平、不被新進餓死。"""
    repo = AiModelEvaluationRepository(db_session)
    base = datetime(2026, 1, 1, tzinfo=_TPE)
    oldest, _ = await _insert_evaluation(
        db_session, status="evaluated", created_at=base
    )
    middle, _ = await _insert_evaluation(
        db_session, status="evaluated", created_at=base + timedelta(hours=1)
    )
    newest, _ = await _insert_evaluation(
        db_session, status="evaluated", created_at=base + timedelta(hours=2)
    )

    uids = await repo.fetch_unreran_evaluation_uids(limit=1000)
    pos = {uid: i for i, uid in enumerate(uids)}
    assert pos[oldest] < pos[middle] < pos[newest]


# ── (c) mark_reran 終局值 ──────────────────────────────────────────────


async def test_mark_reran_success_sets_status_one_and_excludes(
    db_session: AsyncSession,
) -> None:
    repo = AiModelEvaluationRepository(db_session)
    eval_uid, _ = await _insert_evaluation(db_session, status="evaluated")

    before = await repo.fetch_unreran_evaluation_uids(limit=1000)
    assert eval_uid in before

    await repo.mark_reran(eval_uid, status=1)

    at, st = (
        await db_session.execute(
            select(
                AiModelEvaluation.ai_reran_at, AiModelEvaluation.ai_rerun_status
            ).where(AiModelEvaluation.ai_evaluation_uid == eval_uid)
        )
    ).one()
    assert at is not None
    assert st == 1

    after = await repo.fetch_unreran_evaluation_uids(limit=1000)
    assert eval_uid not in after  # 終局,不重派


async def test_mark_reran_failure_sets_status_zero_and_excludes(
    db_session: AsyncSession,
) -> None:
    """失敗也算「跑過」:ai_reran_at 有值、status=0,不再回派發。"""
    repo = AiModelEvaluationRepository(db_session)
    eval_uid, _ = await _insert_evaluation(db_session, status="evaluated")

    await repo.mark_reran(eval_uid, status=0)

    at, st = (
        await db_session.execute(
            select(
                AiModelEvaluation.ai_reran_at, AiModelEvaluation.ai_rerun_status
            ).where(AiModelEvaluation.ai_evaluation_uid == eval_uid)
        )
    ).one()
    assert at is not None
    assert st == 0

    after = await repo.fetch_unreran_evaluation_uids(limit=1000)
    assert eval_uid not in after


# ── (d) list_by_* 過濾軟刪 ─────────────────────────────────────────────


async def test_list_by_usage_log_uid_filters_soft_deleted(
    db_session: AsyncSession,
) -> None:
    repo = AiModelEvalRerunRepository(db_session)
    eval_uid, log_uid = await _insert_evaluation(db_session)

    live = await repo.create_rerun(
        _rerun_input(
            ai_evaluation_uid=eval_uid,
            usage_log_uid=log_uid,
            rerun_model="anthropic/claude-3.5",
        )
    )
    gone = await repo.create_rerun(
        _rerun_input(
            ai_evaluation_uid=eval_uid,
            usage_log_uid=log_uid,
            rerun_model="google/gemini-flash",
        )
    )
    await db_session.execute(
        update(AiModelEvalRerun)
        .where(AiModelEvalRerun.ai_eval_rerun_uid == gone.ai_eval_rerun_uid)
        .values(is_deleted=True)
    )
    await db_session.flush()

    rows = await repo.list_by_usage_log_uid(log_uid)
    uids = {r.ai_eval_rerun_uid for r in rows}
    assert live.ai_eval_rerun_uid in uids
    assert gone.ai_eval_rerun_uid not in uids


async def test_list_by_evaluation_uid_filters_soft_deleted(
    db_session: AsyncSession,
) -> None:
    repo = AiModelEvalRerunRepository(db_session)
    eval_uid, log_uid = await _insert_evaluation(db_session)

    live = await repo.create_rerun(
        _rerun_input(
            ai_evaluation_uid=eval_uid,
            usage_log_uid=log_uid,
            rerun_model="anthropic/claude-3.5",
        )
    )
    gone = await repo.create_rerun(
        _rerun_input(
            ai_evaluation_uid=eval_uid,
            usage_log_uid=log_uid,
            rerun_model="google/gemini-flash",
        )
    )
    await db_session.execute(
        update(AiModelEvalRerun)
        .where(AiModelEvalRerun.ai_eval_rerun_uid == gone.ai_eval_rerun_uid)
        .values(is_deleted=True)
    )
    await db_session.flush()

    rows = await repo.list_by_evaluation_uid(eval_uid)
    uids = {r.ai_eval_rerun_uid for r in rows}
    assert live.ai_eval_rerun_uid in uids
    assert gone.ai_eval_rerun_uid not in uids


# ── (e) list_grouped_by_usage_log / count_distinct_usage_logs ──────────
# 注意:全表查詢,transaction 內可見 dev DB 既有 committed 列;以遠未來時戳(2099)
# 保證自插組排最前,total/len 用相對(>=)斷言。


def _rerun_at(
    *,
    ai_evaluation_uid: UUID,
    usage_log_uid: UUID,
    rerun_model: str,
    triggered_at: datetime,
) -> RerunInput:
    return RerunInput(
        ai_evaluation_uid=ai_evaluation_uid,
        usage_log_uid=usage_log_uid,
        original_model="openai/gpt-4o",
        rerun_model=rerun_model,
        triggered_at=triggered_at,
        status="success",
    )


async def test_list_grouped_by_usage_log_groups_and_orders(
    db_session: AsyncSession,
) -> None:
    """distinct usage_log 以「組最新 triggered_at」排序;回傳該頁分組鍵 + 底下全部列。"""
    repo = AiModelEvalRerunRepository(db_session)
    base = datetime(2099, 1, 1, 10, 0, 0, tzinfo=_TPE)

    # log_a:組最新 = 10:05;log_b:組最新 = 10:30(較新 → 排在 log_a 前)
    eval_a, log_a = await _insert_evaluation(db_session)
    eval_b, log_b = await _insert_evaluation(db_session)
    await repo.create_rerun(
        _rerun_at(
            ai_evaluation_uid=eval_a,
            usage_log_uid=log_a,
            rerun_model="a/1",
            triggered_at=base.replace(minute=1),
        )
    )
    await repo.create_rerun(
        _rerun_at(
            ai_evaluation_uid=eval_a,
            usage_log_uid=log_a,
            rerun_model="a/2",
            triggered_at=base.replace(minute=5),
        )
    )
    await repo.create_rerun(
        _rerun_at(
            ai_evaluation_uid=eval_b,
            usage_log_uid=log_b,
            rerun_model="b/1",
            triggered_at=base.replace(minute=30),
        )
    )

    uids, rows = await repo.list_grouped_by_usage_log(limit=100, offset=0)
    # log_b(10:30)應排在 log_a(10:05)之前
    pos = {uid: i for i, uid in enumerate(uids)}
    assert pos[log_b] < pos[log_a]
    # 回傳列含這兩組底下全部(a/1, a/2, b/1)
    models_by_log = {log_a: set(), log_b: set()}
    for r in rows:
        if r.usage_log_uid in models_by_log:
            models_by_log[r.usage_log_uid].add(r.rerun_model)
    assert models_by_log[log_a] == {"a/1", "a/2"}
    assert models_by_log[log_b] == {"b/1"}


async def test_list_grouped_by_usage_log_paginates_by_group(
    db_session: AsyncSession,
) -> None:
    """分頁以「組」為單位:limit=1 → 只回最新 1 組的鍵(及其列)。"""
    repo = AiModelEvalRerunRepository(db_session)
    base = datetime(2099, 1, 1, 11, 0, 0, tzinfo=_TPE)
    eval_a, log_a = await _insert_evaluation(db_session)
    eval_b, log_b = await _insert_evaluation(db_session)
    await repo.create_rerun(
        _rerun_at(
            ai_evaluation_uid=eval_a,
            usage_log_uid=log_a,
            rerun_model="a/1",
            triggered_at=base.replace(minute=10),
        )
    )
    await repo.create_rerun(
        _rerun_at(
            ai_evaluation_uid=eval_b,
            usage_log_uid=log_b,
            rerun_model="b/1",
            triggered_at=base.replace(minute=40),
        )
    )

    uids, _rows = await repo.list_grouped_by_usage_log(limit=1, offset=0)
    assert len(uids) == 1
    assert uids[0] == log_b  # 最新組


async def test_list_grouped_excludes_soft_deleted(
    db_session: AsyncSession,
) -> None:
    """軟刪列不參與分組:某組全列軟刪 → 該組不出現、不計入。"""
    repo = AiModelEvalRerunRepository(db_session)
    base = datetime(2099, 1, 1, 12, 0, 0, tzinfo=_TPE)
    eval_uid, log_uid = await _insert_evaluation(db_session)
    gone = await repo.create_rerun(
        _rerun_at(
            ai_evaluation_uid=eval_uid,
            usage_log_uid=log_uid,
            rerun_model="gone/1",
            triggered_at=base.replace(minute=50),
        )
    )
    await db_session.execute(
        update(AiModelEvalRerun)
        .where(AiModelEvalRerun.ai_eval_rerun_uid == gone.ai_eval_rerun_uid)
        .values(is_deleted=True)
    )
    await db_session.flush()

    uids, rows = await repo.list_grouped_by_usage_log(limit=100, offset=0)
    assert log_uid not in uids
    assert all(r.usage_log_uid != log_uid for r in rows)


async def test_count_distinct_usage_logs_counts_groups(
    db_session: AsyncSession,
) -> None:
    """count = distinct usage_log 組數(過濾軟刪);同組多列只算一組。"""
    repo = AiModelEvalRerunRepository(db_session)
    before = await repo.count_distinct_usage_logs()

    base = datetime(2099, 1, 1, 13, 0, 0, tzinfo=_TPE)
    eval_uid, log_uid = await _insert_evaluation(db_session)
    # 同一 usage_log 兩列 → 仍只算一組
    await repo.create_rerun(
        _rerun_at(
            ai_evaluation_uid=eval_uid,
            usage_log_uid=log_uid,
            rerun_model="x/1",
            triggered_at=base.replace(minute=1),
        )
    )
    await repo.create_rerun(
        _rerun_at(
            ai_evaluation_uid=eval_uid,
            usage_log_uid=log_uid,
            rerun_model="x/2",
            triggered_at=base.replace(minute=2),
        )
    )

    after = await repo.count_distinct_usage_logs()
    assert after == before + 1
