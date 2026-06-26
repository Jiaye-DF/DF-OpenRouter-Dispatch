"""評審結果彙總服務(task-303;對齊 docs/Tasks/v2.0/propose-v2.0.3.md §4.3 / §5)。

把 v2.0.1 已落地、目前只存在 DB 裡的三評審結果(父表 dim1/2 + 子表 dim3/4 ×3)
收斂成單一「判決結果」並組成對外讀取視圖 `EvaluationResult`,供 task-304 endpoint
包上頂層 wrapper(`EvaluationResultResponse.evaluation`)回前端。

職責邊界(對齊 propose §4.3):
- **純讀、無副作用**:只查父列 + 候選(repository 既有 / 302 新增),不打 OpenRouter、
  不寫 DB、不開 transaction。
- **Decimal → 字串**:子表 `ai_fit_score` 與彙總 avg/min/max 一律轉 `str`(對齊既有
  「Decimal → string」慣例,避免 JS 浮點誤差);schema 只宣告型別,轉換在本層。
- **彙總計算抽成純函式** `_compute_summary`(輸入 `list[CandidateWithJudge]`、不碰 DB),
  讓全部邊界可單元測試(全 null / 平票 / 單票 / self_vote None 不計…)。

endpoint(task-304)如何包 wrapper:`build_evaluation_result` 回 `EvaluationResult | None`;
endpoint 收到後組 `EvaluationResultResponse(evaluation=result)`(`None` → `evaluation=null`,
對齊決議 #6 的 `200 + evaluation=null`)。

定義(逐欄對齊 propose §5):
- 「評審成功」判準:以 `ai_fit_score is not None` 為唯一可觀察錨點(fit_score 是 NUMERIC
  欄位、只有評審成功才會有值);`succeeded_count` 即此計數,`judge_count` 為候選總數。
- `is_split` 分母:用「有非 null `ai_recommend_model` 的候選數」(有效推薦票數),
  非 `succeeded_count`。理由:`recommend_model=null` 的候選對「推薦共識」無意義,以有效
  推薦票數當分母最貼合共識語意(對齊 §5 決議 #5)。
- `summary` / `task_analysis` 何時為 `None`:
  - `summary`:在「有候選且 `succeeded_count >= 1`」時提供;否則(無候選 / 全失敗,對齊
    propose §3 `status='error'` 前端不顯示彙總)為 `None`。
  - `task_analysis`:父表 `ai_task_summary` / `ai_task_intent` / `ai_task_complexity`
    三者皆非 null 時提供;任一缺(未取得首個成功評審值)→ `None`。
"""

from __future__ import annotations

from collections import Counter
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.repositories.ai_model_evaluation import (
    AiModelEvaluationRepository,
    CandidateWithJudge,
)
from app.schemas.ai_model_eval_result import (
    EvalCandidate,
    EvaluationResult,
    EvaluationSummary,
    RecommendConsensus,
    TaskAnalysis,
)

logger = get_logger(__name__)

# NUMERIC(4,3):fit_score 對外字串統一保 3 位小數(對齊 propose §5 / schema 註)。
_FIT_QUANT = Decimal("0.001")


def _fit_to_str(value: Decimal | None) -> str | None:
    """Decimal fit_score → 保 3 位小數字串(對齊 NUMERIC(4,3) 呈現);None 保留 None。"""
    if value is None:
        return None
    return str(value.quantize(_FIT_QUANT, rounding=ROUND_HALF_UP))


def _compute_recommend_consensus(
    candidates: list[CandidateWithJudge],
) -> RecommendConsensus:
    """三評審 `ai_recommend_model` 收斂成推薦共識(眾數 + 分歧判定)。

    - `model`:非 null `ai_recommend_model` 取眾數;平票取任一最高票;全 null → None。
    - `votes`:眾數模型得票數;全 null → 0。
    - `tier`:眾數模型對應的 `ai_recommend_tier`(同模型 tier 應一致,取該模型任一候選的
      tier);null 安全。
    - `is_split`:`(top_votes*2 <= valid_recommend) and valid_recommend > 1`,分母為
      **有效推薦票數**(非 null recommend_model 的候選數),非 succeeded_count。
      2:1→False、1:1:1→True、1:1→True、單票→False、全 null→False。
    """
    voters = [c for c in candidates if c.ai_recommend_model is not None]
    valid_recommend = len(voters)
    if valid_recommend == 0:
        return RecommendConsensus(model=None, tier=None, votes=0, is_split=False)

    counts = Counter(c.ai_recommend_model for c in voters)
    # most_common(1) 在平票時取任一最高票(對齊 §5「平票 → 取任一最高票」)。
    top_model, top_votes = counts.most_common(1)[0]

    # 眾數模型對應 tier:取該模型任一候選的 tier(同模型應一致)。
    top_tier = next(
        (c.ai_recommend_tier for c in voters if c.ai_recommend_model == top_model),
        None,
    )

    is_split = (top_votes * 2 <= valid_recommend) and valid_recommend > 1
    return RecommendConsensus(
        model=top_model,
        tier=top_tier,
        votes=top_votes,
        is_split=is_split,
    )


def _compute_summary(candidates: list[CandidateWithJudge]) -> EvaluationSummary:
    """三評審 → 單一彙總(純函式;對齊 propose §5 逐欄規則)。

    判準:「評審成功」= `ai_fit_score is not None`(唯一可觀察錨點)。
    avg/min/max 取非 null fit_score;avg 四捨五入到 3 位(ROUND_HALF_UP)後轉字串;
    全 null → None。`self_vote_count` 只計 `ai_self_vote is True`(None 不計)。
    """
    judge_count = len(candidates)
    fit_scores = [c.ai_fit_score for c in candidates if c.ai_fit_score is not None]
    succeeded_count = len(fit_scores)

    if fit_scores:
        avg = (sum(fit_scores, Decimal(0)) / Decimal(len(fit_scores))).quantize(
            _FIT_QUANT, rounding=ROUND_HALF_UP
        )
        avg_fit_score: str | None = str(avg)
        min_fit_score = _fit_to_str(min(fit_scores))
        max_fit_score = _fit_to_str(max(fit_scores))
    else:
        avg_fit_score = None
        min_fit_score = None
        max_fit_score = None

    self_vote_count = sum(1 for c in candidates if c.ai_self_vote is True)

    return EvaluationSummary(
        judge_count=judge_count,
        succeeded_count=succeeded_count,
        avg_fit_score=avg_fit_score,
        min_fit_score=min_fit_score,
        max_fit_score=max_fit_score,
        recommend_consensus=_compute_recommend_consensus(candidates),
        self_vote_count=self_vote_count,
    )


def _to_eval_candidate(cand: CandidateWithJudge) -> EvalCandidate:
    """`CandidateWithJudge`(repo)→ `EvalCandidate`(對外);fit_score Decimal→str。"""
    return EvalCandidate(
        ai_candidate_uid=cand.ai_candidate_uid,
        judge_model_uid=cand.model_uid,  # repo 的 model_uid 即對外 judge_model_uid
        judge_model_key=cand.judge_model_key,
        judge_model_name=cand.judge_model_name,
        ai_recommend_model=cand.ai_recommend_model,
        ai_recommend_tier=cand.ai_recommend_tier,
        ai_recommend_reason=cand.ai_recommend_reason,
        ai_fit_score=_fit_to_str(cand.ai_fit_score),
        ai_self_vote=cand.ai_self_vote,
    )


async def build_evaluation_result(
    usage_log_uid: UUID, *, db: AsyncSession
) -> EvaluationResult | None:
    """取單筆 usage_log 的評審結果並組成對外讀取視圖(純讀,無副作用)。

    流程(對齊 propose §4.3):
    1. 以 `find_by_usage_log_uid` 取父列;**None → 回 None**(對應 endpoint
       `evaluation=null`,決議 #6:log 已知存在、僅未評審)。
    2. 以 `list_candidates_with_judge(parent.ai_evaluation_uid)` 取候選(含 join 裁判
       key/name,避免 N+1)。
    3. 算彙總(§5)→ 組 `EvaluationResult`(`task_analysis` / `summary` / `candidates`)。

    回傳 `EvaluationResult | None`(內層);頂層 wrapper 由 task-304 endpoint 組:
    `EvaluationResultResponse(evaluation=<本函式回傳>)`(None → `evaluation=null`)。

    `summary` / `task_analysis` 的 None 判準見模組 docstring。

    Args:
        usage_log_uid: 來源 usage_logs.usage_log_uid(明細頁手上只有此鍵,1:1 直查)。
        db: AsyncSession(由 caller / endpoint 提供;本函式不開 transaction)。

    Returns:
        評審結果內層視圖;無父列(未評審)→ None。
    """
    repo = AiModelEvaluationRepository(db)

    parent = await repo.find_by_usage_log_uid(usage_log_uid)
    if parent is None:
        return None

    candidates = await repo.list_candidates_with_judge(parent.ai_evaluation_uid)

    summary = _compute_summary(candidates)
    # 有候選且至少一筆評審成功才提供彙總;否則(無候選 / 全失敗 status='error')→ None。
    summary_out = summary if summary.succeeded_count >= 1 else None

    # 父表 dim1/2 三欄皆非 null 才提供任務分析(取「首個成功評審值」,缺則整塊 None)。
    if (
        parent.ai_task_summary is not None
        and parent.ai_task_intent is not None
        and parent.ai_task_complexity is not None
    ):
        task_analysis: TaskAnalysis | None = TaskAnalysis(
            summary=parent.ai_task_summary,
            intent=parent.ai_task_intent,
            complexity=parent.ai_task_complexity,
        )
    else:
        task_analysis = None

    logger.debug(
        "組裝評審結果 usage_log_uid=%s status=%s judge_count=%d succeeded=%d",
        usage_log_uid,
        parent.status,
        summary.judge_count,
        summary.succeeded_count,
    )

    return EvaluationResult(
        ai_evaluation_uid=parent.ai_evaluation_uid,
        usage_log_uid=parent.usage_log_uid,
        ai_original_model=parent.ai_original_model,
        status=parent.status,
        ai_evaluated_at=parent.ai_evaluated_at,
        task_analysis=task_analysis,
        summary=summary_out,
        candidates=[_to_eval_candidate(c) for c in candidates],
    )
