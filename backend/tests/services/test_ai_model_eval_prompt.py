"""ai_model_eval_prompt.py + ai_model_eval schema 單元測試(對齊 task-103 Acceptance)。

純函式 / 純 schema 測試,無 DB、無 I/O。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.ai_model_eval import JudgeOutput, TaskComplexity, TaskIntent
from app.services.ai_model_eval_prompt import build_judge_prompt

# --- 共用 fixtures ----------------------------------------------------------

_VALID_PAYLOAD = {
    "task_summary": "x",
    "task_intent": "code_generation",
    "task_complexity": "medium",
    "output_fit": {"score": 0.8, "reason": "r"},
    "recommend": {"model": "anthropic/claude-opus-4.8", "reason": "r"},
}

_REQUEST_CONTENT = {
    "model": "openai/gpt-4o-mini",
    "text": "幫我寫一個 quicksort 的 python 實作",
    "images": [],
    "tools": [],
}

_RESPONSE_SUMMARY = {
    "output_text": "def quicksort(arr): ...",
    "usage": {"prompt_tokens": 10, "completion_tokens": 20},
}

_CANDIDATES = [
    {"model_key": "anthropic/claude-opus-4.8", "tier": "premium"},
    {"model_key": "openai/gpt-4o", "tier": "standard"},
    {"model_key": "google/gemini-2.5-pro", "tier": "premium"},
]

# 使用者目前使用的模型(非盲測,明確揭露給裁判)。
_ORIGINAL_MODEL = "openai/gpt-4o-mini"


# --- schema:JudgeOutput -----------------------------------------------------


def test_judge_output_validates_example():
    """Acceptance:§6 範例 dict 應通過驗證。"""
    out = JudgeOutput.model_validate(_VALID_PAYLOAD)
    assert out.task_summary == "x"
    assert out.task_intent is TaskIntent.CODE_GENERATION
    assert out.task_complexity is TaskComplexity.MEDIUM
    assert out.output_fit.score == 0.8
    assert out.recommend.model == "anthropic/claude-opus-4.8"


@pytest.mark.parametrize("bad_score", [1.5, -0.1, 2.0])
def test_score_out_of_range_raises(bad_score: float):
    """Acceptance:score 超出 0–1 應 raise ValidationError。"""
    payload = {**_VALID_PAYLOAD, "output_fit": {"score": bad_score, "reason": "r"}}
    with pytest.raises(ValidationError):
        JudgeOutput.model_validate(payload)


def test_score_boundaries_ok():
    """邊界 0.0 / 1.0 應通過。"""
    for score in (0.0, 1.0):
        payload = {**_VALID_PAYLOAD, "output_fit": {"score": score, "reason": "r"}}
        assert JudgeOutput.model_validate(payload).output_fit.score == score


def test_unknown_intent_falls_back_to_other():
    """寬鬆解析:意圖不在枚舉 → 落 other。"""
    payload = {**_VALID_PAYLOAD, "task_intent": "brainstorming"}
    assert JudgeOutput.model_validate(payload).task_intent is TaskIntent.OTHER


def test_intent_case_insensitive():
    """寬鬆解析:大小寫 / 前後空白容忍。"""
    payload = {**_VALID_PAYLOAD, "task_intent": "  Summarization  "}
    assert JudgeOutput.model_validate(payload).task_intent is TaskIntent.SUMMARIZATION


def test_extra_fields_ignored():
    """寬鬆解析:模型多回欄位應被忽略,不報錯。"""
    payload = {**_VALID_PAYLOAD, "confidence": 0.99, "extra_note": "whatever"}
    out = JudgeOutput.model_validate(payload)
    assert out.task_summary == "x"


def test_bad_complexity_raises():
    """複雜度不在枚舉 → ValidationError(複雜度為固定枚舉,不寬鬆 fallback)。"""
    payload = {**_VALID_PAYLOAD, "task_complexity": "extreme"}
    with pytest.raises(ValidationError):
        JudgeOutput.model_validate(payload)


# --- service:build_judge_prompt --------------------------------------------


def test_prompt_contains_all_candidate_model_keys():
    """Acceptance:prompt 文字含全部傳入候選 model_key。"""
    payload = build_judge_prompt(_REQUEST_CONTENT, _RESPONSE_SUMMARY, _CANDIDATES, _ORIGINAL_MODEL)
    text = _flatten_messages(payload)
    for cand in _CANDIDATES:
        assert cand["model_key"] in text


def test_prompt_reveals_current_model():
    """非盲測:prompt 應明確揭露使用者目前使用的模型(面試式評選)。"""
    payload = build_judge_prompt(
        _REQUEST_CONTENT, _RESPONSE_SUMMARY, _CANDIDATES, _ORIGINAL_MODEL
    )
    text = _flatten_messages(payload)
    assert _ORIGINAL_MODEL in text


def test_prompt_includes_current_tier_when_given():
    """目前模型 tier 提供時應一併揭露(基礎資訊)。"""
    payload = build_judge_prompt(
        _REQUEST_CONTENT,
        _RESPONSE_SUMMARY,
        _CANDIDATES,
        _ORIGINAL_MODEL,
        original_tier="standard",
    )
    text = _flatten_messages(payload)
    assert "standard" in text


def test_prompt_allows_keeping_current_model():
    """recommend 規則應允許/鼓勵『維持目前模型』(避免一律建議更換)。"""
    payload = build_judge_prompt(
        _REQUEST_CONTENT, _RESPONSE_SUMMARY, _CANDIDATES, _ORIGINAL_MODEL
    )
    text = _flatten_messages(payload)
    assert "維持" in text


def test_prompt_includes_input_and_output_text():
    """prompt 應帶入使用者輸入原文與模型輸出原文。"""
    payload = build_judge_prompt(_REQUEST_CONTENT, _RESPONSE_SUMMARY, _CANDIDATES, _ORIGINAL_MODEL)
    text = _flatten_messages(payload)
    assert _REQUEST_CONTENT["text"] in text
    assert _RESPONSE_SUMMARY["output_text"] in text


def test_prompt_requests_json_output():
    """要求 JSON 結構化輸出。"""
    payload = build_judge_prompt(_REQUEST_CONTENT, _RESPONSE_SUMMARY, _CANDIDATES, _ORIGINAL_MODEL)
    assert payload["response_format"] == {"type": "json_object"}
    assert isinstance(payload["messages"], list)
    assert payload["messages"][0]["role"] == "system"


def test_prompt_pins_temperature_zero():
    """評分/分類任務:temperature=0,壓低取樣隨機性以提升可重現性。"""
    payload = build_judge_prompt(_REQUEST_CONTENT, _RESPONSE_SUMMARY, _CANDIDATES, _ORIGINAL_MODEL)
    assert payload["temperature"] == 0


def test_mask_hook_applied_to_input_text():
    """遮罩 hook 介面:傳入的 masker 應作用於使用者文字。"""

    def masker(_: str) -> str:
        return "[REDACTED]"

    payload = build_judge_prompt(
        _REQUEST_CONTENT,
        _RESPONSE_SUMMARY,
        _CANDIDATES,
        _ORIGINAL_MODEL,
        text_masker=masker,
    )
    text = _flatten_messages(payload)
    assert "[REDACTED]" in text
    assert _REQUEST_CONTENT["text"] not in text


def test_default_mask_hook_is_identity():
    """預設不遮罩:原文應原樣出現。"""
    payload = build_judge_prompt(_REQUEST_CONTENT, _RESPONSE_SUMMARY, _CANDIDATES, _ORIGINAL_MODEL)
    text = _flatten_messages(payload)
    assert _REQUEST_CONTENT["text"] in text


def test_prompt_handles_empty_candidates():
    """無候選不應炸,且仍揭露目前模型。"""
    payload = build_judge_prompt(
        _REQUEST_CONTENT, _RESPONSE_SUMMARY, [], _ORIGINAL_MODEL
    )
    text = _flatten_messages(payload)
    assert _ORIGINAL_MODEL in text


# --- helpers ----------------------------------------------------------------


def _flatten_messages(payload: dict[str, object]) -> str:
    """把 payload.messages 的所有 content 串成單一字串供斷言。"""
    messages = payload["messages"]
    assert isinstance(messages, list)
    parts: list[str] = []
    for msg in messages:
        assert isinstance(msg, dict)
        content = msg.get("content")
        if isinstance(content, str):
            parts.append(content)
    return "\n".join(parts)
