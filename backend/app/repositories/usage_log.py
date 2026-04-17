from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import String, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.department import Department
from app.models.usage_log import UsageLog


class UsageLogRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def add(self, row: UsageLog) -> None:
        self.db.add(row)

    async def get_by_uid(self, usage_log_uid: UUID) -> UsageLog | None:
        stmt = select(UsageLog).where(
            UsageLog.usage_log_uid == usage_log_uid,
            UsageLog.is_deleted.is_(False),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    # --- 查詢 ---

    def _apply_filters(
        self,
        stmt,
        *,
        department_uid: UUID | None,
        user_uid: UUID | None,
        model: str | None,
        from_time: datetime | None,
        to_time: datetime | None,
        status: str | None,
    ):
        stmt = stmt.where(UsageLog.is_deleted.is_(False))
        if department_uid is not None:
            stmt = stmt.where(UsageLog.department_uid == department_uid)
        if user_uid is not None:
            stmt = stmt.where(UsageLog.user_uid == user_uid)
        if model:
            stmt = stmt.where(UsageLog.model == model)
        if from_time:
            stmt = stmt.where(UsageLog.created_at >= from_time)
        if to_time:
            stmt = stmt.where(UsageLog.created_at <= to_time)
        if status:
            stmt = stmt.where(UsageLog.status == status)
        return stmt

    async def list(
        self,
        *,
        page: int,
        size: int,
        department_uid: UUID | None = None,
        user_uid: UUID | None = None,
        model: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        status: str | None = None,
    ) -> tuple[list[UsageLog], int]:
        stmt = select(UsageLog)
        stmt = self._apply_filters(
            stmt,
            department_uid=department_uid,
            user_uid=user_uid,
            model=model,
            from_time=from_time,
            to_time=to_time,
            status=status,
        )
        count_stmt = self._apply_filters(
            select(func.count()).select_from(UsageLog),
            department_uid=department_uid,
            user_uid=user_uid,
            model=model,
            from_time=from_time,
            to_time=to_time,
            status=status,
        )
        stmt = stmt.order_by(UsageLog.pid.desc()).offset((page - 1) * size).limit(size)
        items = list((await self.db.execute(stmt)).scalars().all())
        total = int((await self.db.execute(count_stmt)).scalar_one())
        return items, total

    # --- 彙總 ---

    async def overview(
        self,
        *,
        department_uid: UUID | None,
        from_time: datetime | None,
        to_time: datetime | None,
    ) -> tuple[int, int, Decimal]:
        stmt = select(
            func.count(UsageLog.pid),
            func.coalesce(func.sum(UsageLog.total_tokens), 0),
            func.coalesce(func.sum(UsageLog.cost_usd), 0),
        )
        stmt = self._apply_filters(
            stmt,
            department_uid=department_uid,
            user_uid=None,
            model=None,
            from_time=from_time,
            to_time=to_time,
            status=None,
        )
        row = (await self.db.execute(stmt)).one()
        return int(row[0]), int(row[1]), Decimal(row[2])

    async def by_department(
        self,
        *,
        department_uid: UUID | None,
        from_time: datetime | None,
        to_time: datetime | None,
    ) -> list[tuple[UUID | None, str | None, str | None, int, int, Decimal]]:
        stmt = (
            select(
                UsageLog.department_uid,
                Department.code,
                Department.name,
                func.count(UsageLog.pid),
                func.coalesce(func.sum(UsageLog.total_tokens), 0),
                func.coalesce(func.sum(UsageLog.cost_usd), 0),
            )
            .select_from(UsageLog)
            .join(
                Department,
                Department.department_uid == UsageLog.department_uid,
                isouter=True,
            )
            .group_by(UsageLog.department_uid, Department.code, Department.name)
        )
        stmt = self._apply_filters(
            stmt,
            department_uid=department_uid,
            user_uid=None,
            model=None,
            from_time=from_time,
            to_time=to_time,
            status=None,
        )
        rows = (await self.db.execute(stmt)).all()
        return [
            (
                r[0],
                r[1],
                r[2],
                int(r[3]),
                int(r[4]),
                Decimal(r[5]),
            )
            for r in rows
        ]

    async def by_model(
        self,
        *,
        department_uid: UUID | None,
        from_time: datetime | None,
        to_time: datetime | None,
    ) -> list[tuple[str, int, int, int, int, Decimal]]:
        stmt = (
            select(
                UsageLog.model,
                func.count(UsageLog.pid),
                func.coalesce(func.sum(UsageLog.prompt_tokens), 0),
                func.coalesce(func.sum(UsageLog.completion_tokens), 0),
                func.coalesce(func.sum(UsageLog.total_tokens), 0),
                func.coalesce(func.sum(UsageLog.cost_usd), 0),
            )
            .group_by(UsageLog.model)
        )
        stmt = self._apply_filters(
            stmt,
            department_uid=department_uid,
            user_uid=None,
            model=None,
            from_time=from_time,
            to_time=to_time,
            status=None,
        )
        rows = (await self.db.execute(stmt)).all()
        return [
            (r[0], int(r[1]), int(r[2]), int(r[3]), int(r[4]), Decimal(r[5])) for r in rows
        ]

    async def timeseries(
        self,
        *,
        department_uid: UUID | None,
        from_time: datetime | None,
        to_time: datetime | None,
        granularity: str = "day",
    ) -> list[tuple[datetime, int, int, Decimal]]:
        if granularity not in ("day", "hour"):
            granularity = "day"
        bucket = func.date_trunc(granularity, UsageLog.created_at).label("bucket")
        stmt = (
            select(
                bucket,
                func.count(UsageLog.pid),
                func.coalesce(func.sum(UsageLog.total_tokens), 0),
                func.coalesce(func.sum(UsageLog.cost_usd), 0),
            )
            .group_by(bucket)
            .order_by(bucket.asc())
        )
        stmt = self._apply_filters(
            stmt,
            department_uid=department_uid,
            user_uid=None,
            model=None,
            from_time=from_time,
            to_time=to_time,
            status=None,
        )
        rows = (await self.db.execute(stmt)).all()
        return [(r[0], int(r[1]), int(r[2]), Decimal(r[3])) for r in rows]
