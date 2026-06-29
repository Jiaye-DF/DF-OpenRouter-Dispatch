"""AI 推薦模型「真實重跑 + 對比裁決」唯讀讀取服務(v2.1.0 重做;對齊 propose §5.4 / §6.1)。

把已落地、目前只存在 DB 裡的推薦模型真實重跑 + 對比裁決列(`ai_model_eval_reruns`)
組成**依用量紀錄(usage_log)分組**的對外讀取視圖 `RerunOverviewPage`,供查詢 API
(task-408)直接回前端「AI 判決總覽」並排比較頁。

職責邊界(對齊既有 `ai_model_eval_result.py`):
- **純讀、無副作用**:只查重跑列(分組分頁)+ 反查 `usage_logs`
  補原模型輸出原文 / 任務輸入原文 + 反查各評審候選補「推薦來源」;**不**打 OpenRouter、
  **不**寫 DB / audit、**不**開 transaction、**不** commit。
- **Decimal → 字串**:金額(`cost_usd` / `original_cost_usd` / `cost_delta_usd`,
  `Numeric(12,6)`)與信心分數(`compare_score`,`Numeric(4,3)`)一律轉 `str`
  (對齊既有「Decimal → string」慣例,避免 JS 浮點誤差);schema 只宣告型別,轉換在本層。
- **輸出原文**:推薦模型取 `ai_model_eval_reruns.response_summary.output_text`;原模型反查
  `usage_logs.response_summary.output_text`(歷史 log 未存快照 → None)。
- **任務輸入原文**:原模型反查 `usage_logs.request_content.text`(同一 row 順手取;
  無 request_content / 無 text / 非字串 → None)。
- **推薦來源(`recommended_by`)**:每筆重跑列帶 `ai_evaluation_uid` + `ai_candidate_uid`;
  對該評審查候選清單(`list_candidates_with_judge`),以候選的 `judge_model_key` 對映回
  「推薦這個模型的評審本人」。**避免 N+1**:同一評審的候選清單只查一次後快取共用
  (本頁分組、組內 rows 同評審,故組內共用一次查詢);查不到 → None。
  不用 `compare_judge_model`(那只有實際跑過裁決才有值,失敗 / 未裁決時 NULL 不可靠)。
- **無資料**:回 `items=[]`、`total=0`、`stats` 全 0(非 None / 非 404)。

`stats` 計數定義(對齊 propose §6.1):
- `keep_count` = `compare_winner='original'`;`swap_count` = `'challenger'`;`tie_count` = `'tie'`;
- `unjudged_count` = `status='success'` 但 `compare_winner IS NULL`(子開關停用);
- `failed_count` = `status != 'success'`(重跑失敗)。
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.ai_model_eval_rerun import AiModelEvalRerun
from app.models.usage_log import UsageLog
from app.repositories.ai_model_eval_rerun import AiModelEvalRerunRepository
from app.repositories.ai_model_evaluation import AiModelEvaluationRepository
from app.repositories.usage_log import UsageLogRepository
from app.schemas.ai_model_eval_rerun_result import (
    RerunGroup,
    RerunOverviewPage,
    RerunRecommendation,
    RerunStats,
    RerunUsageLogInfo,
)

logger = get_logger(__name__)

# Numeric(12,6):金額(USD,微量計)對外字串統一保 6 位小數。
_COST_QUANT = Decimal("0.000001")
# Numeric(4,3):信心分數 0–1 對外字串統一保 3 位小數。
_SCORE_QUANT = Decimal("0.001")

# 全棧顯示時區(對齊 00-overview/05-timezone.md:UTC+8 / Asia/Taipei)。
_TW_TZ = ZoneInfo("Asia/Taipei")


def _to_tw(dt: datetime) -> datetime:
    """把 DB TIMESTAMPTZ(讀回為 UTC tz-aware)轉成 UTC+8,使序列化 ISO 帶 +08:00。

    前端依 04-datetime.md 以正規表示式切 ISO「壁鐘」字串(不轉時區);若這裡不先轉 TW,
    切到的會是 UTC 壁鐘(慢 8 小時)。naive(無 tzinfo)視為 UTC 後轉,容錯既有資料。
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(_TW_TZ)


def _decimal_to_str(value: Decimal | None, quant: Decimal) -> str | None:
    """Decimal → 保指定位數字串(對齊欄位 NUMERIC scale);None 保留 None。

    讀取展示用:不另做 rounding(DB 已是該 scale),quantize 僅統一補零位數。
    """
    if value is None:
        return None
    return str(value.quantize(quant))


def _output_text_of(response_summary: dict[str, Any] | None) -> str | None:
    """從 `response_summary`({output_text, usage?})取輸出原文(對齊 proxy / eval_prompt 慣例)。

    response_summary 為 NULL / 缺 `output_text` / 非字串 / 空字串 → None。
    """
    if not response_summary:
        return None
    output_text = response_summary.get("output_text")
    if isinstance(output_text, str) and output_text:
        return output_text
    return None


def _input_text_of(request_content: dict[str, Any] | None) -> str | None:
    """從 `request_content` 取任務輸入原文(`text` 欄;對齊 usage-log 明細 / rerun service 慣例)。

    request_content 為 NULL / 缺 `text` / 非字串 / 空字串 → None。
    """
    if not request_content:
        return None
    text = request_content.get("text")
    if isinstance(text, str) and text:
        return text
    return None


def _to_usage_log_info(usage_log: UsageLog | None) -> RerunUsageLogInfo | None:
    """同一筆已反查的 `usage_logs` row → `RerunUsageLogInfo`(供 Dialog 顯示);row 為 None → None。

    不另查 DB(沿用 caller 已取的 row);成本 Decimal→str(沿用 _COST_QUANT 慣例)。
    """
    if usage_log is None:
        return None
    return RerunUsageLogInfo(
        pid=usage_log.pid,
        created_at=_to_tw(usage_log.created_at),
        model=usage_log.model,
        status=usage_log.status,
        prompt_tokens=usage_log.prompt_tokens,
        completion_tokens=usage_log.completion_tokens,
        total_tokens=usage_log.total_tokens,
        # cost_usd 為 NOT NULL Decimal,quantize 後必為字串(非 None)。
        cost_usd=str(usage_log.cost_usd.quantize(_COST_QUANT)),
        latency_ms=usage_log.latency_ms,
        used_tools=usage_log.used_tools,
        error_code=usage_log.error_code,
    )


def _to_recommendation(
    row: AiModelEvalRerun, recommended_by: str | None
) -> RerunRecommendation:
    """`AiModelEvalRerun`(ORM 列)→ `RerunRecommendation`(對外);金額 / 分數 Decimal→str。

    `recommended_by` 由 caller 從 candidate 反查 derive 後傳入(推薦此模型的評審 key;查不到 None)。
    """
    return RerunRecommendation(
        rerun_model=row.rerun_model,
        model_uid=row.model_uid,
        output_text=_output_text_of(row.response_summary),
        prompt_tokens=row.prompt_tokens,
        completion_tokens=row.completion_tokens,
        total_tokens=row.total_tokens,
        cost_usd=_decimal_to_str(row.cost_usd, _COST_QUANT),
        cost_delta_usd=_decimal_to_str(row.cost_delta_usd, _COST_QUANT),
        latency_ms=row.latency_ms,
        status=row.status,
        error_code=row.error_code,
        compare_winner=row.compare_winner,
        compare_score=_decimal_to_str(row.compare_score, _SCORE_QUANT),
        compare_reason=row.compare_reason,
        compare_judge_model=row.compare_judge_model,
        recommended_by=recommended_by,
        triggered_at=_to_tw(row.triggered_at),
    )


def _compute_stats(rows: list[AiModelEvalRerun]) -> RerunStats:
    """當頁分組內全部推薦模型列 → 裁決分布彙總(純函式;對齊 propose §6.1)。"""
    keep = swap = tie = unjudged = failed = 0
    for row in rows:
        if row.status != "success":
            failed += 1
        elif row.compare_winner is None:
            unjudged += 1
        elif row.compare_winner == "original":
            keep += 1
        elif row.compare_winner == "challenger":
            swap += 1
        elif row.compare_winner == "tie":
            tie += 1
    return RerunStats(
        total_recommendations=len(rows),
        keep_count=keep,
        swap_count=swap,
        tie_count=tie,
        unjudged_count=unjudged,
        failed_count=failed,
    )


async def build_rerun_overview(
    *,
    db: AsyncSession,
    page: int,
    size: int,
    order: str = "desc",
    pid: int | None = None,
) -> RerunOverviewPage:
    """跨 log 取最新推薦模型重跑 + 對比裁決,組成**依用量紀錄分組**的 AI 判決總覽分頁(純讀)。

    流程(對齊 propose §5.4 / §6.1):
    1. repo `list_grouped_by_usage_log`:取當頁分組鍵(distinct usage_log,組最新時戳優先)
       + 這些 usage_log 底下全部未軟刪重跑列。
    2. 反查 `usage_logs`(同一 row)補各組 `original_output_text`
       (response_summary.output_text)、`original_input_text`(request_content.text)
       與 `usage_log_info`(該筆呼叫基礎 metadata)(純讀;不另查 DB)。
    3. 反查各評審候選補每筆推薦的 `recommended_by`(推薦此模型的評審本人);同評審只查一次後快取
       (避免 N+1)。
    4. 逐組組 `RerunGroup`(原模型輸出 / 輸入 + recommendations[],Decimal→str)。
    5. 彙總當頁 `stats`(裁決分布)。
    6. repo `count_distinct_usage_logs` 取 `total`(分組組數)。

    Args:
        db: AsyncSession(由 endpoint 提供;本函式不開 transaction / 不 commit)。
        page: 1-based 頁碼。
        size: 每頁組數。

    Returns:
        `RerunOverviewPage`(items 依用量紀錄分組,最新優先;無資料 → items=[] / total=0 / stats 全 0)。
    """
    repo = AiModelEvalRerunRepository(db)
    usage_log_repo = UsageLogRepository(db)
    eval_repo = AiModelEvaluationRepository(db)

    ordered_uids, rows = await repo.list_grouped_by_usage_log(
        limit=size, offset=(page - 1) * size, order=order, pid=pid
    )
    total = await repo.count_distinct_usage_logs(pid=pid)

    # 同一 usage_log 的多筆重跑併入同組(保 repo 的 triggered_at DESC 順序)。
    rows_by_log: dict[Any, list[AiModelEvalRerun]] = defaultdict(list)
    for row in rows:
        rows_by_log[row.usage_log_uid].append(row)

    # 推薦來源反查快取:{ai_evaluation_uid: {ai_candidate_uid: judge_model_key}}。
    # 同評審只查一次候選清單後快取(避免 N+1);本頁分組、組內 rows 同評審,組內共用。
    judge_by_eval: dict[UUID, dict[UUID, str | None]] = {}

    async def _recommended_by(row: AiModelEvalRerun) -> str | None:
        """以本列 ai_candidate_uid 對映回「推薦此模型的評審 key」;查不到 / 無候選 → None。"""
        if row.ai_candidate_uid is None:
            return None
        cand_map = judge_by_eval.get(row.ai_evaluation_uid)
        if cand_map is None:
            candidates = await eval_repo.list_candidates_with_judge(
                row.ai_evaluation_uid
            )
            cand_map = {
                cand.ai_candidate_uid: cand.judge_model_key for cand in candidates
            }
            judge_by_eval[row.ai_evaluation_uid] = cand_map
        return cand_map.get(row.ai_candidate_uid)

    items: list[RerunGroup] = []
    for log_uid in ordered_uids:
        group_rows = rows_by_log.get(log_uid, [])
        # 組代表列:取最新一筆(repo 已 DESC,group_rows[0]),供原模型 / 原成本 denormalize。
        head = group_rows[0]
        # 原模型輸出 / 輸入原文反查 usage_logs(同一 row;歷史未存 / log 不存在 → None)。
        usage_log = await usage_log_repo.get_by_uid(log_uid)
        original_output_text = (
            _output_text_of(usage_log.response_summary) if usage_log is not None else None
        )
        original_input_text = (
            _input_text_of(usage_log.request_content) if usage_log is not None else None
        )
        # 同一 row 順手組 usage_log 基礎資訊(供 Dialog 顯示;row 為 None → None)。
        usage_log_info = _to_usage_log_info(usage_log)
        recommendations = [
            _to_recommendation(r, await _recommended_by(r)) for r in group_rows
        ]
        items.append(
            RerunGroup(
                usage_log_uid=log_uid,
                original_model=head.original_model,
                original_output_text=original_output_text,
                original_input_text=original_input_text,
                original_cost_usd=_decimal_to_str(head.original_cost_usd, _COST_QUANT),
                evaluated_at=_to_tw(head.triggered_at),
                usage_log_info=usage_log_info,
                recommendations=recommendations,
            )
        )

    stats = _compute_stats(rows)

    logger.debug(
        "組裝 AI 判決總覽 page=%d size=%d groups=%d total=%d recommendations=%d",
        page,
        size,
        len(items),
        total,
        stats.total_recommendations,
    )

    return RerunOverviewPage(
        items=items, total=total, page=page, size=size, stats=stats
    )
