from uuid import UUID

from sqlalchemy import func, select
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
    ) -> tuple[list[ApiKeyRequest], int]:
        stmt = select(ApiKeyRequest).where(ApiKeyRequest.is_deleted.is_(False))
        count_stmt = (
            select(func.count())
            .select_from(ApiKeyRequest)
            .where(ApiKeyRequest.is_deleted.is_(False))
        )
        if applicant_user_uid is not None:
            stmt = stmt.where(ApiKeyRequest.applicant_user_uid == applicant_user_uid)
            count_stmt = count_stmt.where(
                ApiKeyRequest.applicant_user_uid == applicant_user_uid
            )
        stmt = stmt.order_by(ApiKeyRequest.pid.desc()).offset((page - 1) * size).limit(size)
        items = list((await self.db.execute(stmt)).scalars().all())
        total = int((await self.db.execute(count_stmt)).scalar_one())
        return items, total

    def add(self, row: ApiKeyRequest) -> None:
        self.db.add(row)
