from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import String, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.department import Department
from app.models.project import Project
from app.models.usage_log import UsageLog
from app.models.user import User


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
        project_uid: UUID | None,
        user_uid: UUID | None,
        model: str | None,
        from_time: datetime | None,
        to_time: datetime | None,
        status: str | None,
        used_tools: bool | None = None,
    ):
        stmt = stmt.where(UsageLog.is_deleted.is_(False))
        if department_uid is not None:
            stmt = stmt.where(UsageLog.department_uid == department_uid)
        if project_uid is not None:
            stmt = stmt.where(UsageLog.project_uid == project_uid)
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
        if used_tools is not None:
            stmt = stmt.where(UsageLog.used_tools.is_(used_tools))
        return stmt

    async def list(
        self,
        *,
        page: int,
        size: int,
        department_uid: UUID | None = None,
        project_uid: UUID | None = None,
        user_uid: UUID | None = None,
        model: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        status: str | None = None,
        used_tools: bool | None = None,
    ) -> tuple[list[UsageLog], int]:
        stmt = select(UsageLog)
        stmt = self._apply_filters(
            stmt,
            department_uid=department_uid,
            project_uid=project_uid,
            user_uid=user_uid,
            model=model,
            from_time=from_time,
            to_time=to_time,
            status=status,
            used_tools=used_tools,
        )
        count_stmt = self._apply_filters(
            select(func.count()).select_from(UsageLog),
            department_uid=department_uid,
            project_uid=project_uid,
            user_uid=user_uid,
            model=model,
            from_time=from_time,
            to_time=to_time,
            status=status,
            used_tools=used_tools,
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
        project_uid: UUID | None = None,
        user_uid: UUID | None = None,
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
            project_uid=project_uid,
            user_uid=user_uid,
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
        project_uid: UUID | None = None,
        user_uid: UUID | None = None,
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
            project_uid=project_uid,
            user_uid=user_uid,
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
        project_uid: UUID | None = None,
        user_uid: UUID | None = None,
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
            project_uid=project_uid,
            user_uid=user_uid,
            model=None,
            from_time=from_time,
            to_time=to_time,
            status=None,
        )
        rows = (await self.db.execute(stmt)).all()
        return [
            (r[0], int(r[1]), int(r[2]), int(r[3]), int(r[4]), Decimal(r[5])) for r in rows
        ]

    async def by_project(
        self,
        *,
        department_uid: UUID | None,
        project_uid: UUID | None = None,
        user_uid: UUID | None = None,
        from_time: datetime | None,
        to_time: datetime | None,
    ) -> list[tuple[UUID, str, str, str | None, int, int, Decimal]]:
        """依專案彙總;歷史 project_uid 為 NULL 的紀錄不出現(JOIN 內連線)。"""
        stmt = (
            select(
                UsageLog.project_uid,
                Project.code,
                Project.name,
                Project.description,
                func.count(UsageLog.pid),
                func.coalesce(func.sum(UsageLog.total_tokens), 0),
                func.coalesce(func.sum(UsageLog.cost_usd), 0),
            )
            .select_from(UsageLog)
            .join(Project, Project.project_uid == UsageLog.project_uid)
            .group_by(
                UsageLog.project_uid, Project.code, Project.name, Project.description
            )
        )
        stmt = self._apply_filters(
            stmt,
            department_uid=department_uid,
            project_uid=project_uid,
            user_uid=user_uid,
            model=None,
            from_time=from_time,
            to_time=to_time,
            status=None,
        )
        rows = (await self.db.execute(stmt)).all()
        return [
            (r[0], r[1], r[2], r[3], int(r[4]), int(r[5]), Decimal(r[6]))
            for r in rows
        ]

    async def by_user(
        self,
        *,
        department_uid: UUID | None,
        project_uid: UUID | None = None,
        user_uid: UUID | None = None,
        from_time: datetime | None,
        to_time: datetime | None,
    ) -> list[tuple[UUID | None, str | None, str | None, int, int, Decimal]]:
        """依使用者彙總;user_uid 為 NULL 的紀錄(歷史代理錯誤)外連線顯示為 unknown。"""
        stmt = (
            select(
                UsageLog.user_uid,
                User.username,
                User.employee_id,
                func.count(UsageLog.pid),
                func.coalesce(func.sum(UsageLog.total_tokens), 0),
                func.coalesce(func.sum(UsageLog.cost_usd), 0),
            )
            .select_from(UsageLog)
            .join(User, User.user_uid == UsageLog.user_uid, isouter=True)
            .group_by(UsageLog.user_uid, User.username, User.employee_id)
        )
        stmt = self._apply_filters(
            stmt,
            department_uid=department_uid,
            project_uid=project_uid,
            user_uid=user_uid,
            model=None,
            from_time=from_time,
            to_time=to_time,
            status=None,
        )
        rows = (await self.db.execute(stmt)).all()
        return [
            (r[0], r[1], r[2], int(r[3]), int(r[4]), Decimal(r[5])) for r in rows
        ]

    async def timeseries(
        self,
        *,
        department_uid: UUID | None,
        project_uid: UUID | None = None,
        user_uid: UUID | None = None,
        from_time: datetime | None,
        to_time: datetime | None,
        granularity: str = "day",
    ) -> list[tuple[datetime, int, int, Decimal]]:
        if granularity not in ("day", "hour"):
            granularity = "day"
        # 切桶以 UTC+8(Asia/Taipei)為準 — 業務在台灣,使用者期望「一天」=「台北一天」。
        # Postgres timezone(zone, timestamptz) 等於 SQL 標準的 `col AT TIME ZONE zone`,
        # 把 timestamptz 轉成台北 wall-clock 的 naive timestamp,再 date_trunc。
        local_ts = func.timezone("Asia/Taipei", UsageLog.created_at)
        bucket = func.date_trunc(granularity, local_ts).label("bucket")
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
            project_uid=project_uid,
            user_uid=user_uid,
            model=None,
            from_time=from_time,
            to_time=to_time,
            status=None,
        )
        rows = (await self.db.execute(stmt)).all()
        # 後端只回有資料的桶,中間沒用量的小時/日要補 0,否則前端折線圖會把不連續的點直接連起來,
        # 看起來不像「每小時一個點」而是「跳著畫」。以 min..max bucket 為範圍,每 step 一個桶填充。
        if not rows:
            return []
        step = timedelta(hours=1) if granularity == "hour" else timedelta(days=1)
        by_bucket: dict[datetime, tuple] = {r[0]: r for r in rows}
        start: datetime = rows[0][0]
        end: datetime = rows[-1][0]
        out: list[tuple[datetime, int, int, Decimal]] = []
        cur = start
        while cur <= end:
            r = by_bucket.get(cur)
            if r is not None:
                out.append((r[0], int(r[1]), int(r[2]), Decimal(r[3])))
            else:
                out.append((cur, 0, 0, Decimal(0)))
            cur += step
        return out
