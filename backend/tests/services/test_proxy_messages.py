"""proxy service messages 透傳 + 生成參數注入測試(v2.1.2, task-432)。

涵蓋:`_rewrite_request` messages 分支透傳形狀(str / parts content、順序保留)、
單輪舊路徑 payload 與 v2.1.1 位元級一致(回歸)、tools 兩模式附掛、
生成參數注入(有帶才出現 / None 不出現 / response_format 兩種 type 展開)、
`_build_request_log` 快照策略(messages 原樣、file part 僅記 filename、
image_url 原樣、生成參數入快照、used_tools 推導不受影響),以及
run_chat 對 internal / openrouter 兩 provider 傳遞相同 payload。
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest

from app.schemas.model import ChatMessage, ResponseFormat
from app.services import proxy
from app.services.proxy import _build_request_log, _rewrite_request

MODEL = "openai/gpt-4o-mini"
IMAGE_URL = "data:image/png;base64,AAAA"
FILE_DATA = "data:application/pdf;base64,BBBB"


def _messages(raw: list[dict[str, object]]) -> list[ChatMessage]:
    return [ChatMessage.model_validate(m) for m in raw]


def _multi_turn() -> list[ChatMessage]:
    return _messages(
        [
            {"role": "system", "content": "你是客服助理"},
            {"role": "user", "content": "上次說到哪?"},
            {"role": "assistant", "content": "說到出貨進度。"},
            {"role": "user", "content": "繼續。"},
        ]
    )


def _parts_message() -> list[ChatMessage]:
    return _messages(
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "看一下這張圖與檔案"},
                    {"type": "image_url", "image_url": {"url": IMAGE_URL}},
                    {"type": "file", "file": {"filename": "report.pdf", "file_data": FILE_DATA}},
                ],
            }
        ]
    )


# ---------------------------------------------------------------------------
# _rewrite_request:messages 分支透傳形狀
# ---------------------------------------------------------------------------


def test_rewrite_messages_str_content_passthrough() -> None:
    payload = _rewrite_request(MODEL, None, None, messages=_multi_turn())
    assert payload == {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "你是客服助理"},
            {"role": "user", "content": "上次說到哪?"},
            {"role": "assistant", "content": "說到出貨進度。"},
            {"role": "user", "content": "繼續。"},
        ],
    }


def test_rewrite_messages_parts_content_passthrough() -> None:
    """parts content 原樣透傳(不重組),file part 含 file_data 完整送下游。"""
    payload = _rewrite_request(MODEL, None, None, messages=_parts_message())
    assert payload == {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "看一下這張圖與檔案"},
                    {"type": "image_url", "image_url": {"url": IMAGE_URL}},
                    {"type": "file", "file": {"filename": "report.pdf", "file_data": FILE_DATA}},
                ],
            }
        ],
    }


# ---------------------------------------------------------------------------
# _rewrite_request:單輪舊路徑回歸(與 v2.1.1 位元級一致)
# ---------------------------------------------------------------------------


def test_rewrite_single_turn_full_fields_unchanged() -> None:
    """單輪 text+images+files+tools 的 payload 與 v2.1.1 形狀 / 鍵序位元級一致。"""
    tools = [{"type": "openrouter:web_search"}]
    files = [{"filename": "report.pdf", "file_data": FILE_DATA}]
    payload = _rewrite_request(MODEL, "hello", [IMAGE_URL], tools, files)
    expected = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "hello"},
                    {"type": "image_url", "image_url": {"url": IMAGE_URL}},
                    {"type": "file", "file": {"filename": "report.pdf", "file_data": FILE_DATA}},
                ],
            }
        ],
        "tools": tools,
    }
    assert json.dumps(payload, ensure_ascii=False) == json.dumps(expected, ensure_ascii=False)


def test_rewrite_single_turn_empty_content_fallback_unchanged() -> None:
    """全空輸入仍補空白 text block(v2.1.1 行為不變)。"""
    payload = _rewrite_request(MODEL, None, None)
    assert payload == {
        "model": MODEL,
        "messages": [{"role": "user", "content": [{"type": "text", "text": ""}]}],
    }


def test_rewrite_single_turn_with_none_generation_params_byte_identical() -> None:
    """帶 temperature=None 等三欄 None 的 payload 必須與完全不帶位元級一致。"""
    without = _rewrite_request(MODEL, "hi", [IMAGE_URL])
    with_none = _rewrite_request(
        MODEL, "hi", [IMAGE_URL], temperature=None, max_tokens=None, response_format=None
    )
    assert json.dumps(with_none, ensure_ascii=False) == json.dumps(without, ensure_ascii=False)


# ---------------------------------------------------------------------------
# _rewrite_request:tools 兩模式附掛
# ---------------------------------------------------------------------------


def test_rewrite_tools_attached_in_messages_mode() -> None:
    tools = [{"type": "openrouter:web_search"}]
    payload = _rewrite_request(MODEL, None, None, tools, messages=_multi_turn())
    assert payload["tools"] == tools


def test_rewrite_tools_attached_in_single_turn_mode() -> None:
    tools = [{"type": "openrouter:web_search"}]
    payload = _rewrite_request(MODEL, "hi", None, tools)
    assert payload["tools"] == tools


def test_rewrite_no_tools_key_when_absent() -> None:
    assert "tools" not in _rewrite_request(MODEL, "hi", None)
    assert "tools" not in _rewrite_request(MODEL, None, None, messages=_multi_turn())


# ---------------------------------------------------------------------------
# _rewrite_request:生成參數注入(兩模式共用)
# ---------------------------------------------------------------------------


def test_generation_params_injected_in_single_turn_mode() -> None:
    payload = _rewrite_request(
        MODEL,
        "hi",
        None,
        temperature=0.7,
        max_tokens=256,
        response_format=ResponseFormat.model_validate({"type": "json_object"}),
    )
    assert payload["temperature"] == 0.7
    assert payload["max_tokens"] == 256
    assert payload["response_format"] == {"type": "json_object"}


def test_generation_params_injected_in_messages_mode() -> None:
    schema = {"name": "answer", "strict": True, "schema": {"type": "object"}}
    payload = _rewrite_request(
        MODEL,
        None,
        None,
        messages=_multi_turn(),
        temperature=0,
        max_tokens=1,
        response_format=ResponseFormat.model_validate(
            {"type": "json_schema", "json_schema": schema}
        ),
    )
    assert payload["temperature"] == 0
    assert payload["max_tokens"] == 1
    assert payload["response_format"] == {"type": "json_schema", "json_schema": schema}


def test_generation_params_absent_when_none() -> None:
    """三欄 None 一律不出現在 payload(兩模式)。"""
    for payload in (
        _rewrite_request(MODEL, "hi", None),
        _rewrite_request(MODEL, None, None, messages=_multi_turn()),
    ):
        assert "temperature" not in payload
        assert "max_tokens" not in payload
        assert "response_format" not in payload


def test_generation_params_partial_injection() -> None:
    """只帶部分生成參數:有帶的出現、沒帶的不出現。"""
    payload = _rewrite_request(MODEL, "hi", None, max_tokens=100)
    assert payload["max_tokens"] == 100
    assert "temperature" not in payload
    assert "response_format" not in payload


def test_response_format_json_object_never_carries_json_schema_key() -> None:
    """json_object 展開後不得夾帶 json_schema: None(exclude_none)。"""
    payload = _rewrite_request(
        MODEL, "hi", None, response_format=ResponseFormat.model_validate({"type": "json_object"})
    )
    assert payload["response_format"] == {"type": "json_object"}
    assert "json_schema" not in payload["response_format"]


# ---------------------------------------------------------------------------
# _build_request_log:快照策略
# ---------------------------------------------------------------------------


def test_request_log_single_turn_unchanged() -> None:
    """單輪快照結構與 v2.1.1 一致(含鍵序;file 僅記檔名)。"""
    tools = [{"type": "openrouter:web_search"}]
    files = [{"filename": "report.pdf", "file_data": FILE_DATA}]
    log = _build_request_log(MODEL, "hello", [IMAGE_URL], tools, files)
    expected = {
        "model": MODEL,
        "text": "hello",
        "images": [IMAGE_URL],
        "tools": tools,
        "files": ["report.pdf"],
    }
    assert json.dumps(log, ensure_ascii=False) == json.dumps(expected, ensure_ascii=False)


def test_request_log_messages_snapshot_shape() -> None:
    """messages 模式:{model, messages} 快照;str content 原樣。"""
    log = _build_request_log(MODEL, None, None, messages=_multi_turn())
    assert log == {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "你是客服助理"},
            {"role": "user", "content": "上次說到哪?"},
            {"role": "assistant", "content": "說到出貨進度。"},
            {"role": "user", "content": "繼續。"},
        ],
    }
    assert "text" not in log
    assert "images" not in log


def test_request_log_messages_file_part_filename_only() -> None:
    """file part 僅記 filename 不記 file_data;image_url part 原樣保留。"""
    log = _build_request_log(MODEL, None, None, messages=_parts_message())
    content = log["messages"][0]["content"]
    assert content == [
        {"type": "text", "text": "看一下這張圖與檔案"},
        {"type": "image_url", "image_url": {"url": IMAGE_URL}},
        {"type": "file", "file": {"filename": "report.pdf"}},
    ]
    assert "file_data" not in json.dumps(log)


def test_request_log_snapshot_does_not_affect_payload_file_data() -> None:
    """快照剝除 file_data 不得影響同一批 messages 的下游 payload。"""
    msgs = _parts_message()
    _ = _build_request_log(MODEL, None, None, messages=msgs)
    payload = _rewrite_request(MODEL, None, None, messages=msgs)
    assert payload["messages"][0]["content"][2]["file"]["file_data"] == FILE_DATA


def test_request_log_generation_params_recorded_both_modes() -> None:
    """有帶的生成參數記入 request_content(兩模式皆同)。"""
    rf = ResponseFormat.model_validate({"type": "json_object"})
    single = _build_request_log(
        MODEL, "hi", None, temperature=0.3, max_tokens=64, response_format=rf
    )
    multi = _build_request_log(
        MODEL,
        None,
        None,
        messages=_multi_turn(),
        temperature=0.3,
        max_tokens=64,
        response_format=rf,
    )
    for log in (single, multi):
        assert log["temperature"] == 0.3
        assert log["max_tokens"] == 64
        assert log["response_format"] == {"type": "json_object"}


def test_request_log_generation_params_absent_when_none() -> None:
    """未帶生成參數不出現在快照(不記 None)。"""
    for log in (
        _build_request_log(MODEL, "hi", None),
        _build_request_log(MODEL, None, None, messages=_multi_turn()),
    ):
        assert "temperature" not in log
        assert "max_tokens" not in log
        assert "response_format" not in log


def test_request_log_used_tools_derivation_unaffected() -> None:
    """used_tools 由快照 tools 鍵推導(schedule_usage_log 邏輯);兩模式皆成立。"""
    tools = [{"type": "openrouter:web_search"}]
    with_tools = _build_request_log(MODEL, None, None, tools, messages=_multi_turn())
    without_tools = _build_request_log(MODEL, None, None, messages=_multi_turn())
    assert bool(with_tools.get("tools")) is True
    assert bool(without_tools.get("tools")) is False


# ---------------------------------------------------------------------------
# run_chat:internal / openrouter 兩 provider 收到相同 payload
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("provider", ["openrouter", "internal"])
async def test_run_chat_passes_same_payload_to_both_providers(
    monkeypatch: pytest.MonkeyPatch, provider: str
) -> None:
    """payload / request_log 於 provider 分流前組好,兩路徑收到完全相同結構。"""
    captured: dict[str, Any] = {}

    async def fake_whitelist(db: Any, model: str) -> Any:
        return SimpleNamespace(
            provider=provider, model_uid=UUID("00000000-0000-0000-0000-000000000001")
        )

    async def fake_runner(db: Any, **kwargs: Any) -> str:
        captured["payload"] = kwargs["payload"]
        captured["request_log"] = kwargs["request_log"]
        return "ok"

    monkeypatch.setattr(proxy, "_check_model_whitelist", fake_whitelist)
    monkeypatch.setattr(proxy, "_run_chat_openrouter", fake_runner)
    monkeypatch.setattr(proxy, "_run_chat_internal", fake_runner)

    uid = UUID("00000000-0000-0000-0000-000000000002")
    result = await proxy.run_chat(
        None,  # type: ignore[arg-type]
        client_factory=None,  # type: ignore[arg-type]
        department_uid=uid,
        project_uid=uid,
        user_uid=uid,
        model=MODEL,
        text=None,
        images=None,
        videos=None,
        tools=[{"type": "openrouter:web_search"}],
        messages=_multi_turn(),
        temperature=0.5,
        max_tokens=128,
        response_format=ResponseFormat.model_validate({"type": "json_object"}),
    )
    assert result == "ok"
    assert captured["payload"] == {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "你是客服助理"},
            {"role": "user", "content": "上次說到哪?"},
            {"role": "assistant", "content": "說到出貨進度。"},
            {"role": "user", "content": "繼續。"},
        ],
        "tools": [{"type": "openrouter:web_search"}],
        "temperature": 0.5,
        "max_tokens": 128,
        "response_format": {"type": "json_object"},
    }
    assert captured["request_log"]["messages"] == captured["payload"]["messages"]
    assert captured["request_log"]["temperature"] == 0.5
