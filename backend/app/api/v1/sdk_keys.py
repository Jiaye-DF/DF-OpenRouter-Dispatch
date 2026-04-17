from uuid import UUID

from fastapi import APIRouter, Query

from app.core.audit import write_audit
from app.core.deps import AdminDep, ClientIpDep, DbDep
from app.core.exceptions import AppError
from app.core.response import success_response
from app.repositories.sdk_api_key import SdkApiKeyRepository
from app.schemas.common import Page
from app.schemas.sdk_key import (
    SdkKeyCreateRequest,
    SdkKeyCreateResponse,
    SdkKeyResponse,
    SdkKeyUpdateRequest,
)
from app.services.sdk_key import create_sdk_key

router = APIRouter(prefix="/sdk-keys", tags=["sdk-keys"])


@router.get("", summary="SDK Key 列表（admin）")
async def list_sdk_keys(
    admin: AdminDep,
    db: DbDep,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    department_uid: UUID | None = None,
):
    repo = SdkApiKeyRepository(db)
    items, total = await repo.list(page=page, size=size, department_uid=department_uid)
    data = Page[SdkKeyResponse](
        items=[SdkKeyResponse.model_validate(x) for x in items],
        total=total,
        page=page,
        size=size,
    )
    return success_response(data=data.model_dump(mode="json"), detail="success")


@router.post("", summary="建立 SDK Key（admin）— 一次性回明文")
async def create_key(
    body: SdkKeyCreateRequest,
    admin: AdminDep,
    db: DbDep,
    ip: ClientIpDep,
):
    row, full = await create_sdk_key(
        db, department_uid=body.department_uid, name=body.name
    )
    await write_audit(
        db,
        actor_user_uid=admin.user_uid,
        actor_role=admin.role,
        action="create_sdk_key",
        target_type="sdk_api_key",
        target_uid=row.sdk_api_key_uid,
        ip=ip,
    )
    await db.commit()
    resp = SdkKeyCreateResponse(
        sdk_api_key_uid=row.sdk_api_key_uid,
        department_uid=row.department_uid,
        name=row.name,
        key_prefix=row.key_prefix,
        is_active=row.is_active,
        key=full,
    )
    return success_response(data=resp.model_dump(mode="json"), detail="success")


@router.patch("/{uid}", summary="修改 SDK Key（admin）")
async def update_key(
    uid: UUID,
    body: SdkKeyUpdateRequest,
    admin: AdminDep,
    db: DbDep,
    ip: ClientIpDep,
):
    repo = SdkApiKeyRepository(db)
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
        action="update_sdk_key",
        target_type="sdk_api_key",
        target_uid=uid,
        ip=ip,
        extra=fields,
    )
    await db.commit()
    return success_response(
        data=SdkKeyResponse.model_validate(row).model_dump(mode="json"), detail="success"
    )


@router.delete("/{uid}", summary="軟刪除 SDK Key（admin）")
async def delete_key(uid: UUID, admin: AdminDep, db: DbDep, ip: ClientIpDep):
    repo = SdkApiKeyRepository(db)
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
        action="delete_sdk_key",
        target_type="sdk_api_key",
        target_uid=uid,
        ip=ip,
    )
    await db.commit()
    return success_response(detail="success")
