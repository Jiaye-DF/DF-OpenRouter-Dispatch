"""模型主檔 API(對齊 docs/Tasks/v1.1/tasks-v1.1.0.md § Backend §2)。

- /models 列表 / 單筆:require_user(完整欄位,供前端後台)
- /allowed/models:公開,精簡欄位,供 SDK 使用者瀏覽
- PATCH / sync:require_admin
"""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from uuid_utils import uuid7

from app.clients.openrouter.client import OpenRouterClient, get_openrouter_client
from app.core.audit import write_audit
from app.core.deps import AdminDep, ClientIpDep, DbDep, UserDep
from app.core.exceptions import AppError
from app.core.response import success_response
from app.models.model import Model
from app.repositories.model import ModelRepository
from app.repositories.model_tier import ModelTierRepository
from app.schemas.common import Page
from app.schemas.model import (
    AllowedModelRead,
    ModelCreateRequest,
    ModelPatch,
    ModelRead,
)
from app.services.sync import sync_models_and_credits

router = APIRouter(prefix="/models", tags=["models"])
# 公開「可用模型」清單;與前端後台用的 /models 分流,只回傳精簡欄位
allowed_router = APIRouter(prefix="/allowed/models", tags=["models"])

# openrouter 模型編輯只可改的欄位(沿用 v1.1)
_OPENROUTER_PATCHABLE = {"is_active", "tier_key"}
# internal 模型編輯可改的欄位(v1.2 新增 internal-only 欄位)
_INTERNAL_PATCHABLE = {"is_active", "tier_key", "name", "description", "context_length", "modality"}


@router.get(
    "",
    summary="模型列表(需登入;一次回傳全部,分頁與篩選由前端處理)",
    description="登入後取得模型清單供後台管理使用,回傳完整欄位。"
    "admin 可額外帶 include_inactive=1 取得未啟用模型。"
    "SDK 使用者請改用公開的 GET /api/v1/allowed/models。",
)
async def list_models(
    actor: UserDep,
    db: DbDep,
    include_inactive: int = Query(0, ge=0, le=1),
):
    # include_inactive 僅 admin 可用;一般使用者一律只看 active
    only_active = not (bool(include_inactive) and actor.is_admin)
    repo = ModelRepository(db)
    items = await repo.list_all(include_inactive=not only_active)
    data = Page[ModelRead](
        items=[ModelRead.model_validate(x) for x in items],
        total=len(items),
        page=1,
        size=len(items),
    )
    return success_response(data=data.model_dump(mode="json"), detail="success")


@allowed_router.get(
    "",
    summary="可用模型清單(公開;精簡欄位,供 SDK 使用者瀏覽)",
    description="無須驗證即可取得已啟用模型的精簡清單(model_key 與基本資訊),"
    "供 SDK 使用者挑選並複製 model_key。定價、tokenizer 等內部資訊不對外。",
)
async def list_allowed_models(db: DbDep):
    repo = ModelRepository(db)
    items = await repo.list_active()
    data = [AllowedModelRead.model_validate(x).model_dump(mode="json") for x in items]
    return success_response(data=data, detail="success")


@router.get("/{model_uid}", summary="模型單筆")
async def get_model(model_uid: UUID, actor: UserDep, db: DbDep):
    repo = ModelRepository(db)
    row = await repo.get_by_uid(model_uid)
    if row is None:
        raise AppError("not_found", code=404)
    return success_response(
        data=ModelRead.model_validate(row).model_dump(mode="json"), detail="success"
    )


@router.post("", summary="手動建立模型(admin;僅接受 provider=internal)")
async def create_model(
    body: ModelCreateRequest,
    admin: AdminDep,
    db: DbDep,
    ip: ClientIpDep,
):
    if body.provider != "internal":
        # openrouter 必須走同步,不允許手動建立
        raise AppError("provider_not_allowed", code=400)

    repo = ModelRepository(db)
    if await repo.find_by_key(body.model_key) is not None:
        raise AppError("model_key_duplicated", code=400)

    # tier_key 須存在於 model_tiers(若有指定)
    if body.tier_key:
        tier_repo = ModelTierRepository(db)
        if await tier_repo.find_by_key(body.tier_key) is None:
            raise AppError("tier_not_found", code=400)

    now = datetime.now(tz=UTC)
    row = Model(
        model_uid=UUID(str(uuid7())),
        provider="internal",
        model_key=body.model_key,
        name=body.name,
        description=body.description,
        context_length=body.context_length,
        modality=body.modality,
        tier_key=body.tier_key,
        is_moderated=False,
        last_synced_at=now,
        is_active=True,
        is_deleted=False,
    )
    repo.add(row)
    await db.flush()
    await write_audit(
        db,
        actor_user_uid=admin.user_uid,
        actor_role=admin.role,
        action="create_internal_model",
        target_type="model",
        target_uid=row.model_uid,
        ip=ip,
        extra={"model_key": body.model_key, "name": body.name},
    )
    await db.commit()
    return success_response(
        data=ModelRead.model_validate(row).model_dump(mode="json"), detail="success"
    )


@router.patch("/{model_uid}", summary="編輯模型(admin;欄位開放依 provider 不同)")
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

    incoming = body.model_dump(exclude_unset=True)
    # 依 provider 過濾可改欄位;不在白名單的欄位即使被傳入也忽略
    allowed = _INTERNAL_PATCHABLE if row.provider == "internal" else _OPENROUTER_PATCHABLE
    fields = {k: v for k, v in incoming.items() if k in allowed}
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
