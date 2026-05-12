"""Internal Key 服務 — 加解密、隨機挑選 active。

對齊 docs/Tasks/v1.2/propose-v1.2.0.md 增量:DB-driven internal pool。
"""

from __future__ import annotations

import random
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils import uuid7

from app.core.crypto import decrypt_bytes, encrypt_bytes
from app.models.internal_key import InternalKey
from app.repositories.internal_key import InternalKeyRepository


async def create_internal_key(
    db: AsyncSession,
    *,
    name: str,
    base_url: str,
    raw_api_key: str | None,
    rpm_limit: int = 0,
    min_request_interval_ms: int = 0,
) -> InternalKey:
    """建立一筆 internal_keys row;`raw_api_key` 為 None / 空字串視為不設置 api_key。"""
    ciphertext: bytes | None = None
    last4: str | None = None
    if raw_api_key:
        ciphertext = encrypt_bytes(raw_api_key.encode("utf-8"))
        last4 = raw_api_key[-4:] if len(raw_api_key) >= 4 else raw_api_key

    row = InternalKey(
        internal_key_uid=UUID(str(uuid7())),
        name=name,
        base_url=base_url.rstrip("/"),
        key_ciphertext=ciphertext,
        key_last4=last4,
        rpm_limit=rpm_limit,
        min_request_interval_ms=min_request_interval_ms,
    )
    repo = InternalKeyRepository(db)
    repo.add(row)
    await db.flush()
    return row


def decrypt_key(row: InternalKey) -> str | None:
    """解密 api_key 明文;若 row 沒設置 key 則回 None(內網信任場景)。"""
    if row.key_ciphertext is None:
        return None
    return decrypt_bytes(bytes(row.key_ciphertext)).decode("utf-8")


async def pick_random_active(
    db: AsyncSession,
    *,
    exclude_uids: set[UUID] | None = None,
) -> InternalKey | None:
    """隨機挑一把 active internal_key;支援 failover 排除清單。"""
    repo = InternalKeyRepository(db)
    keys = await repo.list_active()
    if exclude_uids:
        keys = [k for k in keys if k.internal_key_uid not in exclude_uids]
    if not keys:
        return None
    return random.choice(keys)
