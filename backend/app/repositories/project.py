from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project


class ProjectRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_uid(self, project_uid: UUID) -> Project | None:
        stmt = select(Project).where(
            Project.project_uid == project_uid,
            Project.is_deleted.is_(False),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_dept_code(self, department_uid: UUID, code: str) -> Project | None:
        stmt = select(Project).where(
            Project.department_uid == department_uid,
            func.lower(Project.code) == code.lower(),
            Project.is_deleted.is_(False),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_active_by_uid_and_dept(
        self, project_uid: UUID, department_uid: UUID
    ) -> Project | None:
        """供 SDK 代理鏈驗證 X-Project-Id 必須屬於該部門且仍啟用。"""
        stmt = select(Project).where(
            Project.project_uid == project_uid,
            Project.department_uid == department_uid,
            Project.is_active.is_(True),
            Project.is_deleted.is_(False),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list(
        self,
        *,
        page: int,
        size: int,
        department_uid: UUID | None = None,
    ) -> tuple[list[Project], int]:
        stmt = select(Project).where(Project.is_deleted.is_(False))
        count_stmt = (
            select(func.count()).select_from(Project).where(Project.is_deleted.is_(False))
        )
        if department_uid is not None:
            stmt = stmt.where(Project.department_uid == department_uid)
            count_stmt = count_stmt.where(Project.department_uid == department_uid)
        stmt = stmt.order_by(Project.pid.desc()).offset((page - 1) * size).limit(size)
        items = list((await self.db.execute(stmt)).scalars().all())
        total = int((await self.db.execute(count_stmt)).scalar_one())
        return items, total

    def add(self, row: Project) -> None:
        self.db.add(row)

    async def update_fields(self, row: Project, **fields: Any) -> None:
        for k, v in fields.items():
            setattr(row, k, v)
        await self.db.flush()

    async def count_active_by_department(self, department_uid: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(Project)
            .where(
                Project.department_uid == department_uid,
                Project.is_deleted.is_(False),
                Project.is_active.is_(True),
            )
        )
        return int((await self.db.execute(stmt)).scalar_one())
