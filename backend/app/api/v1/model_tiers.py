"""模型分級 CRUD API(對齊 docs/Tasks/v1.1/tasks-v1.1.0.md § Backend §2)。

- GET 列表 / 單筆:require_user
- POST / PATCH / DELETE:require_admin
- key 建立後不可改;刪除前須確認無 model 引用
"""

from uuid import UUID

from fastapi import APIRouter

from app.core.audit import write_audit
from app.core.deps import AdminDep, ClientIpDep, DbDep, UserDep
from app.core.exceptions import AppError
from app.core.response import success_response
from app.models.model_tier import ModelTier
from app.repositories.model_tier import ModelTierRepository
from app.schemas.model_tier import ModelTierCreate, ModelTierPatch, ModelTierRead
from uuid_utils import uuid7

router = APIRouter(prefix="/model-tiers", tags=["model-tiers"])


@router.get("", summary="模型分級列表")
async def list_tiers(actor: UserDep, db: DbDep):
    repo = ModelTierRepository(db)
    rows = await repo.list_all()
    data = [ModelTierRead.model_validate(r).model_dump(mode="json") for r in rows]
    return success_response(data=data, detail="success")


@router.get("/{tier_uid}", summary="模型分級單筆")
async def get_tier(tier_uid: UUID, actor: UserDep, db: DbDep):
    repo = ModelTierRepository(db)
    row = await repo.get_by_uid(tier_uid)
    if row is None:
        raise AppError("not_found", code=404)
    return success_response(
        data=ModelTierRead.model_validate(row).model_dump(mode="json"), detail="success"
    )


@router.post("", summary="建立模型分級(admin)")
async def create_tier(
    body: ModelTierCreate,
    admin: AdminDep,
    db: DbDep,
    ip: ClientIpDep,
):
    repo = ModelTierRepository(db)
    if await repo.find_by_key(body.key) is not None:
        raise AppError("tier_key_taken", code=400)
    row = ModelTier(
        tier_uid=UUID(str(uuid7())),
        key=body.key,
        label_zh=body.label_zh,
        label_en=body.label_en,
        color=body.color,
        sort_order=body.sort_order,
        auto_match_min_price_per_mtok=body.auto_match_min_price_per_mtok,
        auto_match_max_price_per_mtok=body.auto_match_max_price_per_mtok,
    )
    repo.add(row)
    await db.flush()
    await write_audit(
        db,
        actor_user_uid=admin.user_uid,
        actor_role=admin.role,
        action="create_model_tier",
        target_type="model_tier",
        target_uid=row.tier_uid,
        ip=ip,
        extra={"key": row.key, "label_zh": row.label_zh},
    )
    await db.commit()
    return success_response(
        data=ModelTierRead.model_validate(row).model_dump(mode="json"), detail="success"
    )


@router.patch("/{tier_uid}", summary="編輯模型分級(admin;不含 key)")
async def patch_tier(
    tier_uid: UUID,
    body: ModelTierPatch,
    admin: AdminDep,
    db: DbDep,
    ip: ClientIpDep,
):
    repo = ModelTierRepository(db)
    row = await repo.get_by_uid(tier_uid)
    if row is None:
        raise AppError("not_found", code=404)
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        return success_response(
            data=ModelTierRead.model_validate(row).model_dump(mode="json"),
            detail="success",
        )
    before = {k: getattr(row, k) for k in fields}
    for k, v in fields.items():
        setattr(row, k, v)
    await db.flush()
    await write_audit(
        db,
        actor_user_uid=admin.user_uid,
        actor_role=admin.role,
        action="update_model_tier",
        target_type="model_tier",
        target_uid=row.tier_uid,
        ip=ip,
        extra={
            "before": {k: _safe(v) for k, v in before.items()},
            "after": {k: _safe(v) for k, v in fields.items()},
        },
    )
    await db.commit()
    return success_response(
        data=ModelTierRead.model_validate(row).model_dump(mode="json"), detail="success"
    )


@router.delete("/{tier_uid}", summary="刪除模型分級(admin;有 model 引用則拒絕)")
async def delete_tier(
    tier_uid: UUID,
    admin: AdminDep,
    db: DbDep,
    ip: ClientIpDep,
):
    repo = ModelTierRepository(db)
    row = await repo.get_by_uid(tier_uid)
    if row is None:
        raise AppError("not_found", code=404)
    using = await repo.is_in_use(row.key)
    if using:
        ids = [m.model_key for m in using[:10]]
        raise AppError(
            "tier_in_use",
            code=400,
            data={"using_models": ids},
        )
    row.is_deleted = True
    row.is_active = False
    await db.flush()
    await write_audit(
        db,
        actor_user_uid=admin.user_uid,
        actor_role=admin.role,
        action="delete_model_tier",
        target_type="model_tier",
        target_uid=row.tier_uid,
        ip=ip,
        extra={"key": row.key},
    )
    await db.commit()
    return success_response(detail="success")


def _safe(v):
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    return str(v)
