from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key_request import ApiKeyRequest
from app.models.department import Department
from app.models.user import User
from app.repositories.department import DepartmentRepository
from app.repositories.project import ProjectRepository
from app.repositories.user import UserRepository


@dataclass
class RouteResult:
    decision: str  # "manual" | "ai" | "system_cancel"
    reason: str | None  # 中文理由(manual / system_cancel 用;ai 為 None)
    matched_department: Department | None  # 命中沿用的既有部門(ai / provision 用)
    matched_user: User | None  # email 命中唯一一筆時的既有使用者(provision 沿用)


async def route(db: AsyncSession, req: ApiKeyRequest) -> RouteResult:
    """確定性規則路由:不呼叫 AI、不寫 DB。順序重要,硬規則先擋。"""
    dept = await DepartmentRepository(db).get_by_code(req.department_code)
    if dept is None:
        return RouteResult(
            decision="manual",
            reason="新部門需後台建立 OpenRouter Key",
            matched_department=None,
            matched_user=None,
        )

    if dept.name.strip() != req.department_name.strip():
        return RouteResult(
            decision="manual",
            reason="部門代號與名稱不符,請人工確認",
            matched_department=None,
            matched_user=None,
        )

    proj = await ProjectRepository(db).get_active_by_department_and_name(
        dept.department_uid, req.project_name
    )
    # list_by_email 已於查詢層排除系統管理員(account='admin'),
    # 故 admin 不會被當成負責人沿用,owner 走新建使用者流程。
    users = await UserRepository(db).list_by_email(req.owner_email)

    if proj is None:
        return RouteResult(
            decision="ai",
            reason=None,
            matched_department=dept,
            matched_user=users[0] if len(users) == 1 else None,
        )

    if len(users) > 1:
        return RouteResult(
            decision="manual",
            reason="負責人 Email 命中多筆使用者,歧義需人工確認",
            matched_department=None,
            matched_user=None,
        )

    if len(users) == 0:
        return RouteResult(
            decision="manual",
            reason="既有專案下的新使用者需人工確認",
            matched_department=None,
            matched_user=None,
        )

    return RouteResult(
        decision="system_cancel",
        reason="過去已存在相同 Key 資料",
        matched_department=None,
        matched_user=None,
    )
