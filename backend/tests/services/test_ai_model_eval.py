"""ai_model_eval.evaluate_usage_log() 整合測試(task-105;對齊 03-backend/07-testing.md)。

策略:
- **真 DB**(禁 mock SQL):連本機測試 Postgres,每測試包外層 transaction,結束 rollback。
- **OpenRouter 走 respx**:以 `respx` 攔截 `/chat/completions`,依序回三次回應
  (可指定某次失敗以驗「單評審失敗不阻斷其他」)。client 為真 `OpenRouterClient` +
  真 `httpx.AsyncClient`,故能斷言每次呼叫帶 `Authorization: Bearer <DEFAULT_OPENROUTER_KEY>`。

DB 不可用時整個模組 skip。
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest
import pytest_asyncio
import respx
from sqlalchemy import delete, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from uuid_utils import uuid7

import app.services.ai_model_eval as svc
from app.clients.openrouter.client import OpenRouterClient
from app.core.exceptions import AppError
from app.models.ai_eval_judge_setting import AiEvalJudgeSetting
from app.models.ai_model_eval_candidate import AiModelEvalCandidate
from app.models.ai_model_evaluation import AiModelEvaluation
from app.models.model import Model
from app.models.usage_log import UsageLog

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://ord:ord_dev_pass_change_me@localhost:5533/ord",
)

_OR_BASE_URL = "https://openrouter.test/api/v1"
_TEST_KEY = "sk-default-internal-test"


def _new_uid() -> UUID:
    return UUID(str(uuid7()))


def _uniq(prefix: str) -> str:
    """產生全域唯一 model_key(`models.model_key` 有不分軟刪的 DB UNIQUE,避免撞 dev 資料)。"""
    return f"{prefix}-{uuid7()!s}"


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


@pytest.fixture
def patched_settings(monkeypatch) -> None:
    """注入內部呼叫金鑰(其餘設定無關緊要)。"""
    monkeypatch.setattr(
        svc,
        "get_settings",
        lambda: SimpleNamespace(DEFAULT_OPENROUTER_KEY=_TEST_KEY),
    )


def _make_client() -> OpenRouterClient:
    """真 OpenRouterClient + 真 httpx.AsyncClient(供 respx 攔截)。"""
    return OpenRouterClient(httpx.AsyncClient(), _OR_BASE_URL)


async def _add_model(session: AsyncSession, *, model_key: str, tier: str | None) -> UUID:
    uid = _new_uid()
    session.add(
        Model(
            model_uid=uid,
            provider="openrouter",
            model_key=model_key,
            name=model_key,
            is_active=True,
            tier_key=tier,
            last_synced_at=datetime.now(UTC),
        )
    )
    await session.flush()
    return uid


async def _add_judge(session: AsyncSession, *, model_uid: UUID, slot: int) -> None:
    session.add(
        AiEvalJudgeSetting(
            ai_judge_setting_uid=_new_uid(),
            model_uid=model_uid,
            ai_judge_slot=slot,
            is_active=True,
        )
    )
    await session.flush()


async def _add_usage_log(
    session: AsyncSession, *, model: str = "openai/gpt-4o"
) -> UUID:
    uid = _new_uid()
    session.add(
        UsageLog(
            usage_log_uid=uid,
            model=model,
            status="success",
            request_content={"model": model, "text": "幫我把這段會議記錄整理成重點"},
            response_summary={"output_text": "重點如下:1...2...3..."},
        )
    )
    await session.flush()
    return uid


@dataclass
class _Seed:
    log_uid: UUID
    judge_keys: list[str]
    recommend_key: str  # 額外白名單候選(tier=low),供 dim4 推薦與 tier 反查


async def _seed(session: AsyncSession) -> _Seed:
    """建 3 判別模型(同時也是 active 白名單成員)+ 3 judge settings + 1 usage_log。

    所有 model_key 帶 uuid 後綴,避免撞 dev DB 既有資料的全域 UNIQUE。
    `ai_judge_slot` 為不分軟刪的 DB UNIQUE,dev DB 可能已佔用 slot 1/2/3,故先於本測試
    transaction 內實刪既有 judge settings(teardown rollback 會還原,不污染 dev DB)。
    """
    await session.execute(delete(AiEvalJudgeSetting))
    await session.flush()

    judge_keys = [
        _uniq("anthropic/claude-judge"),
        _uniq("openai/gpt-judge"),
        _uniq("google/gemini-judge"),
    ]
    tiers = ["high", "mid", "low"]
    judge_uids = [
        await _add_model(session, model_key=k, tier=t)
        for k, t in zip(judge_keys, tiers, strict=True)
    ]
    # 額外白名單候選(供 dim4 推薦),含可反查 tier 的目標。
    recommend_key = _uniq("anthropic/claude-haiku")
    await _add_model(session, model_key=recommend_key, tier="low")
    for i, muid in enumerate(judge_uids, start=1):
        await _add_judge(session, model_uid=muid, slot=i)
    log_uid = await _add_usage_log(session)
    return _Seed(log_uid=log_uid, judge_keys=judge_keys, recommend_key=recommend_key)


def _judge_payload(recommend_model: str) -> str:
    return json.dumps(
        {
            "task_summary": "整理會議記錄",
            "task_intent": "summarization",
            "task_complexity": "low",
            "output_fit": {"score": 0.8, "reason": "涵蓋重點"},
            "recommend": {"model": recommend_model, "reason": "更省"},
        },
        ensure_ascii=False,
    )


def _ok_response(content: str) -> httpx.Response:
    return httpx.Response(
        200, json={"choices": [{"message": {"content": content}}]}
    )


async def _count_usage_logs(session: AsyncSession) -> int:
    return int(
        (await session.execute(select(func.count(UsageLog.pid)))).scalar_one()
    )


async def _get_parent(
    session: AsyncSession, log_uid: UUID
) -> AiModelEvaluation | None:
    return (
        await session.execute(
            select(AiModelEvaluation).where(
                AiModelEvaluation.usage_log_uid == log_uid
            )
        )
    ).scalar_one_or_none()


async def _list_candidates(
    session: AsyncSession, eval_uid: UUID
) -> list[AiModelEvalCandidate]:
    return list(
        (
            await session.execute(
                select(AiModelEvalCandidate).where(
                    AiModelEvalCandidate.ai_evaluation_uid == eval_uid
                )
            )
        )
        .scalars()
        .all()
    )


@respx.mock(base_url=_OR_BASE_URL)
async def test_all_three_succeed(
    respx_mock, db_session: AsyncSession, patched_settings
) -> None:
    seed = await _seed(db_session)
    log_uid = seed.log_uid
    before_logs = await _count_usage_logs(db_session)

    route = respx_mock.post("/chat/completions").mock(
        side_effect=[
            _ok_response(_judge_payload(seed.recommend_key)),
            _ok_response(_judge_payload(seed.judge_keys[1])),
            _ok_response(_judge_payload(seed.judge_keys[2])),
        ]
    )

    client = _make_client()
    await svc.evaluate_usage_log(log_uid, db=db_session, client=client)
    await client._client.aclose()

    # 三次呼叫、皆帶 DEFAULT_OPENROUTER_KEY。
    assert route.call_count == 3
    for call in route.calls:
        assert call.request.headers["authorization"] == f"Bearer {_TEST_KEY}"

    parent = await _get_parent(db_session, log_uid)
    assert parent is not None
    assert parent.status == "evaluated"
    assert parent.ai_evaluated_at is not None
    cands = await _list_candidates(db_session, parent.ai_evaluation_uid)
    assert len(cands) == 3
    # dim4 tier 由所選 recommend model 反查 models 白名單。
    haiku_cand = next(
        c for c in cands if c.ai_recommend_model == seed.recommend_key
    )
    assert haiku_cand.ai_recommend_tier == "low"

    # usage_log 派發游標已標(at 有值 + status=1 成功)、且未新增任何 usage_logs。
    at, st = (
        await db_session.execute(
            select(UsageLog.ai_evaluated_at, UsageLog.ai_evaluated_status).where(
                UsageLog.usage_log_uid == log_uid
            )
        )
    ).one()
    assert at is not None
    assert st == 1
    assert await _count_usage_logs(db_session) == before_logs


@respx.mock(base_url=_OR_BASE_URL)
async def test_one_fails_two_succeed(
    respx_mock, db_session: AsyncSession, patched_settings
) -> None:
    seed = await _seed(db_session)
    log_uid = seed.log_uid

    route = respx_mock.post("/chat/completions").mock(
        side_effect=[
            _ok_response(_judge_payload(seed.recommend_key)),
            httpx.Response(500, text="upstream boom"),  # 第二評審失敗
            _ok_response(_judge_payload(seed.judge_keys[2])),
        ]
    )

    client = _make_client()
    await svc.evaluate_usage_log(log_uid, db=db_session, client=client)
    await client._client.aclose()

    assert route.call_count == 3

    parent = await _get_parent(db_session, log_uid)
    assert parent is not None
    # partial(≥1 成功)→ 父 status='evaluated'(非 error)。
    assert parent.status == "evaluated"
    assert parent.ai_evaluated_at is not None

    # 游標:partial 視為成功(ai_evaluated_status=1)。
    at, st = (
        await db_session.execute(
            select(UsageLog.ai_evaluated_at, UsageLog.ai_evaluated_status).where(
                UsageLog.usage_log_uid == log_uid
            )
        )
    ).one()
    assert at is not None
    assert st == 1

    cands = await _list_candidates(db_session, parent.ai_evaluation_uid)
    assert len(cands) == 3
    # 失敗評審該子列標記:AI 欄位皆 None(僅占位 model_uid)。
    failed = [c for c in cands if c.ai_recommend_model is None]
    succeeded = [c for c in cands if c.ai_recommend_model is not None]
    assert len(failed) == 1
    assert len(succeeded) == 2
    assert failed[0].ai_fit_score is None
    assert failed[0].ai_self_vote is None


@respx.mock(base_url=_OR_BASE_URL)
async def test_all_three_fail_sets_error_status(
    respx_mock, db_session: AsyncSession, patched_settings
) -> None:
    seed = await _seed(db_session)
    log_uid = seed.log_uid

    route = respx_mock.post("/chat/completions").mock(
        side_effect=[
            httpx.Response(500, text="boom1"),
            httpx.Response(502, text="boom2"),
            httpx.Response(503, text="boom3"),
        ]
    )

    client = _make_client()
    await svc.evaluate_usage_log(log_uid, db=db_session, client=client)
    await client._client.aclose()

    assert route.call_count == 3

    parent = await _get_parent(db_session, log_uid)
    assert parent is not None
    # 三方全失敗 → 父 status='error',ai_evaluated_at 也標(終局,不重派)。
    assert parent.status == "error"
    assert parent.ai_evaluated_at is not None

    # 游標:失敗也算「跑過」→ at 有值 + status=0(失敗);dispatcher 不重撈。
    at, st = (
        await db_session.execute(
            select(UsageLog.ai_evaluated_at, UsageLog.ai_evaluated_status).where(
                UsageLog.usage_log_uid == log_uid
            )
        )
    ).one()
    assert at is not None
    assert st == 0

    cands = await _list_candidates(db_session, parent.ai_evaluation_uid)
    assert len(cands) == 3
    assert all(c.ai_recommend_model is None for c in cands)


@respx.mock(base_url=_OR_BASE_URL)
async def test_no_judge_settings_raises_app_error(
    respx_mock, db_session: AsyncSession, patched_settings
) -> None:
    # 只建 usage_log,不建判別模型設定(先清掉 dev DB 既有 judge settings)。
    await db_session.execute(delete(AiEvalJudgeSetting))
    await db_session.flush()
    log_uid = await _add_usage_log(db_session)

    client = _make_client()
    with pytest.raises(AppError):
        await svc.evaluate_usage_log(log_uid, db=db_session, client=client)
    await client._client.aclose()


async def test_self_vote_same_vendor() -> None:
    # 推薦與原模型同廠商前綴 → True;不同 → False;無前綴 → None。
    assert svc._compute_self_vote("openai/gpt-4o-mini", "openai/gpt-4o") is True
    assert svc._compute_self_vote("anthropic/claude-3.5", "openai/gpt-4o") is False
    assert svc._compute_self_vote(None, "openai/gpt-4o") is None
    assert svc._compute_self_vote("openai/gpt-4o", "noslashmodel") is None
