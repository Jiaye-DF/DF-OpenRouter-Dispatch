"""Internal Keys CRUD(僅 admin)— v1.2 增量。

對齊 docs/Tasks/v1.2/propose-v1.2.0.md。Internal pool 全平台共用,不分部門。
"""

from uuid import UUID

from fastapi import APIRouter, Query

from app.core.audit import write_audit
from app.core.crypto import encrypt_bytes
from app.core.deps import AdminDep, ClientIpDep, DbDep
from app.core.exceptions import AppError
from app.core.response import success_response
from app.repositories.internal_key import InternalKeyRepository
from app.schemas.common import Page
from app.schemas.internal_key import (
    InternalKeyCreateRequest,
    InternalKeyResponse,
    InternalKeyUpdateRequest,
)
from app.services.internal_key import create_internal_key

router = APIRouter(prefix="/internal-keys", tags=["internal-keys"])


def _to_response(row) -> dict:
    """補上 has_api_key 衍生欄位後序列化。"""
    payload = InternalKeyResponse.model_validate(
        {
            "internal_key_uid": row.internal_key_uid,
            "name": row.name,
            "base_url": row.base_url,
            "has_api_key": row.key_ciphertext is not None,
            "key_last4": row.key_last4,
            "rpm_limit": row.rpm_limit,
            "min_request_interval_ms": row.min_request_interval_ms,
            "is_active": row.is_active,
            "is_deleted": row.is_deleted,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
    )
    return payload.model_dump(mode="json")


@router.get("", summary="Internal Key 列表(admin)")
async def list_keys(
    admin: AdminDep,
    db: DbDep,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
):
    repo = InternalKeyRepository(db)
    items, total = await repo.list(page=page, size=size)
    data = Page[dict](
        items=[_to_response(x) for x in items],
        total=total,
        page=page,
        size=size,
    )
    return success_response(data=data.model_dump(mode="json"), detail="success")


@router.post("", summary="建立 Internal Key(admin)")
async def create_key(
    body: InternalKeyCreateRequest,
    admin: AdminDep,
    db: DbDep,
    ip: ClientIpDep,
):
    row = await create_internal_key(
        db,
        name=body.name,
        base_url=body.base_url,
        raw_api_key=body.api_key,
        rpm_limit=body.rpm_limit,
        min_request_interval_ms=body.min_request_interval_ms,
    )
    await write_audit(
        db,
        actor_user_uid=admin.user_uid,
        actor_role=admin.role,
        action="create_internal_key",
        target_type="internal_key",
        target_uid=row.internal_key_uid,
        ip=ip,
        extra={"name": body.name, "base_url": body.base_url},
    )
    await db.commit()
    return success_response(data=_to_response(row), detail="success")


@router.get("/{uid}", summary="查詢 Internal Key(admin)")
async def get_key(uid: UUID, admin: AdminDep, db: DbDep):
    repo = InternalKeyRepository(db)
    row = await repo.get_by_uid(uid)
    if row is None:
        raise AppError("not_found", code=404)
    return success_response(data=_to_response(row), detail="success")


@router.patch("/{uid}", summary="編輯 Internal Key(admin)")
async def update_key(
    uid: UUID,
    body: InternalKeyUpdateRequest,
    admin: AdminDep,
    db: DbDep,
    ip: ClientIpDep,
):
    repo = InternalKeyRepository(db)
    row = await repo.get_by_uid(uid)
    if row is None:
        raise AppError("not_found", code=404)
    fields = body.model_dump(exclude_unset=True)

    # api_key 特殊處理:傳值即換 Key(空字串 → 清除);未傳則保持原狀
    if "api_key" in fields:
        raw = fields.pop("api_key")
        if raw:
            row.key_ciphertext = encrypt_bytes(raw.encode("utf-8"))
            row.key_last4 = raw[-4:] if len(raw) >= 4 else raw
        else:
            row.key_ciphertext = None
            row.key_last4 = None

    for k, v in fields.items():
        if k == "base_url" and isinstance(v, str):
            v = v.rstrip("/")
        setattr(row, k, v)

    await db.flush()
    await write_audit(
        db,
        actor_user_uid=admin.user_uid,
        actor_role=admin.role,
        action="update_internal_key",
        target_type="internal_key",
        target_uid=uid,
        ip=ip,
        extra={k: v for k, v in fields.items() if k not in {"api_key"}},
    )
    await db.commit()
    return success_response(data=_to_response(row), detail="success")


@router.delete("/{uid}", summary="軟刪除 Internal Key(admin)")
async def delete_key(uid: UUID, admin: AdminDep, db: DbDep, ip: ClientIpDep):
    repo = InternalKeyRepository(db)
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
        action="delete_internal_key",
        target_type="internal_key",
        target_uid=uid,
        ip=ip,
    )
    await db.commit()
    return success_response(detail="success")
