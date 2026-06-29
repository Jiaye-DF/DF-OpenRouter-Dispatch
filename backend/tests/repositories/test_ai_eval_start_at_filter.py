"""AI 分析起始時間門檻(AI_EVAL_START_AT)真 DB 過濾測試。

證明 repository 撈取會以 `usage_logs.created_at >= start_at` 過濾(SQL 層行為,mock 測不到):
- fetch_unevaluated_log_uids:評審撈取門檻。
- fetch_unreran_evaluation_uids:重跑撈取門檻(join 來源 usage_logs)。

隔離手法:用**未來年份 2099** 的 created_at,確保 dev DB 既有真實資料(created_at 皆 < 2099)
不會干擾斷言;測試於外層 transaction 內進行,結束整批 rollback。DB 不可用時 skip。
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from uuid_utils import uuid7

from app.models.ai_model_evaluation import AiModelEvaluation
from app.models.usage_log import UsageLog
from app.repositories.ai_model_evaluation import AiModelEvaluationRepository

pytestmark = pytest.mark.asyncio

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://ord:ord_dev_pass_change_me@localhost:5533/ord",
)

_TW = ZoneInfo("Asia/Taipei")
# 未來門檻,確保既有真實資料(< 2099)不入結果集 → 結果集只會是本測試插入的列。
_CUTOFF = datetime(2099, 6, 29, 0, 0, 0, tzinfo=_TW)


def _new_uid() -> UUID:
    return UUID(str(uuid7()))


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
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


async def _add_log(session: AsyncSession, *, created_at: datetime) -> UUID:
    uid = _new_uid()
    session.add(
        UsageLog(
            usage_log_uid=uid,
            model="openai/gpt-4o",
            status="success",
            cost_usd=Decimal("0"),
            request_content={"text": "x"},
            response_summary={"output_text": "y"},
            created_at=created_at,  # 明確指定以驗門檻(覆寫 server_default now())
        )
    )
    await session.flush()
    return uid


async def _add_eval(
    session: AsyncSession, *, usage_log_uid: UUID
) -> UUID:
    uid = _new_uid()
    session.add(
        AiModelEvaluation(
            ai_evaluation_uid=uid,
            usage_log_uid=usage_log_uid,
            ai_original_model="openai/gpt-4o",
            status="evaluated",
            ai_evaluated_at=datetime.now(_TW),
            # ai_reran_at 留 NULL → 待重跑
        )
    )
    await session.flush()
    return uid


async def test_unevaluated_filter_excludes_before_includes_at_and_after(
    db_session: AsyncSession,
) -> None:
    """評審撈取:< 門檻排除;== 門檻(00:00:00)含;> 門檻含。"""
    before = await _add_log(db_session, created_at=_CUTOFF - timedelta(seconds=1))
    at = await _add_log(db_session, created_at=_CUTOFF)  # 正好 00:00:00
    after = await _add_log(db_session, created_at=_CUTOFF + timedelta(hours=1))

    repo = AiModelEvaluationRepository(db_session)
    got = set(await repo.fetch_unevaluated_log_uids(1000, start_at=_CUTOFF))

    assert before not in got  # 門檻前一律排除
    assert at in got  # >= 含正好 00:00:00(user 要求的邊界)
    assert after in got


async def test_unevaluated_no_cutoff_includes_before(
    db_session: AsyncSession,
) -> None:
    """start_at=None(不設限)→ 門檻前的資料也會被撈到。"""
    before = await _add_log(db_session, created_at=_CUTOFF - timedelta(days=400))
    repo = AiModelEvaluationRepository(db_session)
    got = set(await repo.fetch_unevaluated_log_uids(100000, start_at=None))
    assert before in got


async def test_unreran_filter_excludes_before_includes_after(
    db_session: AsyncSession,
) -> None:
    """重跑撈取:join 來源 usage_logs,以來源 log created_at 套門檻。"""
    before_log = await _add_log(db_session, created_at=_CUTOFF - timedelta(seconds=1))
    after_log = await _add_log(db_session, created_at=_CUTOFF + timedelta(hours=1))
    before_eval = await _add_eval(db_session, usage_log_uid=before_log)
    after_eval = await _add_eval(db_session, usage_log_uid=after_log)

    repo = AiModelEvaluationRepository(db_session)
    got = set(await repo.fetch_unreran_evaluation_uids(1000, start_at=_CUTOFF))

    assert before_eval not in got
    assert after_eval in got
