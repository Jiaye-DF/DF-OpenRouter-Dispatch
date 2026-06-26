"""ai_model_eval_rerun_prompt.py + DiscriminatorOutput schema 單元測試(task-404 Acceptance)。

純函式 / 純 schema 測試,無 DB、無 I/O。涵蓋 Acceptance (a)(b)(c)(d)。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.ai_model_eval import DiscriminatorOutput, DiscriminatorWinner
from app.services.ai_model_eval_rerun_prompt import (
    _parse_discriminator_content,
    build_discriminator_prompt,
)

# --- 共用 fixtures ----------------------------------------------------------

_REQUEST_CONTENT = {
    "model": "openai/gpt-4o-mini",
    "text": "幫我寫一個 quicksort 的 python 實作",
    "images": [],
    "tools": [],
}

_OUTPUT_A = "def quicksort(arr): return arr  # 由 anthropic/claude 產生(實際不應外洩)"
_OUTPUT_B = "def quicksort(arr): ...  # 由 openai/gpt-4o 產生(實際不應外洩)"

# 盲化斷言:payload 文字不得出現任一模型 key。
_MODEL_KEYS = [
    "openai/gpt-4o-mini",
    "anthropic/claude-opus-4.8",
    "openai/gpt-4o",
    "google/gemini-2.5-pro",
]


# --- (a) temperature / response_format --------------------------------------


def test_payload_pins_temperature_zero_and_json_object():
    """Acceptance (a):payload temperature==0 且 response_format.type=='json_object'。"""
    payload = build_discriminator_prompt(_REQUEST_CONTENT, _OUTPUT_A, _OUTPUT_B)
    assert payload["temperature"] == 0
    assert payload["response_format"] == {"type": "json_object"}
    messages = payload["messages"]
    assert isinstance(messages, list)
    assert messages[0]["role"] == "system"


# --- (b) 盲化:payload 文字不含任一模型 key ---------------------------------


def test_payload_is_blinded_no_model_keys():
    """Acceptance (b):盲化 — payload 文字不得出現任一模型名/key。"""
    # request_content.model 與 output 內夾帶的模型名都不應外洩到 payload(model 欄略過;
    # output 文字由 caller 負責不含模型名,此處驗 request 端盲化 + 只有 A/B 標籤)。
    blinded_a = "def quicksort(arr): return arr"
    blinded_b = "def quicksort(arr): ..."
    payload = build_discriminator_prompt(_REQUEST_CONTENT, blinded_a, blinded_b)
    text = _flatten_messages(payload)
    for key in _MODEL_KEYS:
        assert key not in text
    # 只用「輸出 A / 輸出 B」標籤盲化呈現。
    assert "輸出 A" in text
    assert "輸出 B" in text


def test_payload_omits_request_content_model_field():
    """request_content.model 欄不得帶入 payload(盲化)。"""
    payload = build_discriminator_prompt(_REQUEST_CONTENT, "a", "b")
    text = _flatten_messages(payload)
    assert _REQUEST_CONTENT["model"] not in text


def test_payload_includes_input_and_both_outputs():
    """payload 應帶入使用者輸入原文與兩側輸出原文。"""
    payload = build_discriminator_prompt(_REQUEST_CONTENT, "OUTPUT_AAA", "OUTPUT_BBB")
    text = _flatten_messages(payload)
    assert _REQUEST_CONTENT["text"] in text
    assert "OUTPUT_AAA" in text
    assert "OUTPUT_BBB" in text


def test_task_context_included_when_given():
    """task_context 提供時應併入 payload。"""
    payload = build_discriminator_prompt(
        _REQUEST_CONTENT, "a", "b", task_context="任務:程式碼生成"
    )
    text = _flatten_messages(payload)
    assert "任務:程式碼生成" in text


# --- mask hook(決議 #5 保留 hook) -----------------------------------------


def test_mask_hook_applied_to_input_text():
    """遮罩 hook 介面:傳入的 masker 應作用於使用者文字。"""

    def masker(_: str) -> str:
        return "[REDACTED]"

    payload = build_discriminator_prompt(
        _REQUEST_CONTENT, "a", "b", text_masker=masker
    )
    text = _flatten_messages(payload)
    assert "[REDACTED]" in text
    assert _REQUEST_CONTENT["text"] not in text


def test_default_mask_hook_is_identity():
    """預設不遮罩:原文應原樣出現。"""
    payload = build_discriminator_prompt(_REQUEST_CONTENT, "a", "b")
    text = _flatten_messages(payload)
    assert _REQUEST_CONTENT["text"] in text


# --- (c) 寬鬆解析:圍欄 + 夾帶文字 ------------------------------------------


def test_parse_plain_json():
    """純 JSON 應正常解析。"""
    out = _parse_discriminator_content('{"winner": "A", "reason": "r", "score": 0.5}')
    assert out.winner is DiscriminatorWinner.A
    assert out.score == 0.5


def test_parse_with_json_fence():
    """Acceptance (c):容忍 ```json 圍欄。"""
    content = '```json\n{"winner": "B", "reason": "r", "score": 0.9}\n```'
    out = _parse_discriminator_content(content)
    assert out.winner is DiscriminatorWinner.B
    assert out.score == 0.9


def test_parse_with_surrounding_text():
    """Acceptance (c):容忍 JSON 前後夾帶說明文字。"""
    content = '我的判斷如下:\n{"winner": "A", "reason": "r", "score": 0.3}\n以上。'
    out = _parse_discriminator_content(content)
    assert out.winner is DiscriminatorWinner.A
    assert out.score == 0.3


def test_parse_with_fence_and_surrounding_text():
    """圍欄 + 夾帶文字同時出現。"""
    content = 'here:\n```json\n{"winner": "B", "reason": "x", "score": 0.6}\n```\ndone'
    out = _parse_discriminator_content(content)
    assert out.winner is DiscriminatorWinner.B


# --- (d) winner 非 A/B → 驗證失敗 ------------------------------------------


@pytest.mark.parametrize("bad_winner", ["C", "X", "winner", "", "AB"])
def test_invalid_winner_raises(bad_winner: str):
    """Acceptance (d):winner 非 A/B 應 raise ValidationError。"""
    with pytest.raises(ValidationError):
        DiscriminatorOutput.model_validate(
            {"winner": bad_winner, "reason": "r", "score": 0.5}
        )


def test_winner_case_and_whitespace_normalized():
    """寬鬆正規化:' a ' → A;'b' → B。"""
    assert (
        DiscriminatorOutput.model_validate(
            {"winner": " a ", "reason": "r", "score": 0.1}
        ).winner
        is DiscriminatorWinner.A
    )
    assert (
        DiscriminatorOutput.model_validate(
            {"winner": "b", "reason": "r", "score": 0.1}
        ).winner
        is DiscriminatorWinner.B
    )


# --- score 範圍與寬鬆欄位 ---------------------------------------------------


@pytest.mark.parametrize("bad_score", [1.5, -0.1, 2.0])
def test_score_out_of_range_raises(bad_score: float):
    """score 超出 0–1 應 raise ValidationError。"""
    with pytest.raises(ValidationError):
        DiscriminatorOutput.model_validate(
            {"winner": "A", "reason": "r", "score": bad_score}
        )


def test_score_boundaries_ok():
    """邊界 0.0 / 1.0 應通過。"""
    for score in (0.0, 1.0):
        out = DiscriminatorOutput.model_validate(
            {"winner": "A", "reason": "r", "score": score}
        )
        assert out.score == score


def test_extra_fields_ignored():
    """寬鬆解析:模型多回欄位應被忽略,不報錯。"""
    out = DiscriminatorOutput.model_validate(
        {"winner": "A", "reason": "r", "score": 0.5, "confidence": 0.99, "note": "x"}
    )
    assert out.winner is DiscriminatorWinner.A


def test_reason_defaults_empty():
    """reason 可缺(預設空字串)。"""
    out = DiscriminatorOutput.model_validate({"winner": "B", "score": 0.5})
    assert out.reason == ""


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
