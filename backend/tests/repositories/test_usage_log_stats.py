"""UsageLogRepository.by_project_model 真 DB 測試(對齊 task-420 Acceptance)。

驗證 SQL 層行為(mock 測不到):
- INNER JOIN projects → 歷史 project_uid IS NULL 的 log 不入結果。
- group_by(project_uid, code, name, model) → 每列一組專案×模型。
- 排序 project_code 升冪、同專案內 cost_usd 降冪。
- 交叉驗證:某專案各模型 total_cost_usd 加總 == by_project 該專案 total_cost_usd。

隔離手法:每次建立唯一 department_uid(uuid7),僅以該部門過濾 → 既有 dev 資料
(屬其他部門)不干擾斷言;測試於外層 transaction 內進行,結束整批 rollback。
DB 不可用時 skip。
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from decimal import Decimal
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from uuid_utils import uuid7

from app.models.department import Department
from app.models.project import Project
from app.models.usage_log import UsageLog
from app.repositories.usage_log import UsageLogRepository

pytestmark = pytest.mark.asyncio

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://ord:ord_dev_pass_change_me@localhost:5533/ord",
)


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


async def _add_department(session: AsyncSession) -> UUID:
    uid = _new_uid()
    session.add(
        Department(
            department_uid=uid,
            code=f"DEPT-{str(uid)[:8]}",
            name="測試部門",
        )
    )
    await session.flush()
    return uid


async def _add_project(
    session: AsyncSession, *, department_uid: UUID, code: str, name: str
) -> UUID:
    uid = _new_uid()
    session.add(
        Project(
            project_uid=uid,
            department_uid=department_uid,
            code=code,
            name=name,
        )
    )
    await session.flush()
    return uid


async def _add_log(
    session: AsyncSession,
    *,
    department_uid: UUID,
    project_uid: UUID | None,
    model: str,
    total_tokens: int,
    cost_usd: Decimal,
) -> None:
    session.add(
        UsageLog(
            usage_log_uid=_new_uid(),
            department_uid=department_uid,
            project_uid=project_uid,
            model=model,
            status="success",
            total_tokens=total_tokens,
            cost_usd=cost_usd,
        )
    )
    await session.flush()


async def test_by_project_model_groups_orders_and_excludes_null_project(
    db_session: AsyncSession,
) -> None:
    dept = await _add_department(db_session)
    p_a = await _add_project(db_session, department_uid=dept, code="PRJ-A", name="專案A")
    p_b = await _add_project(db_session, department_uid=dept, code="PRJ-B", name="專案B")

    # 專案A:gpt-4o 兩筆(合 1.5)、claude 一筆(0.75)
    await _add_log(
        db_session, department_uid=dept, project_uid=p_a,
        model="openai/gpt-4o", total_tokens=600, cost_usd=Decimal("1.000000"),
    )
    await _add_log(
        db_session, department_uid=dept, project_uid=p_a,
        model="openai/gpt-4o", total_tokens=400, cost_usd=Decimal("0.500000"),
    )
    await _add_log(
        db_session, department_uid=dept, project_uid=p_a,
        model="anthropic/claude-3.5", total_tokens=200, cost_usd=Decimal("0.750000"),
    )
    # 專案B:gpt-4o 一筆(0.25)
    await _add_log(
        db_session, department_uid=dept, project_uid=p_b,
        model="openai/gpt-4o", total_tokens=100, cost_usd=Decimal("0.250000"),
    )
    # 歷史無專案 log:project_uid=NULL → INNER JOIN 應排除
    await _add_log(
        db_session, department_uid=dept, project_uid=None,
        model="openai/gpt-4o", total_tokens=999, cost_usd=Decimal("9.000000"),
    )

    repo = UsageLogRepository(db_session)
    rows = await repo.by_project_model(
        department_uid=dept, from_time=None, to_time=None
    )

    # NULL 專案不入
    assert all(r[0] is not None for r in rows)
    # 三組:A/gpt-4o、A/claude、B/gpt-4o
    assert len(rows) == 3

    # 排序:project_code 升冪(A 在 B 前),同專案內 cost 降冪
    assert [r[1] for r in rows] == ["PRJ-A", "PRJ-A", "PRJ-B"]
    # 專案A 內 gpt-4o(1.5)> claude(0.75)
    assert rows[0][3] == "openai/gpt-4o"
    assert rows[0][4] == 2  # total_requests(合併兩筆)
    assert rows[0][5] == 1000  # total_tokens
    assert rows[0][6] == Decimal("1.500000")
    assert rows[1][3] == "anthropic/claude-3.5"
    assert rows[1][6] == Decimal("0.750000")
    assert rows[2][1] == "PRJ-B"
    assert rows[2][6] == Decimal("0.250000")


async def test_by_project_model_cost_sum_matches_by_project(
    db_session: AsyncSession,
) -> None:
    """交叉驗證:某專案各模型成本加總 == by_project 該專案總成本。"""
    dept = await _add_department(db_session)
    p_a = await _add_project(db_session, department_uid=dept, code="PRJ-A", name="專案A")

    await _add_log(
        db_session, department_uid=dept, project_uid=p_a,
        model="openai/gpt-4o", total_tokens=600, cost_usd=Decimal("1.000000"),
    )
    await _add_log(
        db_session, department_uid=dept, project_uid=p_a,
        model="anthropic/claude-3.5", total_tokens=200, cost_usd=Decimal("0.750000"),
    )

    repo = UsageLogRepository(db_session)
    pm_rows = await repo.by_project_model(
        department_uid=dept, from_time=None, to_time=None
    )
    proj_rows = await repo.by_project(
        department_uid=dept, from_time=None, to_time=None
    )

    pm_sum = sum((r[6] for r in pm_rows if r[0] == p_a), Decimal(0))
    proj_total = next(r[6] for r in proj_rows if r[0] == p_a)
    assert pm_sum == proj_total == Decimal("1.750000")
