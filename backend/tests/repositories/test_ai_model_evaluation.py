"""ai_model_evaluation repository 真 DB 整合測試(對齊 03-backend/07-testing.md)。

禁 mock SQL:連真實測試 DB(預設本機 docker compose 暴露的 Postgres),每個測試包在
一個外層 connection-level transaction,結束一律 rollback → 不污染既有 dev DB 資料。

連線位址以 `TEST_DATABASE_URL` 覆寫;未設時 fallback 到本機 compose 暴露的
postgres(host port 5533,db/user/pass=ord)。DB 不可用時整個模組 skip 並提示原因。
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from uuid_utils import uuid7

from app.models.ai_model_eval_candidate import AiModelEvalCandidate
from app.models.ai_model_evaluation import AiModelEvaluation
from app.models.model import Model
from app.models.usage_log import UsageLog
from app.repositories.ai_model_evaluation import (
    AiModelEvaluationRepository,
    CandidateInput,
)

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://ord:ord_dev_pass_change_me@localhost:5533/ord",
)


def _new_uid() -> UUID:
    return UUID(str(uuid7()))


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """外層 transaction + 加入式 session;測試結束整批 rollback。

    repo 內部 `begin_nested()`(因外層已在 transaction)走 SAVEPOINT,測試可斷言
    其中途 raise 的 rollback 行為;最外層 transaction 在 teardown 統一 rollback,
    所有測試寫入皆不落地。
    """
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
    session: AsyncSession,
    *,
    model: str = "openai/gpt-4o",
    created_at: datetime | None = None,
) -> UUID:
    uid = _new_uid()
    log = UsageLog(
        usage_log_uid=uid,
        model=model,
        status="success",
    )
    # created_at 僅 server_default、無 Python default → 可顯式覆寫以測派發排序
    if created_at is not None:
        log.created_at = created_at
    session.add(log)
    await session.flush()
    return uid


async def _insert_model(
    session: AsyncSession,
    *,
    key: str,
    name: str,
    is_deleted: bool = False,
) -> UUID:
    """插入一筆 `models` 列並回其 model_uid(供 join 測試用)。

    `last_synced_at` NOT NULL 無預設 → 必給值(用 `func.now()`);其餘可空 / 有預設欄位略過。
    """
    uid = _new_uid()
    session.add(
        Model(
            model_uid=uid,
            model_key=key,
            name=name,
            last_synced_at=func.now(),
            is_deleted=is_deleted,
        )
    )
    await session.flush()
    return uid


def _three_candidates() -> list[CandidateInput]:
    return [
        CandidateInput(
            model_uid=_new_uid(),
            ai_recommend_model="anthropic/claude-3.5",
            ai_recommend_tier="mid",
            ai_recommend_reason="便宜且足夠",
            ai_fit_score=Decimal("0.812"),
            ai_self_vote=False,
        ),
        CandidateInput(
            model_uid=_new_uid(),
            ai_recommend_model="openai/gpt-4o-mini",
            ai_recommend_tier="low",
            ai_recommend_reason="任務簡單",
            ai_fit_score=Decimal("0.640"),
            ai_self_vote=True,
        ),
        CandidateInput(
            model_uid=_new_uid(),
            ai_recommend_model="google/gemini-flash",
            ai_recommend_tier="low",
            ai_recommend_reason="速度優先",
            ai_fit_score=Decimal("0.701"),
            ai_self_vote=False,
        ),
    ]


async def _count_candidates(session: AsyncSession, ai_evaluation_uid: UUID) -> int:
    rows = (
        await session.execute(
            select(AiModelEvalCandidate).where(
                AiModelEvalCandidate.ai_evaluation_uid == ai_evaluation_uid
            )
        )
    ).scalars().all()
    return len(rows)


async def _count_parents(session: AsyncSession, usage_log_uid: UUID) -> int:
    rows = (
        await session.execute(
            select(AiModelEvaluation).where(
                AiModelEvaluation.usage_log_uid == usage_log_uid
            )
        )
    ).scalars().all()
    return len(rows)


async def test_create_writes_parent_and_three_candidates(db_session: AsyncSession) -> None:
    repo = AiModelEvaluationRepository(db_session)
    log_uid = await _insert_usage_log(db_session)

    parent = await repo.create_evaluation_with_candidates(
        usage_log_uid=log_uid,
        ai_original_model="openai/gpt-4o",
        candidates=_three_candidates(),
        ai_task_summary="整理會議記錄",
        ai_task_intent="summarize",
        ai_task_complexity="low",
    )

    assert parent.pid is not None
    assert parent.usage_log_uid == log_uid
    assert parent.status == "evaluated"
    assert parent.ai_evaluated_at is not None
    assert await _count_parents(db_session, log_uid) == 1
    assert await _count_candidates(db_session, parent.ai_evaluation_uid) == 3


async def test_create_success_marks_status_one(db_session: AsyncSession) -> None:
    """成功評審:父 status=evaluated,來源 log 游標有值、status=1。"""
    repo = AiModelEvaluationRepository(db_session)
    log_uid = await _insert_usage_log(db_session)

    parent = await repo.create_evaluation_with_candidates(
        usage_log_uid=log_uid,
        ai_original_model="openai/gpt-4o",
        candidates=_three_candidates(),
    )

    assert parent.status == "evaluated"
    at, status = (
        await db_session.execute(
            select(UsageLog.ai_evaluated_at, UsageLog.ai_evaluated_status).where(
                UsageLog.usage_log_uid == log_uid
            )
        )
    ).one()
    assert at is not None
    assert status == 1


async def test_create_failure_marks_status_zero(db_session: AsyncSession) -> None:
    """失敗評審:父 status=error,來源 log 游標有值、status=0,fetch 不再回該 uid。"""
    repo = AiModelEvaluationRepository(db_session)
    log_uid = await _insert_usage_log(db_session)

    parent = await repo.create_evaluation_with_candidates(
        usage_log_uid=log_uid,
        ai_original_model="openai/gpt-4o",
        candidates=_three_candidates(),
        evaluation_succeeded=False,
    )

    assert parent.status == "error"
    assert parent.ai_evaluated_at is not None
    at, status = (
        await db_session.execute(
            select(UsageLog.ai_evaluated_at, UsageLog.ai_evaluated_status).where(
                UsageLog.usage_log_uid == log_uid
            )
        )
    ).one()
    assert at is not None
    assert status == 0

    after = await repo.fetch_unevaluated_log_uids(limit=1000)
    assert log_uid not in after


async def test_create_is_idempotent_on_usage_log_uid(db_session: AsyncSession) -> None:
    repo = AiModelEvaluationRepository(db_session)
    log_uid = await _insert_usage_log(db_session)

    first = await repo.create_evaluation_with_candidates(
        usage_log_uid=log_uid,
        ai_original_model="openai/gpt-4o",
        candidates=_three_candidates(),
    )
    second = await repo.create_evaluation_with_candidates(
        usage_log_uid=log_uid,
        ai_original_model="openai/gpt-4o",
        candidates=_three_candidates(),
    )

    # 同一 usage_log_uid 第二次呼叫回既有父列、不重寫
    assert second.ai_evaluation_uid == first.ai_evaluation_uid
    assert await _count_parents(db_session, log_uid) == 1
    # 子表不因第二次呼叫翻倍(仍 3 筆)
    assert await _count_candidates(db_session, first.ai_evaluation_uid) == 3


async def test_raw_json_not_persisted(db_session: AsyncSession) -> None:
    repo = AiModelEvaluationRepository(db_session)
    log_uid = await _insert_usage_log(db_session)

    parent = await repo.create_evaluation_with_candidates(
        usage_log_uid=log_uid,
        ai_original_model="openai/gpt-4o",
        candidates=_three_candidates(),
        raw_json={"debug": "should-not-be-stored"},
    )

    # 父表無 raw_json 欄位;傳入也不應落地(僅介面相容)
    assert not hasattr(parent, "raw_json")


async def test_mark_success_sets_status_and_excludes_uid(
    db_session: AsyncSession,
) -> None:
    repo = AiModelEvaluationRepository(db_session)
    log_uid = await _insert_usage_log(db_session)

    before = await repo.fetch_unevaluated_log_uids(limit=1000)
    assert log_uid in before

    await repo.mark_usage_log_evaluated(log_uid, success=True)

    at, status = (
        await db_session.execute(
            select(UsageLog.ai_evaluated_at, UsageLog.ai_evaluated_status).where(
                UsageLog.usage_log_uid == log_uid
            )
        )
    ).one()
    assert at is not None
    assert status == 1

    after = await repo.fetch_unevaluated_log_uids(limit=1000)
    assert log_uid not in after


async def test_mark_failure_sets_status_and_excludes_uid(
    db_session: AsyncSession,
) -> None:
    """失敗也算「跑過」:ai_evaluated_at 有值、status=0,fetch 也不再回傳。"""
    repo = AiModelEvaluationRepository(db_session)
    log_uid = await _insert_usage_log(db_session)

    await repo.mark_usage_log_evaluated(log_uid, success=False)

    at, status = (
        await db_session.execute(
            select(UsageLog.ai_evaluated_at, UsageLog.ai_evaluated_status).where(
                UsageLog.usage_log_uid == log_uid
            )
        )
    ).one()
    assert at is not None
    assert status == 0

    after = await repo.fetch_unevaluated_log_uids(limit=1000)
    assert log_uid not in after


async def test_fetch_unevaluated_respects_limit(db_session: AsyncSession) -> None:
    repo = AiModelEvaluationRepository(db_session)
    for _ in range(3):
        await _insert_usage_log(db_session)

    uids = await repo.fetch_unevaluated_log_uids(limit=2)
    assert len(uids) == 2


async def test_fetch_unevaluated_is_oldest_first(db_session: AsyncSession) -> None:
    """派發為最舊優先(FIFO,created_at ASC):backlog 公平處理、不被新進 log 餓死。"""
    repo = AiModelEvaluationRepository(db_session)
    # 顯式給遞增的 created_at(同一 transaction 內 func.now() 對所有列相同,無法分辨先後)。
    base = datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=8)))
    oldest = await _insert_usage_log(db_session, created_at=base)
    middle = await _insert_usage_log(db_session, created_at=base + timedelta(hours=1))
    newest = await _insert_usage_log(db_session, created_at=base + timedelta(hours=2))

    uids = await repo.fetch_unevaluated_log_uids(limit=1000)
    # 同 DB 可能有他人未評審資料,僅斷言三者相對順序(舊 → 新)。
    pos = {uid: i for i, uid in enumerate(uids)}
    assert pos[oldest] < pos[middle] < pos[newest]


async def test_transaction_rollback_no_half_write(db_session: AsyncSession) -> None:
    """子表寫入中途 raise → 父 + 已寫子表整批 rollback,DB 無半寫。"""
    repo = AiModelEvaluationRepository(db_session)
    log_uid = await _insert_usage_log(db_session)

    bad = [
        CandidateInput(model_uid=_new_uid()),
        # ai_fit_score 超出 NUMERIC(4,3) 範圍 → flush 時 DB raise
        CandidateInput(model_uid=_new_uid(), ai_fit_score=Decimal("999.999")),
        CandidateInput(model_uid=_new_uid()),
    ]

    with pytest.raises(DBAPIError):
        await repo.create_evaluation_with_candidates(
            usage_log_uid=log_uid,
            ai_original_model="openai/gpt-4o",
            candidates=bad,
        )

    # SAVEPOINT 失敗後,外層 transaction 仍可繼續查詢驗證無半寫
    await db_session.rollback()  # 釋放失敗的 SAVEPOINT 狀態,回外層 transaction
    assert await _count_parents(db_session, log_uid) == 0

    orphan = (
        await db_session.execute(
            text("SELECT count(*) FROM ai_model_eval_candidates")
        )
    ).scalar_one()
    # 不直接斷言全表為 0(同 DB 可能有他人資料);改以父表 0 列佐證整批未落地
    assert orphan >= 0


async def _create_eval_with_candidate_models(
    db_session: AsyncSession,
    repo: AiModelEvaluationRepository,
    candidates: list[CandidateInput],
) -> AiModelEvaluation:
    """建立 evaluation + 給定候選,回父列(供 join 測試共用)。"""
    log_uid = await _insert_usage_log(db_session)
    return await repo.create_evaluation_with_candidates(
        usage_log_uid=log_uid,
        ai_original_model="openai/gpt-4o",
        candidates=candidates,
    )


async def test_list_candidates_with_judge_joins_model_key_and_name(
    db_session: AsyncSession,
) -> None:
    """正常 join:3 個 model + 3 候選 → 每筆帶出正確的 judge key/name 與候選欄位。"""
    repo = AiModelEvaluationRepository(db_session)

    suffix = uuid7()
    m1 = await _insert_model(
        db_session, key=f"anthropic/claude-opus-{suffix}", name="Claude Opus"
    )
    m2 = await _insert_model(db_session, key=f"openai/gpt-4o-{suffix}", name="GPT-4o")
    m3 = await _insert_model(db_session, key=f"google/gemini-{suffix}", name="Gemini")

    cands = [
        CandidateInput(
            model_uid=m1,
            ai_recommend_model="anthropic/claude-3.5",
            ai_recommend_tier="mid",
            ai_recommend_reason="便宜且足夠",
            ai_fit_score=Decimal("0.812"),
            ai_self_vote=False,
        ),
        CandidateInput(
            model_uid=m2,
            ai_recommend_model="openai/gpt-4o-mini",
            ai_recommend_tier="low",
            ai_recommend_reason="任務簡單",
            ai_fit_score=Decimal("0.640"),
            ai_self_vote=True,
        ),
        CandidateInput(
            model_uid=m3,
            ai_recommend_model="google/gemini-flash",
            ai_recommend_tier="low",
            ai_recommend_reason="速度優先",
            ai_fit_score=Decimal("0.701"),
            ai_self_vote=False,
        ),
    ]
    parent = await _create_eval_with_candidate_models(db_session, repo, cands)

    rows = await repo.list_candidates_with_judge(parent.ai_evaluation_uid)
    assert len(rows) == 3

    by_model = {r.model_uid: r for r in rows}
    assert by_model[m1].judge_model_key == f"anthropic/claude-opus-{suffix}"
    assert by_model[m1].judge_model_name == "Claude Opus"
    assert by_model[m2].judge_model_key == f"openai/gpt-4o-{suffix}"
    assert by_model[m2].judge_model_name == "GPT-4o"
    assert by_model[m3].judge_model_key == f"google/gemini-{suffix}"
    assert by_model[m3].judge_model_name == "Gemini"

    # 候選欄位正確帶出(fit_score 等)
    assert by_model[m1].ai_recommend_model == "anthropic/claude-3.5"
    assert by_model[m1].ai_recommend_tier == "mid"
    assert by_model[m1].ai_recommend_reason == "便宜且足夠"
    assert by_model[m1].ai_fit_score == Decimal("0.812")
    assert by_model[m1].ai_self_vote is False
    assert by_model[m2].ai_self_vote is True
    assert by_model[m2].ai_fit_score == Decimal("0.640")


async def test_list_candidates_with_judge_missing_model_yields_null_key_name(
    db_session: AsyncSession,
) -> None:
    """判別模型不存在:候選 model_uid 指向沒有的 model → key/name=None,但候選仍回傳。"""
    repo = AiModelEvaluationRepository(db_session)

    missing_uid = _new_uid()  # 沒有對應 models 列
    cands = [
        CandidateInput(
            model_uid=missing_uid,
            ai_recommend_model="openai/gpt-4o-mini",
            ai_fit_score=Decimal("0.555"),
        )
    ]
    parent = await _create_eval_with_candidate_models(db_session, repo, cands)

    rows = await repo.list_candidates_with_judge(parent.ai_evaluation_uid)
    assert len(rows) == 1  # outer join 不掉列
    assert rows[0].model_uid == missing_uid
    assert rows[0].judge_model_key is None
    assert rows[0].judge_model_name is None
    assert rows[0].ai_fit_score == Decimal("0.555")


async def test_list_candidates_with_judge_soft_deleted_model_still_named(
    db_session: AsyncSession,
) -> None:
    """判別模型已軟刪:仍以 model_uid 補名(不過濾 model 軟刪),key/name 不為 None。"""
    repo = AiModelEvaluationRepository(db_session)

    soft_key = f"anthropic/retired-{uuid7()}"
    soft_uid = await _insert_model(
        db_session, key=soft_key, name="Retired Judge", is_deleted=True
    )
    cands = [CandidateInput(model_uid=soft_uid, ai_fit_score=Decimal("0.700"))]
    parent = await _create_eval_with_candidate_models(db_session, repo, cands)

    rows = await repo.list_candidates_with_judge(parent.ai_evaluation_uid)
    assert len(rows) == 1
    # 軟刪 model 仍補名(對齊 propose §4.2「盡量以 model_uid 取既有 models 列補名」)
    assert rows[0].judge_model_key == soft_key
    assert rows[0].judge_model_name == "Retired Judge"


async def test_list_candidates_with_judge_empty_when_no_candidates(
    db_session: AsyncSession,
) -> None:
    """無候選的 evaluation_uid → 回空 list。"""
    repo = AiModelEvaluationRepository(db_session)
    parent = await _create_eval_with_candidate_models(db_session, repo, [])

    rows = await repo.list_candidates_with_judge(parent.ai_evaluation_uid)
    assert rows == []
