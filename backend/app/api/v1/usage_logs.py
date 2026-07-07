from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.v1._scope_filters import resolve_filters
from app.core.deps import DbDep, UserDep
from app.core.exceptions import AppError
from app.core.response import success_response
from app.repositories.usage_log import UsageLogRepository
from app.schemas.common import Page
from app.schemas.usage_log import UsageLogDetail, UsageLogListItem

router = APIRouter(prefix="/usage-logs", tags=["usage-logs"])


@router.get("", summary="用量紀錄列表")
async def list_usage_logs(
    actor: UserDep,
    db: DbDep,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    department_uid: UUID | None = None,
    project_uid: UUID | None = None,
    user_uid: UUID | None = None,
    model: str | None = None,
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
    status: str | None = None,
    used_tools: bool | None = None,
    pid: int | None = Query(default=None, ge=1),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
):
    # 權限收斂於 resolve_filters:admin 不鎖、非-admin 強制自身部門、跨部門顯式傳參 → 403。
    dept, project, user = resolve_filters(actor, department_uid, project_uid, user_uid)
    repo = UsageLogRepository(db)
    rows, total = await repo.list(
        page=page,
        size=size,
        department_uid=dept,
        project_uid=project,
        user_uid=user,
        model=model,
        from_time=from_time,
        to_time=to_time,
        status=status,
        used_tools=used_tools,
        pid=pid,
        order=order,
    )
    data = Page[UsageLogListItem](
        items=[
            UsageLogListItem.model_validate(ul).model_copy(
                update={"project_code": code, "project_name": name}
            )
            for ul, code, name in rows
        ],
        total=total,
        page=page,
        size=size,
    )
    return success_response(data=data.model_dump(mode="json"), detail="success")


@router.get("/{uid}", summary="用量紀錄單筆")
async def get_usage_log(uid: UUID, actor: UserDep, db: DbDep):
    # resolve_filters 回傳的 dept:admin → None(不鎖)、非-admin → 自身部門 UID。
    # 權限一律收斂於 resolve_filters,不在 router 依角色散落判斷。
    dept, _, _ = resolve_filters(actor, None, None, None)
    repo = UsageLogRepository(db)
    row = await repo.get_by_uid_with_project(uid)
    if row is None:
        raise AppError("not_found", code=404)
    log, project_code, project_name = row
    # 非-admin 取他部門明細 → 404(不以存在與否側漏,對齊 propose §D.1);admin dept 為 None 不鎖。
    if dept is not None and log.department_uid != dept:
        raise AppError("not_found", code=404)
    detail = UsageLogDetail.model_validate(log).model_copy(
        update={"project_code": project_code, "project_name": project_name}
    )
    return success_response(data=detail.model_dump(mode="json"), detail="success")
