from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model import Model


class ModelRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def find_by_key(self, mid: str) -> Model | None:
        stmt = select(Model).where(
            Model.model_key == mid,
            Model.is_deleted.is_(False),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_uid(self, model_uid: UUID) -> Model | None:
        stmt = select(Model).where(
            Model.model_uid == model_uid,
            Model.is_deleted.is_(False),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_active(self) -> list[Model]:
        stmt = select(Model).where(
            Model.is_active.is_(True),
            Model.is_deleted.is_(False),
        ).order_by(Model.model_key.asc())
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_all(self, *, include_inactive: bool = False) -> list[Model]:
        """一次回傳全部模型(不分頁);分頁與其餘篩選交由前端處理。"""
        stmt = select(Model).where(Model.is_deleted.is_(False))
        if not include_inactive:
            stmt = stmt.where(Model.is_active.is_(True))
        stmt = stmt.order_by(Model.model_key.asc())
        return list((await self.db.execute(stmt)).scalars().all())

    def add(self, row: Model) -> None:
        self.db.add(row)

    async def update_admin_fields(self, model_uid: UUID, **patch: Any) -> Model | None:
        """admin 僅可改 is_active / tier_key;其他欄位由呼叫端把關。"""
        row = await self.get_by_uid(model_uid)
        if row is None:
            return None
        for k, v in patch.items():
            setattr(row, k, v)
        await self.db.flush()
        return row

    async def update_fields(self, row: Model, **fields: Any) -> None:
        for k, v in fields.items():
            setattr(row, k, v)
        await self.db.flush()

    async def activate_all_openrouter(self) -> int:
        """啟用全部 OpenRouter 模型;回傳本次被啟用(原為停用)的筆數。"""
        stmt = (
            update(Model)
            .where(
                Model.provider == "openrouter",
                Model.is_deleted.is_(False),
                Model.is_active.is_(False),
            )
            .values(is_active=True)
        )
        result = await self.db.execute(stmt)
        await self.db.flush()
        return result.rowcount or 0

    async def apply_whitelist_openrouter(self, whitelist: set[str]) -> tuple[int, int]:
        """以白名單重套 OpenRouter 模型可用性:白名單內啟用、其餘停用。

        回傳 (activated, deactivated) —— 各為「狀態實際改變」的筆數。
        whitelist 為空時等同停用全部 OpenRouter 模型。
        """
        # 白名單內、原為停用 → 啟用
        activated = 0
        if whitelist:
            act_stmt = (
                update(Model)
                .where(
                    Model.provider == "openrouter",
                    Model.is_deleted.is_(False),
                    Model.is_active.is_(False),
                    Model.model_key.in_(whitelist),
                )
                .values(is_active=True)
            )
            activated = (await self.db.execute(act_stmt)).rowcount or 0

        # 白名單外、原為啟用 → 停用(白名單為空時等同停用全部)
        deact_stmt = (
            update(Model)
            .where(
                Model.provider == "openrouter",
                Model.is_deleted.is_(False),
                Model.is_active.is_(True),
            )
            .values(is_active=False)
        )
        if whitelist:
            deact_stmt = deact_stmt.where(Model.model_key.notin_(whitelist))
        deactivated = (await self.db.execute(deact_stmt)).rowcount or 0
        await self.db.flush()
        return activated, deactivated
