import secrets
import string
from uuid import UUID

from argon2 import PasswordHasher
from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils import uuid7

from app.core.exceptions import AppError
from app.models.sdk_api_key import SdkApiKey
from app.repositories.department import DepartmentRepository
from app.repositories.sdk_api_key import SdkApiKeyRepository

_ph = PasswordHasher()
_SECRET_ALPHABET = string.ascii_letters + string.digits


def _gen_sdk_key() -> tuple[str, str]:
    """Return (full_key, prefix)."""
    hex_part = secrets.token_hex(6)  # 12 hex chars
    secret_part = "".join(secrets.choice(_SECRET_ALPHABET) for _ in range(32))
    prefix = f"ordsk_{hex_part}"
    full = f"{prefix}_{secret_part}"
    return full, prefix


async def create_sdk_key(
    db: AsyncSession,
    *,
    department_uid: UUID,
    name: str,
) -> tuple[SdkApiKey, str]:
    dept_repo = DepartmentRepository(db)
    dept = await dept_repo.get_by_uid(department_uid)
    if dept is None or not dept.is_active:
        raise AppError("invalid_input", code=400)

    full, prefix = _gen_sdk_key()
    row = SdkApiKey(
        sdk_api_key_uid=UUID(str(uuid7())),
        department_uid=department_uid,
        name=name,
        key_hash=_ph.hash(full),
        key_prefix=prefix,
    )
    repo = SdkApiKeyRepository(db)
    repo.add(row)
    await db.flush()
    return row, full
