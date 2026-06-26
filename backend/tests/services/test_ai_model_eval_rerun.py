"""ai_model_eval_rerun.rerun_evaluation() 整合測試(task-405;對齊 03-backend/07-testing.md)。

策略:
- **真 DB**(禁 mock SQL):連本機測試 Postgres,每測試包外層 transaction,結束 rollback。
- **OpenRouter 走 respx**:以 `respx` 攔截 `/chat/completions`。challenger 與 discriminator
  以 payload 特徵分流(discriminator payload 帶 `response_format.type == 'json_object'`),
  各自回對應假回覆,可斷言去重 / 串行 / 子開關 / 部分失敗 / 成本 delta / 盲化。
  client 為真 `OpenRouterClient` + 真 `httpx.AsyncClient`,故能斷言每次呼叫帶
  `Authorization: Bearer <DEFAULT_OPENROUTER_KEY>`。

DB 不可用時整個模組 skip。
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest
import pytest_asyncio
import respx
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from uuid_utils import uuid7

import app.services.ai_model_eval_rerun as svc
from app.clients.openrouter.client import OpenRouterClient
from app.core.exceptions import AppError
from app.models.ai_model_eval_candidate import AiModelEvalCandidate
from app.models.ai_model_eval_rerun import AiModelEvalRerun
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


def _patch_settings(monkeypatch, *, discriminator: bool) -> None:
    """注入內部呼叫金鑰 + discriminator 子開關(其餘設定無關緊要)。"""
    monkeypatch.setattr(
        svc,
        "get_settings",
        lambda: SimpleNamespace(
            DEFAULT_OPENROUTER_KEY=_TEST_KEY,
            AI_RERUN_DISCRIMINATOR_ENABLED=discriminator,
        ),
    )


def _make_client() -> OpenRouterClient:
    """真 OpenRouterClient + 真 httpx.AsyncClient(供 respx 攔截)。"""
    return OpenRouterClient(httpx.AsyncClient(), _OR_BASE_URL)


async def _add_model(
    session: AsyncSession, *, model_key: str, tier: str | None = None
) -> UUID:
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


async def _add_usage_log(
    session: AsyncSession,
    *,
    model: str,
    cost_usd: Decimal | None,
) -> UUID:
    uid = _new_uid()
    session.add(
        UsageLog(
            usage_log_uid=uid,
            model=model,
            status="success",
            cost_usd=cost_usd if cost_usd is not None else Decimal("0"),
            request_content={"model": model, "text": "幫我把這段會議記錄整理成重點"},
            response_summary={"output_text": "原模型輸出:重點如下 1...2...3"},
        )
    )
    await session.flush()
    return uid


async def _add_parent(
    session: AsyncSession, *, usage_log_uid: UUID, original_model: str
) -> UUID:
    uid = _new_uid()
    session.add(
        AiModelEvaluation(
            ai_evaluation_uid=uid,
            usage_log_uid=usage_log_uid,
            ai_original_model=original_model,
            ai_task_summary="整理會議記錄",
            ai_task_intent="summarization",
            ai_task_complexity="low",
            status="evaluated",
            ai_evaluated_at=datetime.now(UTC),
        )
    )
    await session.flush()
    return uid


async def _add_candidate(
    session: AsyncSession,
    *,
    eval_uid: UUID,
    judge_model_uid: UUID,
    recommend_model: str | None,
) -> UUID:
    uid = _new_uid()
    session.add(
        AiModelEvalCandidate(
            ai_candidate_uid=uid,
            ai_evaluation_uid=eval_uid,
            model_uid=judge_model_uid,
            ai_recommend_model=recommend_model,
            ai_fit_score=Decimal("0.8"),
        )
    )
    await session.flush()
    return uid


@dataclass
class _Seed:
    eval_uid: UUID
    usage_log_uid: UUID
    original_model: str
    judge_keys: list[str]


async def _seed(
    session: AsyncSession,
    *,
    recommends: list[str | None],
    original_cost: Decimal | None = Decimal("0.002000"),
    extra_models: list[str] | None = None,
) -> _Seed:
    """建原模型 + 3 裁判模型 + 1 usage_log + 1 父評審 + 3 候選(各帶 recommends[i])。

    `recommends[i]` 為第 i 個裁判的推薦 model_key(None=未推薦)。所有 model_key 帶 uuid
    後綴避免撞 dev DB 全域 UNIQUE。`extra_models` 為需建入 models 白名單的 challenger key
    (供反查 model_uid;不建則 challenger model_uid 留 None)。
    """
    original_model = _uniq("openai/gpt-orig")
    log_uid = await _add_usage_log(
        session, model=original_model, cost_usd=original_cost
    )
    eval_uid = await _add_parent(
        session, usage_log_uid=log_uid, original_model=original_model
    )

    judge_keys = [
        _uniq("anthropic/claude-judge"),
        _uniq("openai/gpt-judge"),
        _uniq("google/gemini-judge"),
    ]
    judge_uids = [await _add_model(session, model_key=k) for k in judge_keys]

    for key in extra_models or []:
        await _add_model(session, model_key=key)

    for juid, rec in zip(judge_uids, recommends, strict=True):
        await _add_candidate(
            session, eval_uid=eval_uid, judge_model_uid=juid, recommend_model=rec
        )

    return _Seed(
        eval_uid=eval_uid,
        usage_log_uid=log_uid,
        original_model=original_model,
        judge_keys=judge_keys,
    )


def _challenger_response(content: str, *, cost: float, total_tokens: int) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "gen-" + str(uuid7()),
            "choices": [{"message": {"content": content}}],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": total_tokens - 10,
                "total_tokens": total_tokens,
                "cost": cost,
            },
        },
    )


def _discriminator_response(winner: str, score: float, reason: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {"winner": winner, "score": score, "reason": reason},
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        },
    )


def _is_discriminator(request: httpx.Request) -> bool:
    """以 payload 特徵判定:discriminator payload 帶 response_format.type == json_object。"""
    body = json.loads(request.content)
    return (body.get("response_format") or {}).get("type") == "json_object"


async def _list_reruns(
    session: AsyncSession, eval_uid: UUID
) -> list[AiModelEvalRerun]:
    return list(
        (
            await session.execute(
                select(AiModelEvalRerun).where(
                    AiModelEvalRerun.ai_evaluation_uid == eval_uid
                )
            )
        )
        .scalars()
        .all()
    )


async def _get_parent(session: AsyncSession, eval_uid: UUID) -> AiModelEvaluation:
    return (
        await session.execute(
            select(AiModelEvaluation).where(
                AiModelEvaluation.ai_evaluation_uid == eval_uid
            )
        )
    ).scalar_one()


# --- (a) 三裁判推薦同模型 → 去重一筆 ---------------------------------------


@respx.mock(base_url=_OR_BASE_URL)
async def test_dedup_same_recommend_single_rerun(
    respx_mock, db_session: AsyncSession, monkeypatch
) -> None:
    _patch_settings(monkeypatch, discriminator=False)
    challenger = _uniq("anthropic/claude-haiku")
    seed = await _seed(
        db_session,
        recommends=[challenger, challenger, challenger],
        extra_models=[challenger],
    )

    route = respx_mock.post("/chat/completions").mock(
        side_effect=lambda req: _challenger_response(
            "challenger 輸出", cost=0.001, total_tokens=30
        )
    )

    client = _make_client()
    await svc.rerun_evaluation(seed.eval_uid, db=db_session, client=client)
    await client._client.aclose()

    # 去重:三裁判推薦同 challenger → 只一次 challenger 呼叫、只一筆 rerun。
    assert route.call_count == 1
    assert route.calls[0].request.headers["authorization"] == f"Bearer {_TEST_KEY}"
    reruns = await _list_reruns(db_session, seed.eval_uid)
    assert len(reruns) == 1
    assert reruns[0].rerun_model == challenger
    parent = await _get_parent(db_session, seed.eval_uid)
    assert parent.ai_reran_at is not None
    assert parent.ai_rerun_status == 1


# --- (b) 推薦含原模型 → 跳過;全員維持原模型 → 0 筆 + status=1 -----------------


@respx.mock(base_url=_OR_BASE_URL)
async def test_recommend_original_is_skipped(
    respx_mock, db_session: AsyncSession, monkeypatch
) -> None:
    _patch_settings(monkeypatch, discriminator=False)
    challenger = _uniq("anthropic/claude-haiku")
    seed = await _seed(
        db_session,
        recommends=[None, challenger, None],
        extra_models=[challenger],
    )
    # 把第一個裁判改成推薦原模型(應被跳過)。
    seed_recommends = [seed.original_model, challenger, None]
    cands = list(
        (
            await db_session.execute(
                select(AiModelEvalCandidate)
                .where(AiModelEvalCandidate.ai_evaluation_uid == seed.eval_uid)
                .order_by(AiModelEvalCandidate.pid.asc())
            )
        )
        .scalars()
        .all()
    )
    for c, rec in zip(cands, seed_recommends, strict=True):
        c.ai_recommend_model = rec
    await db_session.flush()

    route = respx_mock.post("/chat/completions").mock(
        side_effect=lambda req: _challenger_response(
            "challenger 輸出", cost=0.001, total_tokens=30
        )
    )

    client = _make_client()
    await svc.rerun_evaluation(seed.eval_uid, db=db_session, client=client)
    await client._client.aclose()

    # 推薦原模型 / None 皆跳過 → 只 challenger 一筆。
    assert route.call_count == 1
    reruns = await _list_reruns(db_session, seed.eval_uid)
    assert {r.rerun_model for r in reruns} == {challenger}


@respx.mock(base_url=_OR_BASE_URL, assert_all_called=False)
async def test_all_keep_original_zero_reruns_marks_success(
    respx_mock, db_session: AsyncSession, monkeypatch
) -> None:
    _patch_settings(monkeypatch, discriminator=False)
    seed = await _seed(db_session, recommends=[None, None, None])
    # 全員推薦原模型。
    cands = list(
        (
            await db_session.execute(
                select(AiModelEvalCandidate).where(
                    AiModelEvalCandidate.ai_evaluation_uid == seed.eval_uid
                )
            )
        )
        .scalars()
        .all()
    )
    for c in cands:
        c.ai_recommend_model = seed.original_model
    await db_session.flush()

    route = respx_mock.post("/chat/completions").mock(
        side_effect=lambda req: _challenger_response("x", cost=0.0, total_tokens=10)
    )

    client = _make_client()
    await svc.rerun_evaluation(seed.eval_uid, db=db_session, client=client)
    await client._client.aclose()

    # 無有效 challenger → 0 呼叫、0 筆、標終局 status=1。
    assert route.call_count == 0
    assert await _list_reruns(db_session, seed.eval_uid) == []
    parent = await _get_parent(db_session, seed.eval_uid)
    assert parent.ai_reran_at is not None
    assert parent.ai_rerun_status == 1


# --- (c) discriminator 子開關 -----------------------------------------------


@respx.mock(base_url=_OR_BASE_URL)
async def test_discriminator_disabled_no_compare(
    respx_mock, db_session: AsyncSession, monkeypatch
) -> None:
    _patch_settings(monkeypatch, discriminator=False)
    challenger = _uniq("anthropic/claude-haiku")
    seed = await _seed(
        db_session, recommends=[challenger, None, None], extra_models=[challenger]
    )

    calls: list[bool] = []

    def _handler(req: httpx.Request) -> httpx.Response:
        is_disc = _is_discriminator(req)
        calls.append(is_disc)
        if is_disc:
            return _discriminator_response("B", 0.9, "challenger 較佳")
        return _challenger_response("challenger 輸出", cost=0.001, total_tokens=30)

    respx_mock.post("/chat/completions").mock(side_effect=_handler)

    client = _make_client()
    await svc.rerun_evaluation(seed.eval_uid, db=db_session, client=client)
    await client._client.aclose()

    # 子開關 false → 無 discriminator 呼叫;compare_* 全 NULL。
    assert calls == [False]
    reruns = await _list_reruns(db_session, seed.eval_uid)
    assert len(reruns) == 1
    r = reruns[0]
    assert r.compare_winner is None
    assert r.compare_score is None
    assert r.compare_reason is None
    assert r.compare_judge_model is None


@respx.mock(base_url=_OR_BASE_URL)
async def test_discriminator_enabled_compare_filled_and_blinded(
    respx_mock, db_session: AsyncSession, monkeypatch
) -> None:
    _patch_settings(monkeypatch, discriminator=True)
    challenger = _uniq("anthropic/claude-haiku")
    seed = await _seed(
        db_session, recommends=[challenger, None, None], extra_models=[challenger]
    )
    judge_key = seed.judge_keys[0]  # 推薦該 challenger 的裁判本人

    disc_bodies: list[dict] = []

    def _handler(req: httpx.Request) -> httpx.Response:
        if _is_discriminator(req):
            disc_bodies.append(json.loads(req.content))
            # winner=B、blind_swap=False(A=original,B=challenger)→ challenger 勝。
            return _discriminator_response("B", 0.77, "challenger 更完整")
        return _challenger_response("challenger 輸出", cost=0.001, total_tokens=30)

    respx_mock.post("/chat/completions").mock(side_effect=_handler)

    client = _make_client()
    # 注入固定盲化映射(blind_swap=False:A=original、B=challenger)→ winner=B 映射回 challenger。
    await svc.rerun_evaluation(
        seed.eval_uid, db=db_session, client=client, blind_swap=False
    )
    await client._client.aclose()

    reruns = await _list_reruns(db_session, seed.eval_uid)
    assert len(reruns) == 1
    r = reruns[0]
    assert r.compare_winner == "challenger"
    assert r.compare_score == Decimal("0.770")
    assert r.compare_reason == "challenger 更完整"
    assert r.compare_judge_model == judge_key

    # 盲化:discriminator payload 不得出現任一模型名(原模型 / challenger / 裁判)。
    assert len(disc_bodies) == 1
    payload_text = json.dumps(disc_bodies[0], ensure_ascii=False)
    assert seed.original_model not in payload_text
    assert challenger not in payload_text


@respx.mock(base_url=_OR_BASE_URL)
async def test_discriminator_blind_swap_maps_winner_a_to_challenger(
    respx_mock, db_session: AsyncSession, monkeypatch
) -> None:
    _patch_settings(monkeypatch, discriminator=True)
    challenger = _uniq("anthropic/claude-haiku")
    seed = await _seed(
        db_session, recommends=[challenger, None, None], extra_models=[challenger]
    )

    def _handler(req: httpx.Request) -> httpx.Response:
        if _is_discriminator(req):
            return _discriminator_response("A", 0.6, "A 較佳")
        return _challenger_response("challenger 輸出", cost=0.001, total_tokens=30)

    respx_mock.post("/chat/completions").mock(side_effect=_handler)

    client = _make_client()
    # blind_swap=True:A=challenger、B=original → winner=A 映射回 challenger。
    await svc.rerun_evaluation(
        seed.eval_uid, db=db_session, client=client, blind_swap=True
    )
    await client._client.aclose()

    reruns = await _list_reruns(db_session, seed.eval_uid)
    assert reruns[0].compare_winner == "challenger"


# --- (d) 部分失敗 / 全失敗 ---------------------------------------------------


@respx.mock(base_url=_OR_BASE_URL)
async def test_one_challenger_fails_others_written(
    respx_mock, db_session: AsyncSession, monkeypatch
) -> None:
    _patch_settings(monkeypatch, discriminator=False)
    ch_ok = _uniq("anthropic/claude-haiku")
    ch_fail = _uniq("openai/gpt-mini")
    seed = await _seed(
        db_session,
        recommends=[ch_ok, ch_fail, None],
        extra_models=[ch_ok, ch_fail],
    )

    def _handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        if body.get("model") == ch_fail:
            return httpx.Response(500, text="upstream boom")
        return _challenger_response("ok 輸出", cost=0.001, total_tokens=30)

    respx_mock.post("/chat/completions").mock(side_effect=_handler)

    client = _make_client()
    await svc.rerun_evaluation(seed.eval_uid, db=db_session, client=client)
    await client._client.aclose()

    reruns = {r.rerun_model: r for r in await _list_reruns(db_session, seed.eval_uid)}
    # 兩筆都寫;失敗筆 status='error',成功筆 status='success'。
    assert set(reruns) == {ch_ok, ch_fail}
    assert reruns[ch_ok].status == "success"
    assert reruns[ch_fail].status == "error"
    assert reruns[ch_fail].error_code == "challenger_failed"
    # ≥1 成功 → 父 status=1。
    parent = await _get_parent(db_session, seed.eval_uid)
    assert parent.ai_rerun_status == 1


@respx.mock(base_url=_OR_BASE_URL)
async def test_all_challengers_fail_marks_status_zero(
    respx_mock, db_session: AsyncSession, monkeypatch
) -> None:
    _patch_settings(monkeypatch, discriminator=False)
    ch1 = _uniq("anthropic/claude-haiku")
    ch2 = _uniq("openai/gpt-mini")
    seed = await _seed(
        db_session, recommends=[ch1, ch2, None], extra_models=[ch1, ch2]
    )

    respx_mock.post("/chat/completions").mock(
        side_effect=lambda req: httpx.Response(503, text="down")
    )

    client = _make_client()
    await svc.rerun_evaluation(seed.eval_uid, db=db_session, client=client)
    await client._client.aclose()

    reruns = await _list_reruns(db_session, seed.eval_uid)
    assert len(reruns) == 2
    assert all(r.status == "error" for r in reruns)
    parent = await _get_parent(db_session, seed.eval_uid)
    assert parent.ai_reran_at is not None
    assert parent.ai_rerun_status == 0


# --- (e) cost_delta -------------------------------------------------------


@respx.mock(base_url=_OR_BASE_URL)
async def test_cost_delta_computed(
    respx_mock, db_session: AsyncSession, monkeypatch
) -> None:
    _patch_settings(monkeypatch, discriminator=False)
    challenger = _uniq("anthropic/claude-haiku")
    seed = await _seed(
        db_session,
        recommends=[challenger, None, None],
        original_cost=Decimal("0.002000"),
        extra_models=[challenger],
    )

    respx_mock.post("/chat/completions").mock(
        side_effect=lambda req: _challenger_response(
            "out", cost=0.000500, total_tokens=30
        )
    )

    client = _make_client()
    await svc.rerun_evaluation(seed.eval_uid, db=db_session, client=client)
    await client._client.aclose()

    r = (await _list_reruns(db_session, seed.eval_uid))[0]
    assert r.cost_usd == Decimal("0.000500")
    assert r.original_cost_usd == Decimal("0.002000")
    # delta = challenger − original = 0.0005 − 0.002 = -0.0015。
    assert r.cost_delta_usd == Decimal("-0.001500")


@respx.mock(base_url=_OR_BASE_URL)
async def test_cost_delta_null_when_challenger_cost_missing(
    respx_mock, db_session: AsyncSession, monkeypatch
) -> None:
    """challenger 回應無 cost / total_cost → cost_usd NULL → cost_delta NULL(決議 §5.2)。

    (`usage_logs.cost_usd` 為 NOT NULL,原成本恆有值;NULL delta 的實際成因為
    challenger 端回應未帶成本。)
    """
    _patch_settings(monkeypatch, discriminator=False)
    challenger = _uniq("anthropic/claude-haiku")
    seed = await _seed(
        db_session,
        recommends=[challenger, None, None],
        original_cost=Decimal("0.002000"),
        extra_models=[challenger],
    )

    # 無 usage.cost / total_cost 的 challenger 回應。
    no_cost_resp = httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": "out"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        },
    )
    respx_mock.post("/chat/completions").mock(side_effect=lambda req: no_cost_resp)

    client = _make_client()
    await svc.rerun_evaluation(seed.eval_uid, db=db_session, client=client)
    await client._client.aclose()

    r = (await _list_reruns(db_session, seed.eval_uid))[0]
    assert r.cost_usd is None
    assert r.original_cost_usd == Decimal("0.002000")
    assert r.cost_delta_usd is None


# --- 前置條件 / 錯誤收斂 ----------------------------------------------------


async def test_missing_parent_raises_app_error(
    db_session: AsyncSession, monkeypatch
) -> None:
    _patch_settings(monkeypatch, discriminator=False)
    client = _make_client()
    with pytest.raises(AppError):
        await svc.rerun_evaluation(_new_uid(), db=db_session, client=client)
    await client._client.aclose()


async def test_missing_api_key_raises_app_error(
    db_session: AsyncSession, monkeypatch
) -> None:
    monkeypatch.setattr(
        svc,
        "get_settings",
        lambda: SimpleNamespace(
            DEFAULT_OPENROUTER_KEY="", AI_RERUN_DISCRIMINATOR_ENABLED=True
        ),
    )
    client = _make_client()
    with pytest.raises(AppError):
        await svc.rerun_evaluation(_new_uid(), db=db_session, client=client)
    await client._client.aclose()
