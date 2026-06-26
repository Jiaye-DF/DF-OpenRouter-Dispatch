"""challenger 重跑結果讀取服務(v2.1.0;對齊 docs/Tasks/v2.1/propose-v2.1.0.md §5.4)。

把 task-405/406 已落地、目前只存在 DB 裡的 challenger 真實重跑 + 對比裁決列
(`ai_model_eval_reruns`)組成對外讀取視圖 `RerunResult[]`,供 task-408 endpoint
包上頂層 wrapper(`RerunListResponse.reruns`)回前端。

職責邊界(對齊既有 `ai_model_eval_result.py`):
- **純讀、無副作用**:只用 task-403 `list_by_usage_log_uid` 查重跑列(預設過濾軟刪),
  不打 OpenRouter、不寫 DB / audit、不開 transaction、不 commit。
- **Decimal → 字串**:金額(`cost_usd` / `original_cost_usd` / `cost_delta_usd`,
  `Numeric(12,6)`)與信心分數(`compare_score`,`Numeric(4,3)`)一律轉 `str`
  (對齊既有「Decimal → string」慣例,避免 JS 浮點誤差);schema 只宣告型別,
  轉換在本層。
- **無重跑列**:回空 list `[]`(非 None / 非 404),與 task-408 的
  `200 + data.reruns=[]` 對齊。`compare_*` 為 NULL 的列(子開關停用)→ 對應欄 None。
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.ai_model_eval_rerun import AiModelEvalRerun
from app.repositories.ai_model_eval_rerun import AiModelEvalRerunRepository
from app.schemas.ai_model_eval_rerun_result import (
    RerunOverviewItem,
    RerunResult,
)

logger = get_logger(__name__)

# Numeric(12,6):金額(USD,微量計)對外字串統一保 6 位小數。
_COST_QUANT = Decimal("0.000001")
# Numeric(4,3):信心分數 0–1 對外字串統一保 3 位小數。
_SCORE_QUANT = Decimal("0.001")


def _decimal_to_str(value: Decimal | None, quant: Decimal) -> str | None:
    """Decimal → 保指定位數字串(對齊欄位 NUMERIC scale);None 保留 None。

    讀取展示用:不另做 rounding(DB 已是該 scale),quantize 僅統一補零位數。
    """
    if value is None:
        return None
    return str(value.quantize(quant))


def _to_rerun_result(row: AiModelEvalRerun) -> RerunResult:
    """`AiModelEvalRerun`(ORM 列)→ `RerunResult`(對外);金額 / 分數 Decimal→str。"""
    return RerunResult(
        rerun_model=row.rerun_model,
        model_uid=row.model_uid,
        prompt_tokens=row.prompt_tokens,
        completion_tokens=row.completion_tokens,
        total_tokens=row.total_tokens,
        cost_usd=_decimal_to_str(row.cost_usd, _COST_QUANT),
        original_cost_usd=_decimal_to_str(row.original_cost_usd, _COST_QUANT),
        cost_delta_usd=_decimal_to_str(row.cost_delta_usd, _COST_QUANT),
        latency_ms=row.latency_ms,
        status=row.status,
        error_code=row.error_code,
        compare_winner=row.compare_winner,
        compare_score=_decimal_to_str(row.compare_score, _SCORE_QUANT),
        compare_reason=row.compare_reason,
        compare_judge_model=row.compare_judge_model,
        triggered_at=row.triggered_at,
    )


async def build_rerun_results(
    usage_log_uid: UUID, *, db: AsyncSession
) -> list[RerunResult]:
    """取單筆 usage_log 對應評審的所有 challenger 重跑並組成對外讀取視圖(純讀,無副作用)。

    流程(對齊 propose §5.4):
    1. 以 task-403 `list_by_usage_log_uid` 取重跑列(預設過濾軟刪)。
    2. 逐列 Decimal→str(金額 6 位 / 信心分數 3 位)→ 組 `RerunResult[]`。

    回傳 `list[RerunResult]`(內層);**無重跑列 → 回空 list `[]`**(非 None)。
    頂層 wrapper 由 task-408 endpoint 組:`RerunListResponse(reruns=<本函式回傳>)`。

    Args:
        usage_log_uid: 來源 usage_logs.usage_log_uid(明細頁手上只有此鍵)。
        db: AsyncSession(由 caller / endpoint 提供;本函式不開 transaction / 不 commit)。

    Returns:
        challenger 重跑對外視圖列;無列 → `[]`。
    """
    repo = AiModelEvalRerunRepository(db)
    rows = await repo.list_by_usage_log_uid(usage_log_uid)

    logger.debug(
        "組裝 challenger 重跑結果 usage_log_uid=%s count=%d",
        usage_log_uid,
        len(rows),
    )

    return [_to_rerun_result(row) for row in rows]


def _to_overview_item(row: AiModelEvalRerun) -> RerunOverviewItem:
    """`AiModelEvalRerun` → `RerunOverviewItem`(跨 log 總覽列;金額 / 分數 Decimal→str)。"""
    return RerunOverviewItem(
        usage_log_uid=row.usage_log_uid,
        original_model=row.original_model,
        rerun_model=row.rerun_model,
        status=row.status,
        error_code=row.error_code,
        cost_usd=_decimal_to_str(row.cost_usd, _COST_QUANT),
        cost_delta_usd=_decimal_to_str(row.cost_delta_usd, _COST_QUANT),
        latency_ms=row.latency_ms,
        compare_winner=row.compare_winner,
        compare_score=_decimal_to_str(row.compare_score, _SCORE_QUANT),
        compare_judge_model=row.compare_judge_model,
        triggered_at=row.triggered_at,
    )


async def build_rerun_overview(
    *, db: AsyncSession, page: int, size: int
) -> tuple[list[RerunOverviewItem], int]:
    """跨 log 取最新 challenger 重跑 + 對比裁決,組成 AI 判決總覽分頁(純讀,無副作用)。

    Args:
        db: AsyncSession(由 endpoint 提供;本函式不開 transaction / 不 commit)。
        page: 1-based 頁碼。
        size: 每頁筆數。

    Returns:
        `(items, total)`:當頁 `RerunOverviewItem[]` 與全體(過濾軟刪)總筆數。
    """
    repo = AiModelEvalRerunRepository(db)
    rows = await repo.list_recent(limit=size, offset=(page - 1) * size)
    total = await repo.count_active()

    logger.debug("組裝 AI 判決總覽 page=%d size=%d total=%d", page, size, total)

    return [_to_overview_item(row) for row in rows], total
