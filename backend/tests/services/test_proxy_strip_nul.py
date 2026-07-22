"""proxy `_strip_nul` 寫入前 NUL 清理測試(修 usage_log JSONB 寫入 UntranslatableCharacterError)。

背景:Postgres text/jsonb 無法儲存 NUL(`\\u0000`);帶 NUL 的 request_content /
response_summary(多為文件/OCR 抽取殘留混入使用者輸入)會令整筆 usage_log 靜默寫入
失敗。寫入前一律遞迴 strip,涵蓋 dict / list / 巢狀與兩種請求快照形狀。
"""

from __future__ import annotations

from app.services.proxy import _strip_nul


def test_strip_nul_from_string() -> None:
    assert _strip_nul("ab\x00cd") == "abcd"


def test_no_nul_returns_equivalent() -> None:
    assert _strip_nul("正常文字") == "正常文字"


def test_strip_nul_recursive_nested() -> None:
    value = {
        "model": "openai/gpt-4o-mini",
        "text": "前\x00後",
        "images": ["data:image/png;base64,AA\x00AA"],
        "messages": [
            {"role": "user", "content": "hello\x00world"},
            {"role": "assistant", "content": [{"type": "text", "text": "x\x00y"}]},
        ],
    }
    cleaned = _strip_nul(value)
    assert cleaned["text"] == "前後"
    assert cleaned["images"] == ["data:image/png;base64,AAAA"]
    assert cleaned["messages"][0]["content"] == "helloworld"
    assert cleaned["messages"][1]["content"][0]["text"] == "xy"


def test_strip_nul_in_dict_keys() -> None:
    assert _strip_nul({"k\x00ey": "v"}) == {"key": "v"}


def test_non_str_scalars_passthrough() -> None:
    value = {"a": 1, "b": 2.5, "c": True, "d": None}
    assert _strip_nul(value) == value
