from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Query

from app.core.deps import DbDep, UserDep
from app.core.exceptions import AppError
from app.core.response import success_response
from app.repositories.usage_log import UsageLogRepository
from app.schemas.common import Page
from app.schemas.usage_log import UsageLogResponse

router = APIRouter(prefix="/usage-logs", tags=["usage-logs"])


def _resolve_dept_filter(actor, department_uid: UUID | None) -> UUID | None:
    if actor.is_admin:
        return department_uid
    # 一般使用者只能看自己部門
    if department_uid is not None and department_uid != actor.department_uid:
        raise AppError("forbidden", code=403)
    return actor.department_uid


@router.get("", summary="用量紀錄列表")
async def list_usage_logs(
    actor: UserDep,
    db: DbDep,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    department_uid: UUID | None = None,
    user_uid: UUID | None = None,
    model: str | None = None,
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
    status: str | None = None,
):
    dept = _resolve_dept_filter(actor, department_uid)
    if not actor.is_admin and user_uid is not None and user_uid != actor.user_uid:
        # 一般使用者僅能查自身部門；此處保守允許查同部門其他人
        pass

    repo = UsageLogRepository(db)
    items, total = await repo.list(
        page=page,
        size=size,
        department_uid=dept,
        user_uid=user_uid,
        model=model,
        from_time=from_time,
        to_time=to_time,
        status=status,
    )
    data = Page[UsageLogResponse](
        items=[UsageLogResponse.model_validate(x) for x in items],
        total=total,
        page=page,
        size=size,
    )
    return success_response(data=data.model_dump(mode="json"), detail="success")


@router.get("/{uid}", summary="用量紀錄單筆")
async def get_usage_log(uid: UUID, actor: UserDep, db: DbDep):
    repo = UsageLogRepository(db)
    row = await repo.get_by_uid(uid)
    if row is None:
        raise AppError("not_found", code=404)
    if not actor.is_admin and row.department_uid != actor.department_uid:
        raise AppError("forbidden", code=403)
    return success_response(
        data=UsageLogResponse.model_validate(row).model_dump(mode="json"), detail="success"
    )
