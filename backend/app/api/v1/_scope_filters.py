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
    """
    if actor.is_admin:
        return department_uid, project_uid, user_uid
    if department_uid is not None and department_uid != actor.department_uid:
        raise AppError("forbidden", code=403)
    return actor.department_uid, project_uid, user_uid
