from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query

from app.core.deps import DbDep, UserDep
from app.core.exceptions import AppError
from app.core.response import success_response
from app.repositories.usage_log import UsageLogRepository
from app.schemas.stats import (
    DepartmentStatItem,
    ModelStatItem,
    OverviewStats,
    TimeseriesPoint,
)

router = APIRouter(prefix="/stats", tags=["stats"])


def _resolve_dept(actor, department_uid: UUID | None) -> UUID | None:
    if actor.is_admin:
        return department_uid
    if department_uid is not None and department_uid != actor.department_uid:
        raise AppError("forbidden", code=403)
    return actor.department_uid


@router.get("/overview", summary="總覽")
async def overview(
    actor: UserDep,
    db: DbDep,
    department_uid: UUID | None = None,
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
):
    dept = _resolve_dept(actor, department_uid)
    repo = UsageLogRepository(db)
    requests, tokens, cost = await repo.overview(
        department_uid=dept, from_time=from_time, to_time=to_time
    )
    data = OverviewStats(total_requests=requests, total_tokens=tokens, total_cost_usd=cost)
    return success_response(data=data.model_dump(mode="json"), detail="success")


@router.get("/by-department", summary="依部門彙總")
async def by_department(
    actor: UserDep,
    db: DbDep,
    department_uid: UUID | None = None,
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
):
    dept = _resolve_dept(actor, department_uid)
    repo = UsageLogRepository(db)
    rows = await repo.by_department(
        department_uid=dept, from_time=from_time, to_time=to_time
    )
    items = [
        DepartmentStatItem(
            department_uid=r[0],
            department_code=r[1],
            department_name=r[2],
            total_requests=r[3],
            total_tokens=r[4],
            total_cost_usd=r[5],
        )
        for r in rows
    ]
    return success_response(
        data=[x.model_dump(mode="json") for x in items], detail="success"
    )


@router.get("/by-model", summary="依模型彙總")
async def by_model(
    actor: UserDep,
    db: DbDep,
    department_uid: UUID | None = None,
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
):
    dept = _resolve_dept(actor, department_uid)
    repo = UsageLogRepository(db)
    rows = await repo.by_model(
        department_uid=dept, from_time=from_time, to_time=to_time
    )
    items = [
        ModelStatItem(
            model=r[0],
            total_requests=r[1],
            prompt_tokens=r[2],
            completion_tokens=r[3],
            total_tokens=r[4],
            total_cost_usd=r[5],
        )
        for r in rows
    ]
    return success_response(
        data=[x.model_dump(mode="json") for x in items], detail="success"
    )


@router.get("/timeseries", summary="時序彙總")
async def timeseries(
    actor: UserDep,
    db: DbDep,
    department_uid: UUID | None = None,
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
    granularity: Literal["hour", "day"] = "day",
):
    dept = _resolve_dept(actor, department_uid)
    repo = UsageLogRepository(db)
    rows = await repo.timeseries(
        department_uid=dept,
        from_time=from_time,
        to_time=to_time,
        granularity=granularity,
    )
    items = [
        TimeseriesPoint(
            bucket=r[0],
            total_requests=r[1],
            total_tokens=r[2],
            total_cost_usd=r[3],
        )
        for r in rows
    ]
    return success_response(
        data=[x.model_dump(mode="json") for x in items], detail="success"
    )
