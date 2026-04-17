from uuid import UUID

from fastapi import APIRouter, Query

from app.core.audit import write_audit
from app.core.deps import AdminDep, ClientIpDep, DbDep
from app.core.exceptions import AppError
from app.core.response import success_response
from app.repositories.openrouter_key import OpenRouterKeyRepository
from app.schemas.common import Page
from app.schemas.openrouter_key import (
    OpenRouterKeyCreateRequest,
    OpenRouterKeyResponse,
    OpenRouterKeyUpdateRequest,
)
from app.services.openrouter_key import create_openrouter_key

router = APIRouter(prefix="/openrouter-keys", tags=["openrouter-keys"])


@router.get("", summary="OpenRouter Key 列表（admin）")
async def list_keys(
    admin: AdminDep,
    db: DbDep,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    department_uid: UUID | None = None,
):
    repo = OpenRouterKeyRepository(db)
    items, total = await repo.list(page=page, size=size, department_uid=department_uid)
    data = Page[OpenRouterKeyResponse](
        items=[OpenRouterKeyResponse.model_validate(x) for x in items],
        total=total,
        page=page,
        size=size,
    )
    return success_response(data=data.model_dump(mode="json"), detail="success")


@router.post("", summary="建立 OpenRouter Key（admin）")
async def create_key(
    body: OpenRouterKeyCreateRequest,
    admin: AdminDep,
    db: DbDep,
    ip: ClientIpDep,
):
    row = await create_openrouter_key(
        db,
        department_uid=body.department_uid,
        name=body.name,
        raw_key=body.key,
    )
    await write_audit(
        db,
        actor_user_uid=admin.user_uid,
        actor_role=admin.role,
        action="create_openrouter_key",
        target_type="openrouter_key",
        target_uid=row.openrouter_key_uid,
        ip=ip,
    )
    await db.commit()
    return success_response(
        data=OpenRouterKeyResponse.model_validate(row).model_dump(mode="json"), detail="success"
    )


@router.get("/{uid}", summary="查詢 OpenRouter Key（admin）")
async def get_key(uid: UUID, admin: AdminDep, db: DbDep):
    repo = OpenRouterKeyRepository(db)
    row = await repo.get_by_uid(uid)
    if row is None:
        raise AppError("not_found", code=404)
    return success_response(
        data=OpenRouterKeyResponse.model_validate(row).model_dump(mode="json"), detail="success"
    )


@router.patch("/{uid}", summary="修改 OpenRouter Key（admin）— 禁止改 key")
async def update_key(
    uid: UUID,
    body: OpenRouterKeyUpdateRequest,
    admin: AdminDep,
    db: DbDep,
    ip: ClientIpDep,
):
    repo = OpenRouterKeyRepository(db)
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
        action="update_openrouter_key",
        target_type="openrouter_key",
        target_uid=uid,
        ip=ip,
        extra=fields,
    )
    await db.commit()
    return success_response(
        data=OpenRouterKeyResponse.model_validate(row).model_dump(mode="json"), detail="success"
    )


@router.delete("/{uid}", summary="軟刪除 OpenRouter Key（admin）")
async def delete_key(uid: UUID, admin: AdminDep, db: DbDep, ip: ClientIpDep):
    repo = OpenRouterKeyRepository(db)
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
        action="delete_openrouter_key",
        target_type="openrouter_key",
        target_uid=uid,
        ip=ip,
    )
    await db.commit()
    return success_response(detail="success")
