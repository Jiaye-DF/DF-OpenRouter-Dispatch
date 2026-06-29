"""禁止 AI 推薦 / 重跑免費模型(`:free`)的純函式單元測試(user 拍板)。

不連 DB / OpenRouter:只驗證評審推薦過濾(`_build_candidate`)與重跑 challenger 過濾
(`_build_challengers`)兩道把關,以及共用的 `_is_free_model` 判定。
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from uuid_utils import uuid7

import app.services.ai_model_eval as eval_svc
import app.services.ai_model_eval_rerun as rerun_svc
from app.repositories.ai_model_evaluation import CandidateWithJudge
from app.schemas.ai_model_eval import JudgeOutput


def _new_uid() -> UUID:
    return UUID(str(uuid7()))


# ---------------------------------------------------------------------------
# _is_free_model:`:free` 結尾才算免費(兩 service 行為一致)
# ---------------------------------------------------------------------------


def test_is_free_model_detects_free_suffix() -> None:
    for fn in (eval_svc._is_free_model, rerun_svc._is_free_model):
        assert fn("google/gemini-2.0-flash-exp:free") is True
        assert fn("DEEPSEEK/DeepSeek-R1:FREE") is True  # 大小寫不敏感
        assert fn("openai/gpt-4o") is False
        assert fn("vendor/model-free") is False  # 僅 `-free` 不算(須 `:free`)
        assert fn(None) is False
        assert fn("") is False


# ---------------------------------------------------------------------------
# 評審推薦:幻覺推薦免費模型 → 作廢(model / reason 皆 None)
# ---------------------------------------------------------------------------


def _judge_result(recommend_model: str, *, reason: str = "理由") -> eval_svc._JudgeResult:
    output = JudgeOutput.model_validate(
        {
            "task_summary": "做某事",
            "task_intent": "qa",
            "task_complexity": "medium",
            "output_fit": {"score": 0.8, "reason": "尚可"},
            "recommend": {"model": recommend_model, "reason": reason},
        }
    )
    return eval_svc._JudgeResult(_new_uid(), "judge/model", output)


def test_build_candidate_voids_free_recommendation() -> None:
    cand = eval_svc._build_candidate(
        _judge_result("vendor/cheap:free"),
        tier_by_model_key={"vendor/cheap:free": "low"},
    )
    assert cand.ai_recommend_model is None
    assert cand.ai_recommend_reason is None
    assert cand.ai_recommend_tier is None


def test_build_candidate_keeps_paid_recommendation() -> None:
    cand = eval_svc._build_candidate(
        _judge_result("openai/gpt-4o"),
        tier_by_model_key={"openai/gpt-4o": "high"},
    )
    assert cand.ai_recommend_model == "openai/gpt-4o"
    assert cand.ai_recommend_reason == "理由"
    assert cand.ai_recommend_tier == "high"


# ---------------------------------------------------------------------------
# 重跑 challenger:免費推薦不進重跑 / 判決
# ---------------------------------------------------------------------------


def _cand_with_judge(recommend_model: str | None) -> CandidateWithJudge:
    return CandidateWithJudge(
        ai_candidate_uid=_new_uid(),
        model_uid=_new_uid(),
        ai_recommend_model=recommend_model,
        ai_recommend_tier=None,
        ai_recommend_reason=None,
        ai_fit_score=Decimal("0.8"),
        ai_self_vote=None,
        judge_model_key="judge/model",
        judge_model_name=None,
    )


def test_build_challengers_skips_free_models() -> None:
    candidates = [
        _cand_with_judge("vendor/free-pick:free"),
        _cand_with_judge("openai/gpt-4o"),
    ]
    challengers = rerun_svc._build_challengers(candidates, original_model="orig/model")
    models = [c.rerun_model for c in challengers]
    assert models == ["openai/gpt-4o"]


def test_build_challengers_all_free_yields_empty() -> None:
    candidates = [
        _cand_with_judge("a/x:free"),
        _cand_with_judge("b/y:free"),
    ]
    challengers = rerun_svc._build_challengers(candidates, original_model="orig/model")
    assert challengers == []
