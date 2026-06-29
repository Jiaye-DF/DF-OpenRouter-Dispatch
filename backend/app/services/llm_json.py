"""LLM 回覆 JSON 強健萃取(評審 / 對比裁決共用)。

純函式、無 I/O:從判別 / 裁決模型回傳的「不乾淨」文字中,穩健取出第一個 JSON 物件。
背景:即便 prompt 要求只回 JSON、且帶 `response_format=json_object`,部分 provider
(經 OpenRouter)仍會夾帶說明文字、圍欄、或在物件後追加內容(`Extra data`),導致
單純 `json.loads` 整段失敗。本模組以 `JSONDecoder.raw_decode` 解析「第一個完整物件、
忽略其後內容」,並對常見 LLM 失誤(尾逗號)做輕量修補。

容忍以下髒污:
- ```json 圍欄 / 純 ``` 圍欄。
- JSON 前後夾帶散文(「我的判斷如下:{...}以上。」)。
- 物件後追加內容(`Extra data`:`{...}\n額外說明` 或第二個物件)。
- 散文中誤含 `{`(逐個 `{` 起點嘗試,取第一個能解析成物件者)。
- 物件 / 陣列尾逗號(`{"a":1,}` → 修補後再試)。

**不**嘗試修復字串內未轉義引號等結構性錯誤(無法通用且易誤判);此類仍上拋
`JSONDecodeError`,由呼叫端收斂為「該評審 / 裁決失敗」(不阻斷其他)。
"""

from __future__ import annotations

import json
import re
from typing import Any

# 物件 / 陣列收尾前的尾逗號(LLM 常見失誤):`,}` / `, ]` → 去逗號。
_TRAILING_COMMA = re.compile(r",(\s*[}\]])")


def _strip_code_fence(text: str) -> str:
    """去除外層 ```json / ``` 圍欄(僅當整段以圍欄開頭時)。"""
    if not text.startswith("```"):
        return text
    text = text.removeprefix("```json").removeprefix("```").strip()
    return text.removesuffix("```").strip()


def _first_object_via_raw_decode(text: str, decoder: json.JSONDecoder) -> dict[str, Any] | None:
    """逐個 `{` 起點 `raw_decode`,回第一個能解析成 dict 的物件;全失敗回 None。

    `raw_decode` 只解析從該位置起的第一個完整 JSON 值、**忽略其後內容**,故能吞掉
    物件後追加的散文 / 第二個物件(`Extra data`)。逐個 `{` 起點則容忍散文誤含 `{`。
    """
    idx = text.find("{")
    while idx != -1:
        try:
            obj, _ = decoder.raw_decode(text, idx)
        except json.JSONDecodeError:
            idx = text.find("{", idx + 1)
            continue
        if isinstance(obj, dict):
            return obj
        idx = text.find("{", idx + 1)
    return None


def extract_first_json_object(content: str) -> dict[str, Any]:
    """從 LLM 回覆文字穩健取出第一個 JSON 物件(dict);無法解析則上拋 `JSONDecodeError`。

    Args:
        content: 判別 / 裁決模型的原始回覆文字(可能含圍欄 / 夾帶散文 / 額外資料)。

    Returns:
        解析出的 JSON 物件(`dict`)。

    Raises:
        json.JSONDecodeError: 文字中找不到可解析的 JSON 物件(含輕量修補後仍失敗)。
    """
    text = _strip_code_fence(content.strip())
    decoder = json.JSONDecoder()

    obj = _first_object_via_raw_decode(text, decoder)
    if obj is not None:
        return obj

    # 最後一搏:移除尾逗號後再試(常見 LLM 失誤,如 `{"a":1,}` / `[1,2,]`)。
    repaired = _TRAILING_COMMA.sub(r"\1", text)
    if repaired != text:
        obj = _first_object_via_raw_decode(repaired, decoder)
        if obj is not None:
            return obj

    raise json.JSONDecodeError("找不到可解析的 JSON 物件", text, 0)


__all__ = ["extract_first_json_object"]
