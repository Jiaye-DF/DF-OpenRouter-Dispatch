"""模型主檔 API(對齊 docs/Tasks/v1.1/tasks-v1.1.0.md § Backend §2)。

- 列表 / 單筆:require_user
- PATCH / sync:require_admin
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.clients.openrouter.client import OpenRouterClient, get_openrouter_client
from app.core.audit import write_audit
from app.core.deps import AdminDep, ClientIpDep, DbDep, UserDep
from app.core.exceptions import AppError
from app.core.response import success_response
from app.repositories.model import ModelRepository
from app.schemas.common import Page
from app.schemas.model import ModelPatch, ModelRead
from app.services.sync import sync_models_and_credits

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", summary="模型列表(預設僅 active)")
async def list_models(
    actor: UserDep,
    db: DbDep,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    include_inactive: int = Query(0, ge=0, le=1),
    modality: str | None = None,
    tier_key: str | None = None,
):
    # include_inactive 僅 admin 可用,一般使用者強制看 active
    only_active = not (bool(include_inactive) and actor.is_admin)
    repo = ModelRepository(db)
    items, total = await repo.list_all(
        page=page,
        size=size,
        include_inactive=not only_active,
        modality=modality,
        tier_key=tier_key,
    )
    data = Page[ModelRead](
        items=[ModelRead.model_validate(x) for x in items],
        total=total,
        page=page,
        size=size,
    )
    return success_response(data=data.model_dump(mode="json"), detail="success")


@router.get("/{model_uid}", summary="模型單筆")
async def get_model(model_uid: UUID, actor: UserDep, db: DbDep):
    repo = ModelRepository(db)
    row = await repo.get_by_uid(model_uid)
    if row is None:
        raise AppError("not_found", code=404)
    return success_response(
        data=ModelRead.model_validate(row).model_dump(mode="json"), detail="success"
    )


@router.patch("/{model_uid}", summary="編輯模型(admin;僅可改 is_active / tier_key)")
async def patch_model(
    model_uid: UUID,
    body: ModelPatch,
    admin: AdminDep,
    db: DbDep,
    ip: ClientIpDep,
):
    repo = ModelRepository(db)
    row = await repo.get_by_uid(model_uid)
    if row is None:
        raise AppError("not_found", code=404)
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        return success_response(
            data=ModelRead.model_validate(row).model_dump(mode="json"), detail="success"
        )
    before = {k: getattr(row, k) for k in fields}
    for k, v in fields.items():
        setattr(row, k, v)
    await db.flush()
    await write_audit(
        db,
        actor_user_uid=admin.user_uid,
        actor_role=admin.role,
        action="update_model",
        target_type="model",
        target_uid=row.model_uid,
        ip=ip,
        extra={"before": {k: _safe_json(v) for k, v in before.items()},
               "after": {k: _safe_json(v) for k, v in fields.items()}},
    )
    await db.commit()
    return success_response(
        data=ModelRead.model_validate(row).model_dump(mode="json"), detail="success"
    )


@router.post("/sync", summary="觸發 OpenRouter 模型 + 餘額同步(admin)")
async def sync(
    admin: AdminDep,
    db: DbDep,
    ip: ClientIpDep,
    client: OpenRouterClient = Depends(get_openrouter_client),
):
    result = await sync_models_and_credits(
        db,
        client,
        actor_user_uid=admin.user_uid,
        actor_role=admin.role,
        ip=ip,
    )
    return success_response(data=result.model_dump(mode="json"), detail="success")


def _safe_json(v):
    """audit_log.extra 為 JSONB;Bool / str / None 直接過,其他轉 str。"""
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    return str(v)
