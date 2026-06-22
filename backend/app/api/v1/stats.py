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
    ProjectStatItem,
    TimeseriesPoint,
    UserStatItem,
)

router = APIRouter(prefix="/stats", tags=["stats"])


def _resolve_filters(
    actor,
    department_uid: UUID | None,
    project_uid: UUID | None,
    user_uid: UUID | None,
) -> tuple[UUID | None, UUID | None, UUID | None]:
    """非 admin 強鎖部門;project_uid / user_uid 不屬該部門時自然由 WHERE 篩掉(不會洩漏)。

    若非 admin 顯式傳了不同部門 → 403(同 v1.4 行為)。
    """
    if actor.is_admin:
        return department_uid, project_uid, user_uid
    if department_uid is not None and department_uid != actor.department_uid:
        raise AppError("forbidden", code=403)
    return actor.department_uid, project_uid, user_uid


@router.get("/overview", summary="總覽")
async def overview(
    actor: UserDep,
    db: DbDep,
    department_uid: UUID | None = None,
    project_uid: UUID | None = None,
    user_uid: UUID | None = None,
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
):
    dept, project, user = _resolve_filters(actor, department_uid, project_uid, user_uid)
    repo = UsageLogRepository(db)
    requests, tokens, cost = await repo.overview(
        department_uid=dept,
        project_uid=project,
        user_uid=user,
        from_time=from_time,
        to_time=to_time,
    )
    data = OverviewStats(total_requests=requests, total_tokens=tokens, total_cost_usd=cost)
    return success_response(data=data.model_dump(mode="json"), detail="success")


@router.get("/by-department", summary="依部門彙總")
async def by_department(
    actor: UserDep,
    db: DbDep,
    department_uid: UUID | None = None,
    project_uid: UUID | None = None,
    user_uid: UUID | None = None,
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
):
    dept, project, user = _resolve_filters(actor, department_uid, project_uid, user_uid)
    repo = UsageLogRepository(db)
    rows = await repo.by_department(
        department_uid=dept,
        project_uid=project,
        user_uid=user,
        from_time=from_time,
        to_time=to_time,
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
    project_uid: UUID | None = None,
    user_uid: UUID | None = None,
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
):
    dept, project, user = _resolve_filters(actor, department_uid, project_uid, user_uid)
    repo = UsageLogRepository(db)
    rows = await repo.by_model(
        department_uid=dept,
        project_uid=project,
        user_uid=user,
        from_time=from_time,
        to_time=to_time,
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


@router.get("/by-project", summary="依專案彙總(v1.5)")
async def by_project_endpoint(
    actor: UserDep,
    db: DbDep,
    department_uid: UUID | None = None,
    project_uid: UUID | None = None,
    user_uid: UUID | None = None,
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
):
    """歷史 project_uid 為 NULL 的紀錄不出現(INNER JOIN projects)。"""
    dept, project, user = _resolve_filters(actor, department_uid, project_uid, user_uid)
    repo = UsageLogRepository(db)
    rows = await repo.by_project(
        department_uid=dept,
        project_uid=project,
        user_uid=user,
        from_time=from_time,
        to_time=to_time,
    )
    items = [
        ProjectStatItem(
            project_uid=r[0],
            project_code=r[1],
            project_name=r[2],
            project_description=r[3],
            total_requests=r[4],
            total_tokens=r[5],
            total_cost_usd=r[6],
        )
        for r in rows
    ]
    return success_response(
        data=[x.model_dump(mode="json") for x in items], detail="success"
    )


@router.get("/by-user", summary="依使用者彙總(v1.5)")
async def by_user_endpoint(
    actor: UserDep,
    db: DbDep,
    department_uid: UUID | None = None,
    project_uid: UUID | None = None,
    user_uid: UUID | None = None,
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
):
    dept, project, user = _resolve_filters(actor, department_uid, project_uid, user_uid)
    repo = UsageLogRepository(db)
    rows = await repo.by_user(
        department_uid=dept,
        project_uid=project,
        user_uid=user,
        from_time=from_time,
        to_time=to_time,
    )
    items = [
        UserStatItem(
            user_uid=r[0],
            username=r[1],
            employee_id=r[2],
            total_requests=r[3],
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
    project_uid: UUID | None = None,
    user_uid: UUID | None = None,
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
    granularity: Literal["hour", "day"] = "day",
):
    dept, project, user = _resolve_filters(actor, department_uid, project_uid, user_uid)
    repo = UsageLogRepository(db)
    rows = await repo.timeseries(
        department_uid=dept,
        project_uid=project,
        user_uid=user,
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
