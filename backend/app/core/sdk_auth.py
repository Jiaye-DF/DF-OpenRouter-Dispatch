import json
from datetime import UTC, datetime
from uuid import UUID

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt_from_b64url
from app.core.exceptions import AppError
from app.schemas.actor import SdkCallerContext

_ph = PasswordHasher()

_UNAUTHORIZED = AppError("unauthorized", code=401)


def _parse_sdk_key_prefix(raw: str) -> str:
    """格式：ordsk_<12 hex>_<secret>；取出 prefix = 'ordsk_<12 hex>'。"""
    parts = raw.split("_", 2)
    if len(parts) < 3 or parts[0] != "ordsk":
        raise _UNAUTHORIZED
    return f"{parts[0]}_{parts[1]}"


async def resolve_sdk_caller(
    db: AsyncSession,
    sdk_key_raw: str,
    user_token_raw: str,
    project_code: str,
) -> SdkCallerContext:
    from app.repositories.project import ProjectRepository
    from app.repositories.sdk_api_key import SdkApiKeyRepository
    from app.repositories.user import UserRepository
    from app.repositories.user_token_revocation import UserTokenRevocationRepository

    # --- 1. SDK Key ---
    try:
        prefix = _parse_sdk_key_prefix(sdk_key_raw)
    except AppError:
        raise _UNAUTHORIZED from None

    sdk_repo = SdkApiKeyRepository(db)
    candidates = await sdk_repo.list_active_by_prefix(prefix)
    sdk_row = None
    for row in candidates:
        try:
            if _ph.verify(row.key_hash, sdk_key_raw):
                sdk_row = row
                break
        except VerifyMismatchError:
            continue
        except Exception:
            continue
    if sdk_row is None:
        raise _UNAUTHORIZED

    # --- 2. User Token 解密 ---
    try:
        payload_json = decrypt_from_b64url(user_token_raw)
        payload = json.loads(payload_json)
    except Exception as exc:  # noqa: BLE001
        raise _UNAUTHORIZED from exc

    try:
        user_uid = UUID(payload["user_uid"])
        token_dept_uid = UUID(payload["department_uid"])
        department_code = str(payload["department_code"])
        employee_id = payload.get("employee_id")
        email = payload.get("email")
        issued_at_str = payload["issued_at"]
        issued_at = datetime.fromisoformat(issued_at_str.replace("Z", "+00:00"))
        if issued_at.tzinfo is None:
            issued_at = issued_at.replace(tzinfo=UTC)
    except (KeyError, ValueError, TypeError) as exc:
        raise _UNAUTHORIZED from exc

    # --- 3. 部門一致性 ---
    if sdk_row.department_uid != token_dept_uid:
        raise _UNAUTHORIZED

    # --- 4. User 是否仍存在且未撤銷 ---
    user_repo = UserRepository(db)
    user = await user_repo.get_by_uid(user_uid)
    if user is None or user.is_deleted or not user.is_active:
        raise _UNAUTHORIZED
    if user.department_uid != token_dept_uid:
        raise _UNAUTHORIZED

    rev_repo = UserTokenRevocationRepository(db)
    latest_rev = await rev_repo.latest_for_user(user_uid)
    if latest_rev is not None and issued_at < latest_rev.revoked_issued_at:
        raise _UNAUTHORIZED

    # --- 5. X-Project-Code 必須屬於 SDK Key 的部門且仍啟用 ---
    project_repo = ProjectRepository(db)
    project = await project_repo.get_active_by_code_and_dept(
        project_code, sdk_row.department_uid
    )
    if project is None:
        raise AppError("project_invalid", code=400)

    return SdkCallerContext(
        sdk_api_key_uid=sdk_row.sdk_api_key_uid,
        department_uid=sdk_row.department_uid,
        department_code=department_code,
        project_uid=project.project_uid,
        project_code=project.code,
        user_uid=user_uid,
        employee_id=employee_id,
        email=email,
    )
