"""判別模型設定 repository(對齊 docs/Design-Base/04-databases/02-soft-delete.md)。

`ai_judge_slot` 有 DB unique 約束;PUT 整批覆寫時須先把舊的有效設定軟刪
(`is_deleted=True, is_active=False`)並 flush,再 insert 新 3 筆(slot=1,2,3),
避免 slot unique 衝突。
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_eval_judge_setting import AiEvalJudgeSetting
from app.models.model import Model


class AiEvalJudgeSettingRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_active(self) -> list[AiEvalJudgeSetting]:
        """目前有效的判別模型設定,依槽位排序。"""
        stmt = (
            select(AiEvalJudgeSetting)
            .where(
                AiEvalJudgeSetting.is_active.is_(True),
                AiEvalJudgeSetting.is_deleted.is_(False),
            )
            .order_by(AiEvalJudgeSetting.ai_judge_slot.asc())
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def soft_delete_active(self) -> None:
        """把目前所有有效設定軟刪(釋放 slot unique 佔用)。"""
        rows = await self.list_active()
        for row in rows:
            row.is_deleted = True
            row.is_active = False
        await self.db.flush()

    def add(self, row: AiEvalJudgeSetting) -> None:
        self.db.add(row)

    async def list_active_models_by_uids(
        self, model_uids: list[UUID]
    ) -> list[Model]:
        """回傳指定 model_uid 中,active(is_active 且未軟刪除)的 models。

        用於驗證 PUT 傳入的 model_uid 皆存在且 active。
        """
        if not model_uids:
            return []
        stmt = select(Model).where(
            Model.model_uid.in_(model_uids),
            Model.is_active.is_(True),
            Model.is_deleted.is_(False),
        )
        return list((await self.db.execute(stmt)).scalars().all())
