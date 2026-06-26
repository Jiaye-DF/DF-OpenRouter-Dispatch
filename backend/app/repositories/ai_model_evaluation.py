"""評審結果 repository(對齊 docs/Design-Base/03-backend/03-async-and-tx.md 多表單一 tx
與 docs/Design-Base/04-databases/02-soft-delete.md 軟刪除命名)。

寫入路徑(`create_evaluation_with_candidates`)於單一 transaction 內寫父表
`ai_model_evaluations`(dim1/2)+ 三筆子表 `ai_model_eval_candidates`(dim3/4),
中途 raise 則整批 rollback,不留半寫。

冪等以父表 `usage_log_uid`(DB UNIQUE)為界:已存在 → 不重寫,直接回既有父列。

派發游標走 `usage_logs.ai_evaluated_at`(NULL=未評審):
`mark_usage_log_evaluated` 設為 `now()`;`fetch_unevaluated_log_uids` 撈 NULL 待派發筆。

> 設計決議(2026-06-25):父表 summary/intent 三評審不一致時取「首個成功評審值」,
> 由呼叫端(task-105 執行服務)決定後傳入本層;本層只負責落地。
> `raw_json` 為可選參數、預設不存(本版 schema 無對應欄位),呼叫端不傳則不寫 raw。
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils import uuid7

from app.models.ai_model_eval_candidate import AiModelEvalCandidate
from app.models.ai_model_evaluation import AiModelEvaluation
from app.models.usage_log import UsageLog


@dataclass(frozen=True)
class CandidateInput:
    """單一判別模型的評審候選輸入(對應一筆子表 dim3/4)。"""

    model_uid: UUID
    ai_recommend_model: str | None = None
    ai_recommend_tier: str | None = None
    ai_recommend_reason: str | None = None
    ai_fit_score: Decimal | None = None
    ai_self_vote: bool | None = None


class AiModelEvaluationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def find_by_usage_log_uid(
        self, usage_log_uid: UUID
    ) -> AiModelEvaluation | None:
        """依來源 log 取評審父列(預設過濾軟刪)。"""
        stmt = select(AiModelEvaluation).where(
            AiModelEvaluation.usage_log_uid == usage_log_uid,
            AiModelEvaluation.is_deleted.is_(False),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def find_by_usage_log_uid_including_deleted(
        self, usage_log_uid: UUID
    ) -> AiModelEvaluation | None:
        """依來源 log 取評審父列(含已軟刪)。"""
        stmt = select(AiModelEvaluation).where(
            AiModelEvaluation.usage_log_uid == usage_log_uid
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def create_evaluation_with_candidates(
        self,
        *,
        usage_log_uid: UUID,
        ai_original_model: str,
        candidates: list[CandidateInput],
        department_uid: UUID | None = None,
        user_uid: UUID | None = None,
        ai_task_summary: str | None = None,
        ai_task_intent: str | None = None,
        ai_task_complexity: str | None = None,
        status: str | None = None,
        evaluation_succeeded: bool = True,
        mark_evaluated: bool = True,
        raw_json: dict | None = None,
    ) -> AiModelEvaluation:
        """於單一 transaction 寫父表 + 三筆子表 + 標來源 log 游標;冪等以 `usage_log_uid` 防重。

        - 已存在(以 `usage_log_uid` UNIQUE 判定)→ 不重寫,回既有父列(no-op)。
          本版失敗為終局、不重派,故 no-op 安全(不放寬冪等)。
        - `evaluation_succeeded`:本次評審成敗;決定父表 `status`(未顯式給 `status` 時)
          與來源 log `ai_evaluated_status`(1=成功 / 0=失敗)。
        - `mark_evaluated`:是否在同一 transaction 標來源 log 游標
          (`ai_evaluated_at = now()` + `ai_evaluated_status`);失敗也算「跑過」、會標。
        - 父 + 三子 + 標旗標為**同一原子單位**;中途 raise → 整批 rollback
          (由 `begin_nested()` / `begin()` 保證)。
        - `raw_json`:可選稽核 payload,**預設不存**(本版 schema 無欄位);
          傳入亦不落地,僅保留介面相容,待後續版本以 migration 增補欄位後切換。
        """
        del raw_json  # 本版不落地;保留參數供日後切換

        existing = await self.find_by_usage_log_uid_including_deleted(usage_log_uid)
        if existing is not None:
            return existing

        resolved_status = status or ("evaluated" if evaluation_succeeded else "error")

        # caller 已包 begin → 用 SAVEPOINT;否則開新 transaction。兩者皆保證中途 raise rollback。
        tx_cm = (
            self.db.begin_nested() if self.db.in_transaction() else self.db.begin()
        )

        async with tx_cm:
            parent = AiModelEvaluation(
                ai_evaluation_uid=UUID(str(uuid7())),
                usage_log_uid=usage_log_uid,
                department_uid=department_uid,
                user_uid=user_uid,
                ai_original_model=ai_original_model,
                ai_task_summary=ai_task_summary,
                ai_task_intent=ai_task_intent,
                ai_task_complexity=ai_task_complexity,
                status=resolved_status,
                ai_evaluated_at=func.now() if mark_evaluated else None,
            )
            self.db.add(parent)
            await self.db.flush()

            for cand in candidates:
                self.db.add(
                    AiModelEvalCandidate(
                        ai_candidate_uid=UUID(str(uuid7())),
                        ai_evaluation_uid=parent.ai_evaluation_uid,
                        model_uid=cand.model_uid,
                        ai_recommend_model=cand.ai_recommend_model,
                        ai_recommend_tier=cand.ai_recommend_tier,
                        ai_recommend_reason=cand.ai_recommend_reason,
                        ai_fit_score=cand.ai_fit_score,
                        ai_self_vote=cand.ai_self_vote,
                    )
                )
            await self.db.flush()

            if mark_evaluated:
                await self.mark_usage_log_evaluated(
                    usage_log_uid, success=evaluation_succeeded
                )

        await self.db.refresh(parent)
        return parent

    async def list_candidates(
        self, ai_evaluation_uid: UUID
    ) -> list[AiModelEvalCandidate]:
        """取某評審父列下的候選(預設過濾軟刪)。"""
        stmt = select(AiModelEvalCandidate).where(
            AiModelEvalCandidate.ai_evaluation_uid == ai_evaluation_uid,
            AiModelEvalCandidate.is_deleted.is_(False),
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def mark_usage_log_evaluated(
        self, usage_log_uid: UUID, *, success: bool
    ) -> None:
        """標來源 log 最新一次評審執行(`ai_evaluated_at = now()`,全棧 UTC+8)。

        `ai_evaluated_status` 1=成功 / 0=失敗;成敗皆寫(失敗也算「跑過」、不重撈)。
        """
        stmt = (
            update(UsageLog)
            .where(
                UsageLog.usage_log_uid == usage_log_uid,
                UsageLog.is_deleted.is_(False),
            )
            .values(ai_evaluated_at=func.now(), ai_evaluated_status=1 if success else 0)
        )
        await self.db.execute(stmt)

    async def fetch_unevaluated_log_uids(self, limit: int) -> list[UUID]:
        """撈尚未評審(`ai_evaluated_at IS NULL`)的 usage log uid 供 dispatcher 派發。"""
        stmt = (
            select(UsageLog.usage_log_uid)
            .where(
                UsageLog.ai_evaluated_at.is_(None),
                UsageLog.is_deleted.is_(False),
            )
            .order_by(UsageLog.created_at.desc())
            .limit(limit)
        )
        return list((await self.db.execute(stmt)).scalars().all())
