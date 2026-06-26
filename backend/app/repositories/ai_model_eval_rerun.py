"""challenger 重跑列 repository(v2.1.0)。

寫入(`create_rerun`)冪等以 `UNIQUE(ai_evaluation_uid, rerun_model)` 為界:
已存在(不分軟刪)→ 不重寫,直接回既有列(對齊 `ai_model_evaluation.py`
以 `usage_log_uid` 防重的冪等慣例)。

讀取(`list_by_*`)供查詢 service(task-407)消費,預設過濾軟刪
(對齊 `docs/Design-Base/04-databases/02-soft-delete.md` 命名:無後綴=過濾版)。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils import uuid7

from app.models.ai_model_eval_rerun import AiModelEvalRerun


@dataclass(frozen=True)
class RerunInput:
    """單一 challenger 重跑 + 對比裁決結果輸入(對應一筆 `ai_model_eval_reruns`)。

    對齊 `ai_model_evaluation.py` 的 `CandidateInput` dataclass 風格:呼叫端
    (task-406 重跑執行服務)算好真實 API 結果 + discriminator 裁決後傳入,
    本層只負責落地。冪等鍵為 `(ai_evaluation_uid, rerun_model)`。
    """

    ai_evaluation_uid: UUID
    usage_log_uid: UUID
    original_model: str
    rerun_model: str
    triggered_at: datetime
    status: str = "success"
    ai_candidate_uid: UUID | None = None
    model_uid: UUID | None = None
    request_content: dict[str, Any] | None = None
    response_summary: dict[str, Any] | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    cost_usd: Decimal | None = None
    original_cost_usd: Decimal | None = None
    cost_delta_usd: Decimal | None = None
    latency_ms: int | None = None
    error_code: str | None = None
    openrouter_generation_id: str | None = None
    compare_winner: str | None = None
    compare_score: Decimal | None = None
    compare_reason: str | None = None
    compare_judge_model: str | None = None


class AiModelEvalRerunRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def find_by_evaluation_and_model_including_deleted(
        self, ai_evaluation_uid: UUID, rerun_model: str
    ) -> AiModelEvalRerun | None:
        """依冪等鍵 `(ai_evaluation_uid, rerun_model)` 取列(含已軟刪)。

        冪等判定須涵蓋軟刪列(`UNIQUE` 不分軟刪),否則軟刪後重跑會撞唯一鍵。
        """
        stmt = select(AiModelEvalRerun).where(
            AiModelEvalRerun.ai_evaluation_uid == ai_evaluation_uid,
            AiModelEvalRerun.rerun_model == rerun_model,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def create_rerun(self, data: RerunInput) -> AiModelEvalRerun:
        """寫一筆 challenger 重跑(原子);冪等以 `(ai_evaluation_uid, rerun_model)` 防重。

        已存在(含軟刪)→ 不重寫,回既有列(no-op);否則插入新列。
        caller 已包 begin → 用 SAVEPOINT;否則開新 transaction
        (對齊 `create_evaluation_with_candidates` 模式,中途 raise 整批 rollback)。
        """
        existing = await self.find_by_evaluation_and_model_including_deleted(
            data.ai_evaluation_uid, data.rerun_model
        )
        if existing is not None:
            return existing

        tx_cm = (
            self.db.begin_nested() if self.db.in_transaction() else self.db.begin()
        )
        async with tx_cm:
            rerun = AiModelEvalRerun(
                ai_eval_rerun_uid=UUID(str(uuid7())),
                ai_evaluation_uid=data.ai_evaluation_uid,
                usage_log_uid=data.usage_log_uid,
                ai_candidate_uid=data.ai_candidate_uid,
                original_model=data.original_model,
                rerun_model=data.rerun_model,
                model_uid=data.model_uid,
                request_content=data.request_content,
                response_summary=data.response_summary,
                prompt_tokens=data.prompt_tokens,
                completion_tokens=data.completion_tokens,
                total_tokens=data.total_tokens,
                cost_usd=data.cost_usd,
                original_cost_usd=data.original_cost_usd,
                cost_delta_usd=data.cost_delta_usd,
                latency_ms=data.latency_ms,
                status=data.status,
                error_code=data.error_code,
                openrouter_generation_id=data.openrouter_generation_id,
                compare_winner=data.compare_winner,
                compare_score=data.compare_score,
                compare_reason=data.compare_reason,
                compare_judge_model=data.compare_judge_model,
                triggered_at=data.triggered_at,
            )
            self.db.add(rerun)
            await self.db.flush()

        await self.db.refresh(rerun)
        return rerun

    async def list_by_usage_log_uid(
        self, usage_log_uid: UUID
    ) -> list[AiModelEvalRerun]:
        """取某 log 對應評審的所有 challenger 重跑(預設過濾軟刪)。"""
        stmt = select(AiModelEvalRerun).where(
            AiModelEvalRerun.usage_log_uid == usage_log_uid,
            AiModelEvalRerun.is_deleted.is_(False),
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_by_evaluation_uid(
        self, ai_evaluation_uid: UUID
    ) -> list[AiModelEvalRerun]:
        """以父評審 UID 取所有 challenger 重跑(預設過濾軟刪)。"""
        stmt = select(AiModelEvalRerun).where(
            AiModelEvalRerun.ai_evaluation_uid == ai_evaluation_uid,
            AiModelEvalRerun.is_deleted.is_(False),
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_grouped_by_usage_log(
        self, *, limit: int, offset: int
    ) -> tuple[list[UUID], list[AiModelEvalRerun]]:
        """依用量紀錄分組分頁(供 AI 判決總覽頁,預設過濾軟刪)。

        分組策略(對齊 propose §5.4「依用量紀錄分組」):
        1. 取 distinct `usage_log_uid`,以該組**最新 `triggered_at`** 排序(最新組優先),
           `limit`/`offset` 以**組**為單位分頁。
        2. 撈這些 usage_log 底下全部(未軟刪)重跑列(`triggered_at DESC`),供 service
           併入各組 `recommendations[]`。

        每列已自帶 `usage_log_uid` / `original_model`,無需 join 父表 / usage_logs。

        Returns:
            `(ordered_usage_log_uids, rows)`:
            - `ordered_usage_log_uids`:當頁分組鍵(已按組最新時戳排序,供 service 保序組裝)。
            - `rows`:這些 usage_log 底下的全部重跑列(未軟刪,`triggered_at DESC`)。
        """
        # 1) 以 usage_log 為單位取「組最新時戳」,排序分頁取當頁分組鍵。
        group_stmt = (
            select(
                AiModelEvalRerun.usage_log_uid,
                func.max(AiModelEvalRerun.triggered_at).label("latest"),
            )
            .where(AiModelEvalRerun.is_deleted.is_(False))
            .group_by(AiModelEvalRerun.usage_log_uid)
            .order_by(func.max(AiModelEvalRerun.triggered_at).desc())
            .limit(limit)
            .offset(offset)
        )
        ordered_uids = [
            row[0] for row in (await self.db.execute(group_stmt)).all()
        ]
        if not ordered_uids:
            return [], []

        # 2) 撈這些 usage_log 底下全部未軟刪重跑列(service 再 group 進各組)。
        rows_stmt = (
            select(AiModelEvalRerun)
            .where(
                AiModelEvalRerun.is_deleted.is_(False),
                AiModelEvalRerun.usage_log_uid.in_(ordered_uids),
            )
            .order_by(AiModelEvalRerun.triggered_at.desc())
        )
        rows = list((await self.db.execute(rows_stmt)).scalars().all())
        return ordered_uids, rows

    async def count_distinct_usage_logs(self) -> int:
        """跨 log 分組組數(distinct usage_log,過濾軟刪),供分頁 total。"""
        stmt = (
            select(func.count(func.distinct(AiModelEvalRerun.usage_log_uid)))
            .select_from(AiModelEvalRerun)
            .where(AiModelEvalRerun.is_deleted.is_(False))
        )
        return int((await self.db.execute(stmt)).scalar_one())
