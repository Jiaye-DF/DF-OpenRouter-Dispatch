import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils import uuid7

from app.core.crypto import encrypt_to_b64url
from app.core.exceptions import AppError
from app.models.user_token import UserToken
from app.models.user_token_revocation import UserTokenRevocation
from app.repositories.department import DepartmentRepository
from app.repositories.user import UserRepository
from app.repositories.user_token import UserTokenRepository
from app.repositories.user_token_revocation import UserTokenRevocationRepository


async def generate_token(
    db: AsyncSession,
    *,
    user_uid: UUID,
) -> tuple[str, datetime]:
    user_repo = UserRepository(db)
    dept_repo = DepartmentRepository(db)
    user = await user_repo.get_by_uid(user_uid)
    if user is None or user.is_deleted or not user.is_active:
        raise AppError("not_found", code=404)
    if user.department_uid is None:
        raise AppError("user_no_department", code=400)
    dept = await dept_repo.get_by_uid(user.department_uid)
    if dept is None:
        raise AppError("user_department_missing", code=400)

    issued_at = datetime.now(tz=UTC)
    payload = {
        "user_uid": str(user.user_uid),
        "department_uid": str(dept.department_uid),
        "department_code": dept.code,
        "employee_id": user.employee_id or "",
        "email": user.email or "",
        "issued_at": issued_at.strftime("%Y-%m-%dT%H:%M:%S.%f+00:00"),
    }
    token = encrypt_to_b64url(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    return token, issued_at


async def get_or_create_token(
    db: AsyncSession,
    *,
    user_uid: UUID,
) -> tuple[str, datetime]:
    """取得該使用者目前的 User Token;一人一把,固定不變。

    新表已有有效 token → 原樣沿用同一把(不撤銷、不重發);
    無有效 token(新使用者 / 撤銷後重發)→ 產生並落地儲存。
    """
    token_repo = UserTokenRepository(db)
    existing = await token_repo.get_active_by_user(user_uid)
    if existing is not None:
        return existing.token, existing.issued_at

    token, issued_at = await generate_token(db, user_uid=user_uid)
    token_repo.add(
        UserToken(
            user_tokens_uid=UUID(str(uuid7())),
            user_uid=user_uid,
            token=token,
            issued_at=issued_at,
        )
    )
    await db.flush()
    return token, issued_at


async def revoke_tokens(
    db: AsyncSession,
    *,
    user_uid: UUID,
    reason: str | None,
) -> None:
    """撤銷使用者所有 User Token;兩張表都要處理。

    1) user_tokens_revocations:寫浮水印,作為驗證鏈對「已發出、未落地」舊 token 的失效依據。
    2) user_tokens:把該使用者目前落地的 token 標記撤銷(追蹤,並讓 get_or_create 不再沿用)。
    """
    user_repo = UserRepository(db)
    rev_repo = UserTokenRevocationRepository(db)
    token_repo = UserTokenRepository(db)
    user = await user_repo.get_by_uid(user_uid)
    if user is None or user.is_deleted:
        raise AppError("not_found", code=404)
    now = datetime.now(tz=UTC)
    rev_repo.add(
        UserTokenRevocation(
            user_tokens_revocation_uid=UUID(str(uuid7())),
            user_uid=user.user_uid,
            revoked_issued_at=now,
            revoked_at=now,
            reason=reason,
        )
    )
    await token_repo.revoke_active_by_user(user.user_uid, now, reason)
    await db.flush()
