from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.department import Department


class DepartmentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_uid(self, department_uid: UUID) -> Department | None:
        stmt = select(Department).where(
            Department.department_uid == department_uid,
            Department.is_deleted.is_(False),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_code(self, code: str) -> Department | None:
        stmt = select(Department).where(
            func.lower(Department.code) == code.lower(),
            Department.is_deleted.is_(False),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list(
        self,
        *,
        page: int,
        size: int,
        only_uid: UUID | None = None,
    ) -> tuple[list[Department], int]:
        stmt = select(Department).where(Department.is_deleted.is_(False))
        count_stmt = (
            select(func.count()).select_from(Department).where(Department.is_deleted.is_(False))
        )
        if only_uid is not None:
            stmt = stmt.where(Department.department_uid == only_uid)
            count_stmt = count_stmt.where(Department.department_uid == only_uid)
        stmt = stmt.order_by(Department.pid.desc()).offset((page - 1) * size).limit(size)
        items = list((await self.db.execute(stmt)).scalars().all())
        total = int((await self.db.execute(count_stmt)).scalar_one())
        return items, total

    def add(self, row: Department) -> None:
        self.db.add(row)

    async def update_fields(self, row: Department, **fields: Any) -> None:
        for k, v in fields.items():
            setattr(row, k, v)
        await self.db.flush()
