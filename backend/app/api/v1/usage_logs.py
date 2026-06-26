from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Query

from app.core.deps import AdminDep, DbDep
from app.core.exceptions import AppError
from app.core.response import success_response
from app.repositories.usage_log import UsageLogRepository
from app.schemas.common import Page
from app.schemas.usage_log import UsageLogDetail, UsageLogListItem

router = APIRouter(prefix="/usage-logs", tags=["usage-logs"])


@router.get("", summary="用量紀錄列表")
async def list_usage_logs(
    actor: AdminDep,
    db: DbDep,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    department_uid: UUID | None = None,
    user_uid: UUID | None = None,
    model: str | None = None,
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
    status: str | None = None,
    used_tools: bool | None = None,
    pid: int | None = Query(default=None, ge=1),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
):
    repo = UsageLogRepository(db)
    items, total = await repo.list(
        page=page,
        size=size,
        department_uid=department_uid,
        user_uid=user_uid,
        model=model,
        from_time=from_time,
        to_time=to_time,
        status=status,
        used_tools=used_tools,
        pid=pid,
        order=order,
    )
    data = Page[UsageLogListItem](
        items=[UsageLogListItem.model_validate(x) for x in items],
        total=total,
        page=page,
        size=size,
    )
    return success_response(data=data.model_dump(mode="json"), detail="success")


@router.get("/{uid}", summary="用量紀錄單筆")
async def get_usage_log(uid: UUID, actor: AdminDep, db: DbDep):
    repo = UsageLogRepository(db)
    row = await repo.get_by_uid(uid)
    if row is None:
        raise AppError("not_found", code=404)
    return success_response(
        data=UsageLogDetail.model_validate(row).model_dump(mode="json"), detail="success"
    )
