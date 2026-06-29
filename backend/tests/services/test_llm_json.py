"""llm_json.extract_first_json_object 強健解析測試。

涵蓋 taskiq-worker 實際遇到的 LLM 髒污回覆:圍欄 / 夾帶散文 / 物件後額外資料
(`Extra data`)/ 第二個物件 / 尾逗號 / 散文誤含 `{` / 無法解析。
"""

from __future__ import annotations

import json

import pytest

from app.services.llm_json import extract_first_json_object


def test_plain_object() -> None:
    assert extract_first_json_object('{"a": 1, "b": "x"}') == {"a": 1, "b": "x"}


def test_json_fence() -> None:
    assert extract_first_json_object('```json\n{"a": 1}\n```') == {"a": 1}


def test_bare_fence() -> None:
    assert extract_first_json_object('```\n{"a": 1}\n```') == {"a": 1}


def test_surrounding_prose() -> None:
    assert extract_first_json_object("我的判斷如下:\n{\"a\": 1}\n以上。") == {"a": 1}


def test_extra_data_after_object() -> None:
    """回報案例:物件後追加說明文字(原 json.loads 會 `Extra data` 整段失敗)。"""
    content = '{"winner": "A", "reason": "r", "score": 0.5}\n額外說明:我覺得 A 比較好。'
    assert extract_first_json_object(content) == {
        "winner": "A",
        "reason": "r",
        "score": 0.5,
    }


def test_second_object_ignored() -> None:
    """物件後再追加第二個物件 → 只取第一個(raw_decode 忽略其後)。"""
    content = '{"a": 1}\n{"b": 2}'
    assert extract_first_json_object(content) == {"a": 1}


def test_prose_with_stray_brace_then_object() -> None:
    """散文誤含 `{`(無法解析)→ 跳到下一個 `{` 取真正的物件。"""
    content = "用法 {placeholder} 如下:{\"a\": 1}"
    assert extract_first_json_object(content) == {"a": 1}


def test_trailing_comma_repaired() -> None:
    """物件尾逗號(LLM 常見失誤)→ 修補後解析。"""
    assert extract_first_json_object('{"a": 1, "b": 2,}') == {"a": 1, "b": 2}


def test_nested_object_kept_whole() -> None:
    content = '{"output_fit": {"score": 0.78, "reason": "ok"}, "recommend": {"model": "m"}}'
    assert extract_first_json_object(content) == {
        "output_fit": {"score": 0.78, "reason": "ok"},
        "recommend": {"model": "m"},
    }


def test_no_json_raises() -> None:
    with pytest.raises(json.JSONDecodeError):
        extract_first_json_object("這裡完全沒有 JSON 物件")
