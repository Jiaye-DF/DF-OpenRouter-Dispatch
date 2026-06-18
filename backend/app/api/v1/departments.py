from uuid import UUID

from fastapi import APIRouter, Query
from uuid_utils import uuid7

from app.core.audit import write_audit
from app.core.deps import AdminDep, ClientIpDep, DbDep, UserDep
from app.core.exceptions import AppError
from app.core.response import success_response
from app.models.department import Department
from app.repositories.department import DepartmentRepository
from app.repositories.openrouter_key import OpenRouterKeyRepository
from app.repositories.project import ProjectRepository
from app.schemas.common import Page
from app.schemas.department import (
    DepartmentCreateRequest,
    DepartmentResponse,
    DepartmentUpdateRequest,
)

router = APIRouter(prefix="/departments", tags=["departments"])


@router.get("", summary="部門列表")
async def list_departments(
    actor: UserDep,
    db: DbDep,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
):
    repo = DepartmentRepository(db)
    only = None if actor.is_admin else actor.department_uid
    items, total = await repo.list(page=page, size=size, only_uid=only)
    data = Page[DepartmentResponse](
        items=[DepartmentResponse.model_validate(x) for x in items],
        total=total,
        page=page,
        size=size,
    )
    return success_response(data=data.model_dump(mode="json"), detail="success")


@router.post("", summary="建立部門（admin）")
async def create_department(
    body: DepartmentCreateRequest,
    admin: AdminDep,
    db: DbDep,
    ip: ClientIpDep,
):
    repo = DepartmentRepository(db)
    if await repo.get_by_code(body.code) is not None:
        raise AppError("code_conflict", code=409)
    row = Department(
        department_uid=UUID(str(uuid7())),
        code=body.code,
        org_code=body.org_code,
        name=body.name,
        description=body.description,
    )
    repo.add(row)
    await db.flush()
    await write_audit(
        db,
        actor_user_uid=admin.user_uid,
        actor_role=admin.role,
        action="create_department",
        target_type="department",
        target_uid=row.department_uid,
        ip=ip,
    )
    await db.commit()
    return success_response(
        data=DepartmentResponse.model_validate(row).model_dump(mode="json"), detail="success"
    )


@router.get("/{uid}", summary="查詢部門")
async def get_department(uid: UUID, actor: UserDep, db: DbDep):
    repo = DepartmentRepository(db)
    row = await repo.get_by_uid(uid)
    if row is None:
        raise AppError("not_found", code=404)
    if not actor.is_admin and actor.department_uid != uid:
        raise AppError("forbidden", code=403)
    return success_response(
        data=DepartmentResponse.model_validate(row).model_dump(mode="json"), detail="success"
    )


@router.patch("/{uid}", summary="修改部門（admin）")
async def update_department(
    uid: UUID,
    body: DepartmentUpdateRequest,
    admin: AdminDep,
    db: DbDep,
    ip: ClientIpDep,
):
    repo = DepartmentRepository(db)
    row = await repo.get_by_uid(uid)
    if row is None:
        raise AppError("not_found", code=404)
    fields = body.model_dump(exclude_unset=True)
    new_code = fields.get("code")
    if new_code is not None and new_code.lower() != row.code.lower():
        conflict = await repo.get_by_code(new_code)
        if conflict is not None and conflict.department_uid != row.department_uid:
            raise AppError("code_conflict", code=409)
    for k, v in fields.items():
        setattr(row, k, v)
    await db.flush()
    await write_audit(
        db,
        actor_user_uid=admin.user_uid,
        actor_role=admin.role,
        action="update_department",
        target_type="department",
        target_uid=row.department_uid,
        ip=ip,
        extra=fields,
    )
    await db.commit()
    return success_response(
        data=DepartmentResponse.model_validate(row).model_dump(mode="json"), detail="success"
    )


@router.delete("/{uid}", summary="軟刪除部門（admin）")
async def delete_department(
    uid: UUID,
    admin: AdminDep,
    db: DbDep,
    ip: ClientIpDep,
):
    dept_repo = DepartmentRepository(db)
    row = await dept_repo.get_by_uid(uid)
    if row is None:
        raise AppError("not_found", code=404)
    # 檢查下方是否仍有 active Key / Project / User
    or_repo = OpenRouterKeyRepository(db)
    pj_repo = ProjectRepository(db)
    if await or_repo.count_active_by_department(uid) > 0:
        raise AppError("dept_has_active_keys", code=409)
    if await pj_repo.count_active_by_department(uid) > 0:
        raise AppError("dept_has_active_projects", code=409)
    row.is_deleted = True
    row.is_active = False
    await db.flush()
    await write_audit(
        db,
        actor_user_uid=admin.user_uid,
        actor_role=admin.role,
        action="delete_department",
        target_type="department",
        target_uid=uid,
        ip=ip,
    )
    await db.commit()
    return success_response(detail="success")
