from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils import uuid7

from app.models.audit_log import AuditLog


async def write_audit(
    db: AsyncSession,
    *,
    actor_user_uid: UUID,
    actor_role: str,
    action: str,
    target_type: str,
    target_uid: UUID | None,
    result: str = "success",
    detail: str | None = None,
    ip: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """寫入稽核 log。呼叫端負責 commit。"""
    row = AuditLog(
        audit_log_uid=UUID(str(uuid7())),
        actor_user_uid=actor_user_uid,
        actor_role=actor_role,
        action=action,
        target_type=target_type,
        target_uid=target_uid,
        result=result,
        detail=detail,
        ip=ip,
        extra=extra or {},
    )
    db.add(row)
    await db.flush()
