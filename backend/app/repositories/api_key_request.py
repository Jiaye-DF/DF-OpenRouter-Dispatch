from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key_request import ApiKeyRequest


class ApiKeyRequestRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_uid(self, request_uid: UUID) -> ApiKeyRequest | None:
        stmt = select(ApiKeyRequest).where(
            ApiKeyRequest.request_uid == request_uid,
            ApiKeyRequest.is_deleted.is_(False),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list(
        self,
        *,
        page: int,
        size: int,
        applicant_user_uid: UUID | None = None,
        status: str | None = None,
        q: str | None = None,
        department_code: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
    ) -> tuple[list[ApiKeyRequest], int]:
        conds = [ApiKeyRequest.is_deleted.is_(False)]
        if applicant_user_uid is not None:
            conds.append(ApiKeyRequest.applicant_user_uid == applicant_user_uid)
        if status:
            conds.append(ApiKeyRequest.status == status)
        if department_code:
            conds.append(ApiKeyRequest.department_code == department_code)
        if from_time is not None:
            conds.append(ApiKeyRequest.created_at >= from_time)
        if to_time is not None:
            conds.append(ApiKeyRequest.created_at <= to_time)
        if q and q.strip():
            kw = f"%{q.strip().lower()}%"
            conds.append(
                or_(
                    func.lower(ApiKeyRequest.project_name).like(kw),
                    func.lower(ApiKeyRequest.owner_name).like(kw),
                    func.lower(ApiKeyRequest.owner_email).like(kw),
                    func.lower(ApiKeyRequest.department_name).like(kw),
                    func.lower(ApiKeyRequest.department_code).like(kw),
                )
            )
        stmt = (
            select(ApiKeyRequest)
            .where(*conds)
            .order_by(ApiKeyRequest.pid.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        count_stmt = select(func.count()).select_from(ApiKeyRequest).where(*conds)
        items = list((await self.db.execute(stmt)).scalars().all())
        total = int((await self.db.execute(count_stmt)).scalar_one())
        return items, total

    def add(self, row: ApiKeyRequest) -> None:
        self.db.add(row)

    async def update_fields(self, row: ApiKeyRequest, **fields: Any) -> None:
        for k, v in fields.items():
            setattr(row, k, v)
        await self.db.flush()
