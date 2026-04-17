from uuid import UUID

from fastapi import APIRouter, Query
from uuid_utils import uuid7

from app.core.audit import write_audit
from app.core.deps import AdminDep, ClientIpDep, DbDep, UserDep
from app.core.exceptions import AppError
from app.core.response import success_response
from app.core.snowflake import generate_id_str
from app.models.project import Project
from app.repositories.department import DepartmentRepository
from app.repositories.project import ProjectRepository
from app.schemas.common import Page
from app.schemas.project import ProjectCreateRequest, ProjectResponse, ProjectUpdateRequest

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", summary="專案列表")
async def list_projects(
    actor: UserDep,
    db: DbDep,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    department_uid: UUID | None = None,
):
    repo = ProjectRepository(db)
    dept_filter = department_uid
    if not actor.is_admin:
        dept_filter = actor.department_uid
    items, total = await repo.list(page=page, size=size, department_uid=dept_filter)
    data = Page[ProjectResponse](
        items=[ProjectResponse.model_validate(x) for x in items],
        total=total,
        page=page,
        size=size,
    )
    return success_response(data=data.model_dump(mode="json"), detail="success")


@router.post("", summary="建立專案（admin）")
async def create_project(
    body: ProjectCreateRequest,
    admin: AdminDep,
    db: DbDep,
    ip: ClientIpDep,
):
    dept_repo = DepartmentRepository(db)
    dept = await dept_repo.get_by_uid(body.department_uid)
    if dept is None or not dept.is_active:
        raise AppError("department_not_found", code=400)
    repo = ProjectRepository(db)
    # code 由後端以 Snowflake ID 產生；全域唯一，無需撞名檢查
    row = Project(
        project_uid=UUID(str(uuid7())),
        department_uid=body.department_uid,
        code=generate_id_str(),
        name=body.name,
        description=body.description,
    )
    repo.add(row)
    await db.flush()
    await write_audit(
        db,
        actor_user_uid=admin.user_uid,
        actor_role=admin.role,
        action="create_project",
        target_type="project",
        target_uid=row.project_uid,
        ip=ip,
    )
    await db.commit()
    return success_response(
        data=ProjectResponse.model_validate(row).model_dump(mode="json"), detail="success"
    )


@router.get("/{uid}", summary="查詢專案")
async def get_project(uid: UUID, actor: UserDep, db: DbDep):
    repo = ProjectRepository(db)
    row = await repo.get_by_uid(uid)
    if row is None:
        raise AppError("not_found", code=404)
    if not actor.is_admin and row.department_uid != actor.department_uid:
        raise AppError("forbidden", code=403)
    return success_response(
        data=ProjectResponse.model_validate(row).model_dump(mode="json"), detail="success"
    )


@router.patch("/{uid}", summary="修改專案（admin）")
async def update_project(
    uid: UUID,
    body: ProjectUpdateRequest,
    admin: AdminDep,
    db: DbDep,
    ip: ClientIpDep,
):
    repo = ProjectRepository(db)
    row = await repo.get_by_uid(uid)
    if row is None:
        raise AppError("not_found", code=404)
    fields = body.model_dump(exclude_unset=True)
    for k, v in fields.items():
        setattr(row, k, v)
    await db.flush()
    await write_audit(
        db,
        actor_user_uid=admin.user_uid,
        actor_role=admin.role,
        action="update_project",
        target_type="project",
        target_uid=row.project_uid,
        ip=ip,
        extra=fields,
    )
    await db.commit()
    return success_response(
        data=ProjectResponse.model_validate(row).model_dump(mode="json"), detail="success"
    )


@router.delete("/{uid}", summary="軟刪除專案（admin）")
async def delete_project(
    uid: UUID,
    admin: AdminDep,
    db: DbDep,
    ip: ClientIpDep,
):
    repo = ProjectRepository(db)
    row = await repo.get_by_uid(uid)
    if row is None:
        raise AppError("not_found", code=404)
    row.is_deleted = True
    row.is_active = False
    await db.flush()
    await write_audit(
        db,
        actor_user_uid=admin.user_uid,
        actor_role=admin.role,
        action="delete_project",
        target_type="project",
        target_uid=uid,
        ip=ip,
    )
    await db.commit()
    return success_response(detail="success")
