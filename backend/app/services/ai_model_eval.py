"""模型適配評審執行服務(task-105;對齊 docs/Tasks/v2.0/propose-v2.0.1.md §5)。

組裝**單筆** usage_log 的三評審流程,是 task-106 taskiq task 的純業務核心
(無排程依賴,可獨立測):

1. 讀 3 個判別模型設定(`ai_eval_judge_settings`)、該筆 `usage_logs`(原文 I/O + 原模型)、
   `models` active 白名單(供 dim4 推薦限定範圍 + 反查 tier)。
2. 用 task-103 `build_judge_prompt` 組 payload(payload 不含 model);對 3 個判別模型各
   內部呼叫一次 `chat_completion(payload + 該模型, api_key=DEFAULT_OPENROUTER_KEY)`
   —— 沿用 v1.9.1 內部呼叫模式:走 `DEFAULT_OPENROUTER_KEY`、不經 SDK proxy、
   **不寫 usage_logs**。
3. 以 task-103 `JudgeOutput` 寬鬆解析;**某評審失敗 → 該筆略過、不阻斷其他評審**;
   三方全失敗 → 父 `status='error'`(propose §5)。
4. 透過 task-104 `create_evaluation_with_candidates` 單一呼叫回寫:父表 + 三子表 +
   來源 log 游標(`ai_evaluated_at` + `ai_evaluated_status`)於**同一 transaction** 原子落地。

錯誤對外一律收斂為 `AppError`(通用訊息),完整例外 / 原始回覆只進結構化 log;
log 中**不**輸出 API key 等機密(對齊 `03-backend/05-exceptions-and-logging.md`)。

設計決議(2026-06-25,user 拍板):
- 父表 summary/intent/complexity 三評審不一致時 → 取**首個成功評審值**傳給 repository。
- 派發游標終局化:成敗皆寫 `ai_evaluated_at = now()`、`ai_evaluated_status`(1=成功 /
  0=失敗);失敗也算「跑過」,dispatcher 不重撈,後續由獨立失敗檢查機制處理(本版不做)。
- `raw_json` 本版**不存**(不傳給 repository)。
- PII:本版不遮罩(`build_judge_prompt` 用預設 text_masker)。
- dim4 `tier`:由所選 recommend model 反查 `models.tier_key`(prompt 不要求模型回 tier),
  保證一致;推薦不在白名單時該欄留 None。
- `ai_self_vote`:該判別模型推薦的模型是否與**判別模型自己**同廠商(自我偏好偏差
  監控),以 `model_key` 的廠商前綴(`provider/model` 的 `/` 前段)判定;任一側無法
  判定廠商前綴時留 None。注意比對對象是「裁判 vs 推薦」,非「原模型 vs 推薦」。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.openrouter.client import OpenRouterClient
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.models.ai_eval_judge_setting import AiEvalJudgeSetting
from app.models.model import Model
from app.models.usage_log import UsageLog
from app.repositories.ai_eval_judge_setting import AiEvalJudgeSettingRepository
from app.repositories.ai_model_evaluation import (
    AiModelEvaluationRepository,
    CandidateInput,
)
from app.repositories.model import ModelRepository
from app.repositories.usage_log import UsageLogRepository
from app.schemas.ai_model_eval import JudgeOutput
from app.services.ai_model_eval_prompt import build_judge_prompt

logger = get_logger(__name__)


@dataclass(frozen=True)
class _JudgeResult:
    """單一判別模型的評審結果(成功才帶 output;失敗時 output=None)。"""

    model_uid: UUID
    model_key: str
    output: JudgeOutput | None


def _is_free_model(model_key: str | None) -> bool:
    """是否為免費模型(OpenRouter 慣例:model_key 以 `:free` 結尾)。

    禁止 AI 推薦免費模型(user 拍板):免費模型受嚴格限流 / 隨時可能下架,不適合作為
    正式派工的推薦對象。據此於候選白名單過濾 + 推薦結果防呆雙重把關。
    """
    return bool(model_key) and model_key.strip().lower().endswith(":free")


def _vendor_prefix(model_key: str | None) -> str | None:
    """取 model_key 的廠商前綴(`provider/model` 的 `/` 前段);無法判定回 None。"""
    if not model_key or "/" not in model_key:
        return None
    prefix = model_key.split("/", 1)[0].strip().lower()
    return prefix or None


def _compute_self_vote(recommend_model: str | None, judge_model: str | None) -> bool | None:
    """推薦是否與判別模型自己同廠商(自我偏好偏差;以 model_key 廠商前綴判定);資訊不足回 None。"""
    rec = _vendor_prefix(recommend_model)
    judge = _vendor_prefix(judge_model)
    if rec is None or judge is None:
        return None
    return rec == judge


def _extract_content(resp: dict[str, Any]) -> str:
    """從 OpenRouter chat completion 回應取出 message content;形狀不符 raise。"""
    return resp["choices"][0]["message"]["content"]


def _parse_judge_content(content: str) -> JudgeOutput:
    """寬鬆解析判別模型回傳:容忍 ```json 圍欄與前後夾帶文字,再交 JudgeOutput 驗證。"""
    text = content.strip()
    if text.startswith("```"):
        text = text.removeprefix("```json").removeprefix("```").strip()
        text = text.removesuffix("```").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        data = json.loads(text[start : end + 1])
    return JudgeOutput.model_validate(data)


async def _run_one_judge(
    client: OpenRouterClient,
    *,
    base_payload: dict[str, Any],
    judge_model_key: str,
    judge_model_uid: UUID,
    api_key: str,
) -> _JudgeResult:
    """對單一判別模型送一次 chat_completion 並解析;失敗(呼叫/解析)→ output=None,不拋。"""
    payload = {**base_payload, "model": judge_model_key}
    try:
        resp = await client.chat_completion(payload, api_key=api_key)
        content = _extract_content(resp)
    except Exception:  # noqa: BLE001
        # 完整例外(上游狀態碼 / 原始 body)只進日誌;不含 api_key。
        logger.exception(
            "模型適配評審:判別模型呼叫失敗 judge_model=%s", judge_model_key
        )
        return _JudgeResult(judge_model_uid, judge_model_key, None)

    try:
        output = _parse_judge_content(content)
    except Exception:  # noqa: BLE001
        logger.exception(
            "模型適配評審:判別模型回覆解析失敗 judge_model=%s, 原始內容=%r",
            judge_model_key,
            content,
        )
        return _JudgeResult(judge_model_uid, judge_model_key, None)

    return _JudgeResult(judge_model_uid, judge_model_key, output)


def _build_candidate(
    result: _JudgeResult,
    *,
    tier_by_model_key: dict[str, str | None],
) -> CandidateInput:
    """把單一評審結果轉成子表輸入;失敗評審 → 各 AI 欄位留 None(標記該子列未取得判斷)。"""
    if result.output is None:
        return CandidateInput(model_uid=result.model_uid)

    out = result.output
    recommend_model = out.recommend.model or None
    recommend_reason = out.recommend.reason or None
    # 防呆:即便候選白名單已濾掉 free,模型仍可能幻覺推薦免費模型 → 一律作廢該推薦
    # (視為無推薦,不得推薦 free;見 _is_free_model)。
    if _is_free_model(recommend_model):
        logger.warning(
            "模型適配評審:判別模型推薦了免費模型,已作廢該推薦 judge=%s recommend=%s",
            result.model_key,
            recommend_model,
        )
        recommend_model = None
        recommend_reason = None
    # dim4 tier 由所選 recommend model 反查 models 白名單;不在白名單則留 None。
    recommend_tier = (
        tier_by_model_key.get(recommend_model) if recommend_model is not None else None
    )
    return CandidateInput(
        model_uid=result.model_uid,
        ai_recommend_model=recommend_model,
        ai_recommend_tier=recommend_tier,
        ai_recommend_reason=recommend_reason,
        ai_fit_score=Decimal(str(out.output_fit.score)),
        # 自我偏好偏差:推薦是否與「該裁判自己」(result.model_key)同廠商,非原模型。
        ai_self_vote=_compute_self_vote(recommend_model, result.model_key),
    )


def _first_successful(results: list[_JudgeResult]) -> JudgeOutput | None:
    """取首個成功評審的 JudgeOutput(父表 dim1/2 不一致時的拍板來源);全失敗回 None。"""
    for r in results:
        if r.output is not None:
            return r.output
    return None


async def evaluate_usage_log(
    usage_log_uid: UUID,
    *,
    db: AsyncSession,
    client: OpenRouterClient,
) -> None:
    """評審單筆 usage_log:三判別模型 → 解析 → 回寫父+子表並標旗標。

    冪等由 repository 以 `usage_log_uid` UNIQUE 保證(已存在則 no-op 回既有父列)。

    Args:
        usage_log_uid: 待評審的 usage_logs.usage_log_uid。
        db: AsyncSession(由 caller / task-106 提供)。
        client: OpenRouterClient(內部呼叫,走 DEFAULT_OPENROUTER_KEY)。

    Raises:
        AppError: 前置條件不足(無判別模型設定 / log 不存在 / 未設金鑰)或回寫失敗時,
            對外收斂為通用訊息;細節走 log。
    """
    settings = get_settings()
    api_key = settings.DEFAULT_OPENROUTER_KEY
    if not api_key:
        logger.error("模型適配評審略過:未設定內部呼叫金鑰 usage_log_uid=%s", usage_log_uid)
        raise AppError("模型適配評審暫時無法執行", code=503)

    judge_repo = AiEvalJudgeSettingRepository(db)
    usage_repo = UsageLogRepository(db)
    model_repo = ModelRepository(db)
    eval_repo = AiModelEvaluationRepository(db)

    judges: list[AiEvalJudgeSetting] = await judge_repo.list_active()
    if not judges:
        logger.error("模型適配評審略過:無有效判別模型設定 usage_log_uid=%s", usage_log_uid)
        raise AppError("尚未設定判別模型,無法執行模型適配評審", code=409)

    usage_log: UsageLog | None = await usage_repo.get_by_uid(usage_log_uid)
    if usage_log is None:
        logger.error("模型適配評審略過:來源 usage_log 不存在 usage_log_uid=%s", usage_log_uid)
        raise AppError("找不到對應的用量紀錄", code=404)

    active_models: list[Model] = await model_repo.list_active()
    # tier 反查表保留全部 active(供原模型 tier 顯示);候選推薦白名單則濾掉免費模型
    # (禁止 AI 推薦 free,見 _is_free_model)。
    tier_by_model_key: dict[str, str | None] = {m.model_key: m.tier_key for m in active_models}
    candidate_models = [
        {"model_key": m.model_key, "tier": m.tier_key}
        for m in active_models
        if not _is_free_model(m.model_key)
    ]

    # 取得各判別模型的 model_key(用於送出 payload 的 model 欄)。
    judge_model_uids = [j.model_uid for j in judges]
    judge_models = await judge_repo.list_active_models_by_uids(judge_model_uids)
    judge_key_by_uid = {m.model_uid: m.model_key for m in judge_models}

    request_content = usage_log.request_content or {}
    response_summary = usage_log.response_summary or {}
    original_model = usage_log.model

    base_payload = build_judge_prompt(
        request_content,
        response_summary,
        candidate_models,
        original_model,
        original_tier=tier_by_model_key.get(original_model),
    )

    results: list[_JudgeResult] = []
    for judge in judges:
        judge_model_key = judge_key_by_uid.get(judge.model_uid)
        if judge_model_key is None:
            # 判別模型已被停用 / 軟刪 → 視為該評審失敗,不阻斷其他評審。
            logger.warning(
                "模型適配評審:判別模型已非 active,跳過 model_uid=%s usage_log_uid=%s",
                judge.model_uid,
                usage_log_uid,
            )
            results.append(_JudgeResult(judge.model_uid, "", None))
            continue
        results.append(
            await _run_one_judge(
                client,
                base_payload=base_payload,
                judge_model_key=judge_model_key,
                judge_model_uid=judge.model_uid,
                api_key=api_key,
            )
        )

    success_count = sum(1 for r in results if r.output is not None)
    parent_output = _first_successful(results)
    all_failed = success_count == 0

    candidates = [
        _build_candidate(r, tier_by_model_key=tier_by_model_key)
        for r in results
    ]

    # ≥1 評審成功(含 partial)→ status='evaluated' + ai_evaluated_status=1;
    # 三評審全失敗 → status='error' + ai_evaluated_status=0。兩者 ai_evaluated_at 皆標:
    # 失敗為終局(由獨立失敗檢查機制處理),dispatcher 不重撈。父+子+游標由 repository
    # 於單一 transaction 原子落地;成敗皆「跑過」、不保留 NULL 重派。
    try:
        await eval_repo.create_evaluation_with_candidates(
            usage_log_uid=usage_log_uid,
            ai_original_model=original_model,
            candidates=candidates,
            department_uid=usage_log.department_uid,
            user_uid=usage_log.user_uid,
            ai_task_summary=(
                parent_output.task_summary if parent_output is not None else None
            ),
            ai_task_intent=(
                parent_output.task_intent.value if parent_output is not None else None
            ),
            ai_task_complexity=(
                parent_output.task_complexity.value
                if parent_output is not None
                else None
            ),
            evaluation_succeeded=not all_failed,
            mark_evaluated=True,
        )
    except AppError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "模型適配評審回寫失敗 usage_log_uid=%s", usage_log_uid
        )
        raise AppError("模型適配評審回寫失敗", code=500) from exc

    logger.info(
        "模型適配評審完成 usage_log_uid=%s status=%s 成功評審=%d/%d",
        usage_log_uid,
        "error" if all_failed else "evaluated",
        success_count,
        len(results),
    )
