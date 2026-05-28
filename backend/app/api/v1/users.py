import secrets
from uuid import UUID

from fastapi import APIRouter, Query
from uuid_utils import uuid7

from app.core.audit import write_audit
from app.core.deps import AdminDep, ClientIpDep, DbDep, UserDep
from app.core.exceptions import AppError
from app.core.response import success_response
from app.core.security import hash_password
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.common import Page
from app.schemas.user import (
    UserCreateRequest,
    UserDropdownItem,
    UserPasswordResetRequest,
    UserResponse,
    UserUpdateRequest,
)
from app.services import auth as auth_service
from app.services.password_policy import validate_password


def _gen_internal_account() -> str:
    """為 role=user 的內部使用者產生不可登入的合成帳號。"""
    return f"usr_{secrets.token_hex(12)}"

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", summary="使用者列表（admin）")
async def list_users(
    admin: AdminDep,
    db: DbDep,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    department_uid: UUID | None = None,
):
    repo = UserRepository(db)
    items, total = await repo.list(page=page, size=size, department_uid=department_uid)
    data = Page[UserResponse](
        items=[UserResponse.model_validate(x) for x in items],
        total=total,
        page=page,
        size=size,
    )
    return success_response(data=data.model_dump(mode="json"), detail="success")


@router.get("/dropdown", summary="使用者下拉清單(v1.5,免分頁,供儀表板篩選)")
async def list_users_dropdown(
    actor: UserDep,
    db: DbDep,
    department_uid: UUID | None = None,
):
    """非 admin 強制只能看自己部門;admin 可不傳取全公司,或傳 department_uid 過濾。"""
    if not actor.is_admin:
        department_uid = actor.department_uid
    repo = UserRepository(db)
    rows = await repo.list_for_dropdown(department_uid=department_uid)
    items = [UserDropdownItem.model_validate(r) for r in rows]
    return success_response(
        data=[x.model_dump(mode="json") for x in items], detail="success"
    )


@router.post("", summary="建立使用者（admin）", status_code=200)
async def create_user(
    body: UserCreateRequest,
    admin: AdminDep,
    db: DbDep,
    ip: ClientIpDep,
):
    repo = UserRepository(db)

    # admin 需明確指定 account/password；user 由後端自動產生（不可登入）
    if body.role == "admin":
        if not body.account or not body.password:
            raise AppError("admin_requires_credentials", code=400)
        validate_password(body.password)
        account = body.account
        password_hash = hash_password(body.password)
    else:
        # role=user 為 SDK 代理身分；員工編號 / Email 為 User Token payload 必要欄位
        if not body.employee_id or not body.email:
            raise AppError("user_requires_identity", code=400)
        account = _gen_internal_account()
        # 隨機長密碼 hash；無人知道，確保 role=user 無法以密碼登入
        password_hash = hash_password(secrets.token_urlsafe(32))

    existing = await repo.get_by_account(account)
    if existing is not None:
        raise AppError("account_taken", code=400)

    user = User(
        user_uid=UUID(str(uuid7())),
        account=account,
        username=body.username,
        password_hash=password_hash,
        role=body.role,
        department_uid=body.department_uid,
        employee_id=body.employee_id,
        email=body.email,
    )
    repo.add(user)
    await db.flush()
    await write_audit(
        db,
        actor_user_uid=admin.user_uid,
        actor_role=admin.role,
        action="create_user",
        target_type="user",
        target_uid=user.user_uid,
        ip=ip,
    )
    await db.commit()
    return success_response(
        data=UserResponse.model_validate(user).model_dump(mode="json"),
        detail="success",
    )


@router.get("/{user_uid}", summary="查詢單一使用者（admin）")
async def get_user(user_uid: UUID, admin: AdminDep, db: DbDep):
    repo = UserRepository(db)
    user = await repo.get_by_uid(user_uid)
    if user is None:
        raise AppError("not_found", code=404)
    return success_response(
        data=UserResponse.model_validate(user).model_dump(mode="json"), detail="success"
    )


@router.patch("/{user_uid}", summary="修改使用者（admin）")
async def update_user(
    user_uid: UUID,
    body: UserUpdateRequest,
    admin: AdminDep,
    db: DbDep,
    ip: ClientIpDep,
):
    repo = UserRepository(db)
    user = await repo.get_by_uid(user_uid)
    if user is None:
        raise AppError("not_found", code=404)
    fields = body.model_dump(exclude_unset=True)
    for k, v in fields.items():
        setattr(user, k, v)
    await db.flush()
    await write_audit(
        db,
        actor_user_uid=admin.user_uid,
        actor_role=admin.role,
        action="update_user",
        target_type="user",
        target_uid=user.user_uid,
        ip=ip,
        extra=fields,
    )
    await db.commit()
    return success_response(
        data=UserResponse.model_validate(user).model_dump(mode="json"), detail="success"
    )


@router.post("/{user_uid}/password/reset", summary="admin 重設使用者密碼")
async def admin_reset_password(
    user_uid: UUID,
    body: UserPasswordResetRequest,
    admin: AdminDep,
    db: DbDep,
    ip: ClientIpDep,
):
    await auth_service.admin_reset_password(
        db, target_user_uid=user_uid, new_password=body.new_password
    )
    await write_audit(
        db,
        actor_user_uid=admin.user_uid,
        actor_role=admin.role,
        action="admin_reset_password",
        target_type="user",
        target_uid=user_uid,
        ip=ip,
    )
    await db.commit()
    return success_response(detail="success")
