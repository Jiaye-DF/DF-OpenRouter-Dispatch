import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils import uuid7

from app.core.crypto import encrypt_to_b64url
from app.core.exceptions import AppError
from app.models.user_token_revocation import UserTokenRevocation
from app.repositories.department import DepartmentRepository
from app.repositories.user import UserRepository
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


async def revoke_tokens(
    db: AsyncSession,
    *,
    user_uid: UUID,
    reason: str | None,
) -> None:
    user_repo = UserRepository(db)
    rev_repo = UserTokenRevocationRepository(db)
    user = await user_repo.get_by_uid(user_uid)
    if user is None or user.is_deleted:
        raise AppError("not_found", code=404)
    now = datetime.now(tz=UTC)
    row = UserTokenRevocation(
        user_tokens_revocation_uid=UUID(str(uuid7())),
        user_uid=user.user_uid,
        revoked_issued_at=now,
        revoked_at=now,
        reason=reason,
    )
    rev_repo.add(row)
    await db.flush()
