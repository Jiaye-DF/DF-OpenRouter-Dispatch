from uuid import UUID

from fastapi import APIRouter

from app.core.audit import write_audit
from app.core.deps import AdminDep, ClientIpDep, DbDep
from app.core.response import success_response
from app.schemas.user_token import UserTokenGenerateResponse, UserTokenRevokeRequest
from app.services import user_token as user_token_service

router = APIRouter(prefix="/users", tags=["user-tokens"])


@router.post("/{user_uid}/tokens", summary="取得 User Token（一人一把、固定不變，admin）")
async def generate_user_token(
    user_uid: UUID,
    admin: AdminDep,
    db: DbDep,
    ip: ClientIpDep,
):
    # 冪等:已存在則回傳同一把;無有效 token 才產生並落地。不再每次重發。
    token, issued_at = await user_token_service.get_or_create_token(db, user_uid=user_uid)
    await write_audit(
        db,
        actor_user_uid=admin.user_uid,
        actor_role=admin.role,
        action="generate_user_token",
        target_type="user_token",
        target_uid=user_uid,
        ip=ip,
    )
    await db.commit()
    return success_response(
        data=UserTokenGenerateResponse(token=token, issued_at=issued_at).model_dump(mode="json"),
        detail="success",
    )


@router.post("/{user_uid}/tokens/revoke", summary="撤銷此使用者所有舊 Token（admin）")
async def revoke_user_tokens(
    user_uid: UUID,
    body: UserTokenRevokeRequest,
    admin: AdminDep,
    db: DbDep,
    ip: ClientIpDep,
):
    await user_token_service.revoke_tokens(db, user_uid=user_uid, reason=body.reason)
    await write_audit(
        db,
        actor_user_uid=admin.user_uid,
        actor_role=admin.role,
        action="revoke_user_token",
        target_type="user_token",
        target_uid=user_uid,
        ip=ip,
        detail=body.reason,
    )
    await db.commit()
    return success_response(detail="success")
