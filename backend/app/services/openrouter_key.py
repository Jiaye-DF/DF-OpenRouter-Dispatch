import random
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils import uuid7

from app.core.crypto import decrypt_bytes, encrypt_bytes
from app.core.exceptions import AppError
from app.models.openrouter_key import OpenRouterKey
from app.repositories.department import DepartmentRepository
from app.repositories.openrouter_key import OpenRouterKeyRepository


async def create_openrouter_key(
    db: AsyncSession,
    *,
    department_uid: UUID,
    name: str,
    raw_key: str,
) -> OpenRouterKey:
    dept_repo = DepartmentRepository(db)
    dept = await dept_repo.get_by_uid(department_uid)
    if dept is None or not dept.is_active:
        raise AppError("department_not_found", code=400)

    ciphertext = encrypt_bytes(raw_key.encode("utf-8"))
    prefix = raw_key[:4] if len(raw_key) >= 4 else raw_key
    last4 = raw_key[-4:] if len(raw_key) >= 4 else raw_key
    row = OpenRouterKey(
        openrouter_key_uid=UUID(str(uuid7())),
        department_uid=department_uid,
        name=name,
        key_ciphertext=ciphertext,
        key_prefix=prefix,
        key_last4=last4,
    )
    repo = OpenRouterKeyRepository(db)
    repo.add(row)
    await db.flush()
    return row


async def pick_random_active(
    db: AsyncSession,
    *,
    department_uid: UUID,
    exclude_uids: set[UUID] | None = None,
) -> OpenRouterKey | None:
    repo = OpenRouterKeyRepository(db)
    keys = await repo.list_active_by_department(department_uid)
    if exclude_uids:
        keys = [k for k in keys if k.openrouter_key_uid not in exclude_uids]
    if not keys:
        return None
    return random.choice(keys)


def decrypt_key(row: OpenRouterKey) -> str:
    return decrypt_bytes(bytes(row.key_ciphertext)).decode("utf-8")
