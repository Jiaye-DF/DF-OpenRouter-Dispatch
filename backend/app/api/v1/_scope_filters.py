from uuid import UUID

from app.core.exceptions import AppError
from app.schemas.actor import Actor


def resolve_filters(
    actor: Actor,
    department_uid: UUID | None,
    project_uid: UUID | None,
    user_uid: UUID | None,
) -> tuple[UUID | None, UUID | None, UUID | None]:
    """非 admin 強鎖部門;project_uid / user_uid 不屬該部門時自然由 WHERE 篩掉(不會洩漏)。

    若非 admin 顯式傳了不同部門 → 403(同 v1.4 行為)。

    非 admin 且**無所屬部門**(`department_uid` 為 NULL)→ 403。否則鎖部門會退化為
    `department_uid=None`(不加 WHERE),使無部門的一般使用者看到全平台資料——usage-logs
    明細更會外露跨部門 request/response PII(見 fixed.md §10 / scan 報告 AD-001)。
    """
    if actor.is_admin:
        return department_uid, project_uid, user_uid
    if department_uid is not None and department_uid != actor.department_uid:
        raise AppError("forbidden", code=403)
    if actor.department_uid is None:
        raise AppError("forbidden", code=403)
    return actor.department_uid, project_uid, user_uid
