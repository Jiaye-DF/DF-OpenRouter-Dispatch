"""評審重跑核心服務(task-405;對齊 docs/Tasks/v2.1/propose-v2.1.0.md §5.2 / §5.3)。

對單筆已完成評審(`ai_model_evaluations`)做「真實重跑 + 對比裁決(GAN 閉環)」的純業務核心
(無排程依賴,可獨立測,對齊 `ai_model_eval.evaluate_usage_log` 風格):

1. 取父評審 + 候選(`list_candidates_with_judge`)→ 算待重跑集合
   = `{三裁判推薦模型} − {原模型}`(**去重**,決議 #4;`ai_candidate_uid` 取代表者)。
2. **跳過條件**(決議:標終局不重跑):無任何「推薦 ≠ 原模型」→ `mark_reran(status=1)`、
   challenger 0 筆。
3. 對每個 challenger **串行**(非併發,§5.2 定案)逐一處理:
   - 組原輸入快照 payload → `chat_completion`(非串流,`DEFAULT_OPENROUTER_KEY`,
     **不**寫 `usage_logs`)→ 解析輸出 / usage → 算 `cost_usd`(沿用 proxy 計費:
     取回應 `usage.cost` / `total_cost`)→ `cost_delta = challenger − original`
     (無原成本 → NULL)。
   - **discriminator**(`AI_RERUN_DISCRIMINATOR_ENABLED=true` 才跑,決議 #2 推薦者自我裁決):
     用 **推薦該 challenger 的評審模型本人** 當裁判,`build_discriminator_prompt`(task-404)
     **盲化**比「原輸出 vs challenger 輸出」→ `winner`(映射回 original/challenger)+
     `score`(信心)+ `reason`;`compare_judge_model` = 該裁判 key。子開關 false →
     `compare_*` 留 NULL,仍寫客觀指標列。
   - `create_rerun(...)` 寫一筆(原子)。
4. **單一 challenger 失敗不阻斷其他**;全 challenger 失敗 → `mark_reran(status=0)`;
   ≥1 成功 → `mark_reran(status=1)`。

錯誤對外一律收斂為 `AppError`(通用訊息),完整例外 / 原始回覆只進結構化 log;
log 中**不**輸出 API key 等機密(對齊 `03-backend/05-exceptions-and-logging.md`)。

設計決議(2026-06-26,user 拍板):
- discriminator = **推薦該 challenger 的評審模型本人**(自我裁決,非固定單一裁判);
  去重取代表者裁判(決議 #2 / #4)。
- **盲化裁決**(決議 #7):A/B 與 original/challenger 的隨機映射由本 service 決定後事後
  還原(prompt 端不知模型名);測試可注入固定映射(`blind_swap`)。
- `cost_delta = challenger − original`,無原成本 → NULL(決議 §5.2)。
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.openrouter.client import OpenRouterClient
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.models.ai_model_evaluation import AiModelEvaluation
from app.repositories.ai_model_eval_rerun import (
    AiModelEvalRerunRepository,
    RerunInput,
)
from app.repositories.ai_model_evaluation import (
    AiModelEvaluationRepository,
    CandidateWithJudge,
)
from app.repositories.model import ModelRepository
from app.repositories.usage_log import UsageLogRepository
from app.schemas.ai_model_eval import DiscriminatorWinner
from app.services.ai_model_eval_rerun_prompt import (
    _parse_discriminator_content,
    build_discriminator_prompt,
)

logger = get_logger(__name__)

_TW_TZ = ZoneInfo("Asia/Taipei")


def _now_tw() -> datetime:
    """取現在時間(全棧鎖 UTC+8 / Asia/Taipei,對齊 00-overview/05-timezone.md)。"""
    return datetime.now(_TW_TZ)


@dataclass(frozen=True)
class _Challenger:
    """待重跑的單一 challenger(去重後;representative 候選承載裁判與來源候選資訊)。"""

    rerun_model: str
    ai_candidate_uid: UUID | None
    judge_model_key: str | None


@dataclass(frozen=True)
class _ChallengerOutcome:
    """單一 challenger 真實重跑的客觀結果(成功才帶;失敗 status='error')。"""

    output_text: str
    response_summary: dict[str, Any]
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    cost_usd: Decimal | None
    latency_ms: int | None
    openrouter_generation_id: str | None


@dataclass(frozen=True)
class _Verdict:
    """discriminator 對比裁決結果(已映射回 original/challenger)。"""

    compare_winner: str
    compare_score: Decimal
    compare_reason: str
    compare_judge_model: str


def _extract_content(resp: dict[str, Any]) -> str:
    """從 OpenRouter chat completion 回應取出第一個 choice 的文字內容(形狀不符 raise)。"""
    choices = resp.get("choices") or []
    if not choices:
        return ""
    raw = choices[0].get("message", {}).get("content")
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        parts: list[str] = []
        for blk in raw:
            if isinstance(blk, dict) and blk.get("type") == "text":
                t = blk.get("text")
                if isinstance(t, str):
                    parts.append(t)
        return "".join(parts)
    return ""


def _extract_cost(usage: dict[str, Any]) -> Decimal | None:
    """從回應 usage 取成本(沿用 proxy 計費:`cost` / `total_cost`);皆無 → None。"""
    raw = usage.get("cost")
    if raw is None:
        raw = usage.get("total_cost")
    if raw is None:
        return None
    return Decimal(str(raw))


def _int_or_none(usage: dict[str, Any], key: str) -> int | None:
    """從 usage 取整數欄位;缺值 → None。"""
    val = usage.get(key)
    if val is None:
        return None
    return int(val)


def _build_challengers(
    candidates: list[CandidateWithJudge], original_model: str
) -> list[_Challenger]:
    """算待重跑集合 = `{裁判推薦模型} − {原模型}`,去重(取首個推薦該模型的候選為代表)。

    決議 #4:三裁判推薦同 challenger → 合併一筆,`ai_candidate_uid` 取代表者
    (首個推薦該模型的候選)。推薦 = 原模型或空 → 跳過(維持原模型不重跑)。
    """
    seen: set[str] = set()
    out: list[_Challenger] = []
    for cand in candidates:
        rec = cand.ai_recommend_model
        if not rec or rec == original_model or rec in seen:
            continue
        seen.add(rec)
        out.append(
            _Challenger(
                rerun_model=rec,
                ai_candidate_uid=cand.ai_candidate_uid,
                judge_model_key=cand.judge_model_key,
            )
        )
    return out


async def _run_challenger(
    client: OpenRouterClient,
    *,
    request_content: dict[str, Any],
    rerun_model: str,
    api_key: str,
) -> _ChallengerOutcome:
    """真實重跑單一 challenger(非串流,內部金鑰,**不**寫 usage_logs);失敗則 raise。

    沿用原 log 輸入快照(text / images / tools / files)組 OpenAI-compatible payload。
    """
    text = request_content.get("text")
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": text if isinstance(text, str) else ""}
    ]
    payload: dict[str, Any] = {"model": rerun_model, "messages": messages}

    started = _now_tw()
    resp = await client.chat_completion(payload, api_key=api_key)
    latency_ms = int((_now_tw() - started).total_seconds() * 1000)

    output_text = _extract_content(resp)
    usage = resp.get("usage") or {}
    response_summary: dict[str, Any] = {"output_text": output_text}
    if usage:
        response_summary["usage"] = usage

    return _ChallengerOutcome(
        output_text=output_text,
        response_summary=response_summary,
        prompt_tokens=_int_or_none(usage, "prompt_tokens"),
        completion_tokens=_int_or_none(usage, "completion_tokens"),
        total_tokens=_int_or_none(usage, "total_tokens"),
        cost_usd=_extract_cost(usage),
        latency_ms=latency_ms,
        openrouter_generation_id=(
            str(resp["id"]) if isinstance(resp.get("id"), str) else None
        ),
    )


async def _run_discriminator(
    client: OpenRouterClient,
    *,
    request_content: dict[str, Any],
    original_output: str,
    challenger_output: str,
    judge_model_key: str,
    task_context: str | None,
    api_key: str,
    blind_swap: bool,
) -> _Verdict:
    """盲化對比裁決:推薦該 challenger 的評審本人當裁判,盲選 A/B 後映射回 original/challenger。

    `blind_swap` 決定 A/B 與 original/challenger 的隨機映射(測試可注入固定值):
    - False → A=original、B=challenger;winner=A → original、winner=B → challenger。
    - True  → A=challenger、B=original;winner=A → challenger、winner=B → original。
    映射事後在本 service 還原,prompt 端不知任何模型名(盲化,決議 #7)。失敗則 raise。
    """
    output_a, output_b = (
        (challenger_output, original_output)
        if blind_swap
        else (original_output, challenger_output)
    )
    payload = build_discriminator_prompt(
        request_content,
        output_a,
        output_b,
        task_context=task_context,
    )
    payload["model"] = judge_model_key
    resp = await client.chat_completion(payload, api_key=api_key)
    content = _extract_content(resp)
    verdict = _parse_discriminator_content(content)

    # A/B 還原回 original/challenger(盲化映射)。
    winner_is_a = verdict.winner == DiscriminatorWinner.A
    chose_challenger = winner_is_a if blind_swap else not winner_is_a
    compare_winner = "challenger" if chose_challenger else "original"

    return _Verdict(
        compare_winner=compare_winner,
        compare_score=Decimal(str(verdict.score)),
        compare_reason=verdict.reason or "",
        compare_judge_model=judge_model_key,
    )


async def rerun_evaluation(
    ai_evaluation_uid: UUID,
    *,
    db: AsyncSession,
    client: OpenRouterClient,
    blind_swap: bool | None = None,
) -> None:
    """重跑單筆評審:去重 challenger → 串行真實重跑 → 盲化對比裁決 → 寫一筆 + 標父游標。

    Args:
        ai_evaluation_uid: 待重跑的 `ai_model_evaluations.ai_evaluation_uid`。
        db: AsyncSession(由 caller / task-406 提供)。
        client: OpenRouterClient(內部呼叫,走 DEFAULT_OPENROUTER_KEY)。
        blind_swap: 測試專用 — 固定 A/B 盲化映射(None=每個 challenger 隨機決定)。

    Raises:
        AppError: 前置條件不足(未設金鑰 / 父評審不存在 / 來源 log 不存在)時,對外收斂為
            通用訊息;細節走 log。單一 challenger 呼叫失敗**不**拋(寫 status='error' 列)。
    """
    settings = get_settings()
    api_key = settings.DEFAULT_OPENROUTER_KEY
    if not api_key:
        logger.error(
            "評審重跑略過:未設定內部呼叫金鑰 ai_evaluation_uid=%s", ai_evaluation_uid
        )
        raise AppError("評審重跑暫時無法執行", code=503)

    eval_repo = AiModelEvaluationRepository(db)
    usage_repo = UsageLogRepository(db)
    rerun_repo = AiModelEvalRerunRepository(db)
    model_repo = ModelRepository(db)

    # 取父評審(repository 無 by-uid getter;以 ORM select 取單列,對齊 proxy.py 既有作法,
    # 不拼接 raw SQL)。見 docs/Tasks/v2.1/fixed.md §2。
    parent: AiModelEvaluation | None = (
        await db.execute(
            select(AiModelEvaluation).where(
                AiModelEvaluation.ai_evaluation_uid == ai_evaluation_uid,
                AiModelEvaluation.is_deleted.is_(False),
            )
        )
    ).scalar_one_or_none()
    if parent is None:
        logger.error(
            "評審重跑略過:父評審不存在 ai_evaluation_uid=%s", ai_evaluation_uid
        )
        raise AppError("找不到對應的評審紀錄", code=404)

    usage_log = await usage_repo.get_by_uid(parent.usage_log_uid)
    if usage_log is None:
        logger.error(
            "評審重跑略過:來源 usage_log 不存在 ai_evaluation_uid=%s usage_log_uid=%s",
            ai_evaluation_uid,
            parent.usage_log_uid,
        )
        raise AppError("找不到對應的用量紀錄", code=404)

    original_model = parent.ai_original_model
    request_content = usage_log.request_content or {}
    original_summary = usage_log.response_summary or {}
    original_output = original_summary.get("output_text") or ""
    original_cost: Decimal | None = usage_log.cost_usd
    task_context = parent.ai_task_summary or None

    candidates = await eval_repo.list_candidates_with_judge(ai_evaluation_uid)
    challengers = _build_challengers(candidates, original_model)

    discriminator_enabled = bool(settings.AI_RERUN_DISCRIMINATOR_ENABLED)

    # 跳過條件:無任何「推薦 ≠ 原模型」→ 標終局成功、challenger 0 筆。
    if not challengers:
        await eval_repo.mark_reran(ai_evaluation_uid, status=1)
        logger.info(
            "評審重跑:無有效 challenger(全員維持原模型),標終局 status=1 "
            "ai_evaluation_uid=%s",
            ai_evaluation_uid,
        )
        return

    success_count = 0
    for ch in challengers:
        challenger_model_uid: UUID | None = None
        model_row = await model_repo.find_by_key(ch.rerun_model)
        if model_row is not None:
            challenger_model_uid = model_row.model_uid

        try:
            outcome = await _run_challenger(
                client,
                request_content=request_content,
                rerun_model=ch.rerun_model,
                api_key=api_key,
            )
        except Exception:  # noqa: BLE001
            # 完整例外(上游狀態碼 / 原始 body)只進日誌;不含 api_key。單筆失敗不阻斷其餘。
            logger.exception(
                "評審重跑:challenger 呼叫失敗 ai_evaluation_uid=%s rerun_model=%s",
                ai_evaluation_uid,
                ch.rerun_model,
            )
            await _safe_create_rerun(
                rerun_repo,
                RerunInput(
                    ai_evaluation_uid=ai_evaluation_uid,
                    usage_log_uid=parent.usage_log_uid,
                    original_model=original_model,
                    rerun_model=ch.rerun_model,
                    triggered_at=_now_tw(),
                    status="error",
                    ai_candidate_uid=ch.ai_candidate_uid,
                    model_uid=challenger_model_uid,
                    request_content=request_content or None,
                    original_cost_usd=original_cost,
                    error_code="challenger_failed",
                ),
                ai_evaluation_uid=ai_evaluation_uid,
            )
            continue

        cost_delta = (
            outcome.cost_usd - original_cost
            if outcome.cost_usd is not None and original_cost is not None
            else None
        )

        verdict: _Verdict | None = None
        if discriminator_enabled and ch.judge_model_key:
            swap = (
                blind_swap if blind_swap is not None else bool(random.getrandbits(1))
            )
            try:
                verdict = await _run_discriminator(
                    client,
                    request_content=request_content,
                    original_output=original_output,
                    challenger_output=outcome.output_text,
                    judge_model_key=ch.judge_model_key,
                    task_context=task_context,
                    api_key=api_key,
                    blind_swap=swap,
                )
            except Exception:  # noqa: BLE001
                # discriminator 失敗 → compare_* 留 NULL,仍寫客觀指標列(不阻斷)。
                logger.exception(
                    "評審重跑:discriminator 裁決失敗 ai_evaluation_uid=%s "
                    "rerun_model=%s judge=%s",
                    ai_evaluation_uid,
                    ch.rerun_model,
                    ch.judge_model_key,
                )

        await _safe_create_rerun(
            rerun_repo,
            RerunInput(
                ai_evaluation_uid=ai_evaluation_uid,
                usage_log_uid=parent.usage_log_uid,
                original_model=original_model,
                rerun_model=ch.rerun_model,
                triggered_at=_now_tw(),
                status="success",
                ai_candidate_uid=ch.ai_candidate_uid,
                model_uid=challenger_model_uid,
                request_content=request_content or None,
                response_summary=outcome.response_summary,
                prompt_tokens=outcome.prompt_tokens,
                completion_tokens=outcome.completion_tokens,
                total_tokens=outcome.total_tokens,
                cost_usd=outcome.cost_usd,
                original_cost_usd=original_cost,
                cost_delta_usd=cost_delta,
                latency_ms=outcome.latency_ms,
                openrouter_generation_id=outcome.openrouter_generation_id,
                compare_winner=verdict.compare_winner if verdict else None,
                compare_score=verdict.compare_score if verdict else None,
                compare_reason=verdict.compare_reason if verdict else None,
                compare_judge_model=verdict.compare_judge_model if verdict else None,
            ),
            ai_evaluation_uid=ai_evaluation_uid,
        )
        success_count += 1

    # 全 challenger 失敗 → status=0;≥1 成功 → status=1(終局,不重派)。
    final_status = 1 if success_count > 0 else 0
    await eval_repo.mark_reran(ai_evaluation_uid, status=final_status)
    logger.info(
        "評審重跑完成 ai_evaluation_uid=%s challenger=%d 成功=%d status=%d",
        ai_evaluation_uid,
        len(challengers),
        success_count,
        final_status,
    )


async def _safe_create_rerun(
    rerun_repo: AiModelEvalRerunRepository,
    data: RerunInput,
    *,
    ai_evaluation_uid: UUID,
) -> None:
    """落地單筆 rerun;寫入失敗只記 log、不阻斷其餘 challenger(維持「單筆失敗不連坐」)。"""
    try:
        await rerun_repo.create_rerun(data)
    except Exception:  # noqa: BLE001
        logger.exception(
            "評審重跑:rerun 落地失敗 ai_evaluation_uid=%s rerun_model=%s",
            ai_evaluation_uid,
            data.rerun_model,
        )


__all__ = ["rerun_evaluation"]
