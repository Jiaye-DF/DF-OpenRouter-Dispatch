"""Sync 白名單管理 API(admin only;v1.5)。

`allowed_models` 表是 sync 流程的白名單來源。本表編輯後,下次 sync 自動套用 ——
不在表內(或 is_active=FALSE)的 model_key,sync 後對應的 `models.is_active` 會被覆寫為 FALSE,
SDK user 呼叫時將收到 403 model_forbidden。
"""

from uuid import UUID

from fastapi import APIRouter
from uuid_utils import uuid7

from app.core.audit import write_audit
from app.core.deps import AdminDep, ClientIpDep, DbDep
from app.core.exceptions import AppError
from app.core.response import success_response
from app.models.allowed_model import AllowedModel
from app.repositories.allowed_model import AllowedModelRepository
from app.schemas.allowed_model import (
    AllowedModelCreate,
    AllowedModelPatch,
    AllowedModelRead,
)

router = APIRouter(prefix="/allowed-models", tags=["allowed-models"])


@router.get("", summary="白名單列表(admin)")
async def list_allowed_models(admin: AdminDep, db: DbDep):
    repo = AllowedModelRepository(db)
    rows = await repo.list_all()
    data = [AllowedModelRead.model_validate(r).model_dump(mode="json") for r in rows]
    return success_response(data=data, detail="success")


@router.post("", summary="新增白名單模型(admin)")
async def create_allowed_model(
    body: AllowedModelCreate,
    admin: AdminDep,
    db: DbDep,
    ip: ClientIpDep,
):
    repo = AllowedModelRepository(db)
    existing = await repo.find_by_key(body.model_key)
    if existing is not None:
        if existing.is_deleted:
            # 軟刪除過的重新啟用 → 不再建新列,直接還原。
            existing.is_deleted = False
            existing.is_active = True
            existing.note = body.note
            row = existing
        else:
            raise AppError("model_key_taken", code=400)
    else:
        row = AllowedModel(
            allowed_model_uid=UUID(str(uuid7())),
            model_key=body.model_key,
            note=body.note,
        )
        repo.add(row)
    await db.flush()
    await write_audit(
        db,
        actor_user_uid=admin.user_uid,
        actor_role=admin.role,
        action="create_allowed_model",
        target_type="allowed_model",
        target_uid=row.allowed_model_uid,
        ip=ip,
        extra={"model_key": row.model_key},
    )
    await db.commit()
    return success_response(
        data=AllowedModelRead.model_validate(row).model_dump(mode="json"),
        detail="success",
    )


@router.patch("/{uid}", summary="編輯白名單模型(admin;可改 note / toggle is_active)")
async def patch_allowed_model(
    uid: UUID,
    body: AllowedModelPatch,
    admin: AdminDep,
    db: DbDep,
    ip: ClientIpDep,
):
    repo = AllowedModelRepository(db)
    row = await repo.get_by_uid(uid)
    if row is None:
        raise AppError("not_found", code=404)
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        return success_response(
            data=AllowedModelRead.model_validate(row).model_dump(mode="json"),
            detail="success",
        )
    for k, v in fields.items():
        setattr(row, k, v)
    await db.flush()
    await write_audit(
        db,
        actor_user_uid=admin.user_uid,
        actor_role=admin.role,
        action="update_allowed_model",
        target_type="allowed_model",
        target_uid=row.allowed_model_uid,
        ip=ip,
        extra={"model_key": row.model_key, **fields},
    )
    await db.commit()
    return success_response(
        data=AllowedModelRead.model_validate(row).model_dump(mode="json"),
        detail="success",
    )


@router.delete("/{uid}", summary="刪除白名單模型(admin;軟刪除)")
async def delete_allowed_model(
    uid: UUID,
    admin: AdminDep,
    db: DbDep,
    ip: ClientIpDep,
):
    repo = AllowedModelRepository(db)
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
        action="delete_allowed_model",
        target_type="allowed_model",
        target_uid=row.allowed_model_uid,
        ip=ip,
        extra={"model_key": row.model_key},
    )
    await db.commit()
    return success_response(detail="success")
