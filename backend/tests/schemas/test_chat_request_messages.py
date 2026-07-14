"""ChatRequest messages 直傳模式 + 生成參數三欄 schema 驗證測試(v2.1.2, task-431)。

涵蓋:互斥(messages+text / messages+images / messages+files)、空陣列、role 白名單、
content parts 型別白名單、字串與 parts 兩種 content、temperature / max_tokens 值域、
response_format 型別化白名單、三欄未帶預設 None、舊單輪請求完全不受影響,
以及提供 task-432 透傳用的 model_dump 形狀契約。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.model import ChatMessage, ChatRequest, ResponseFormat

MODEL = "openai/gpt-4o-mini"


def _messages_body() -> list[dict[str, object]]:
    return [
        {"role": "system", "content": "你是客服助理"},
        {"role": "user", "content": "上次說到哪?"},
        {"role": "assistant", "content": "說到出貨進度。"},
        {"role": "user", "content": "繼續。"},
    ]


# ---------------------------------------------------------------------------
# 合法 messages 模式
# ---------------------------------------------------------------------------


def test_messages_multi_turn_str_content() -> None:
    req = ChatRequest(model=MODEL, messages=_messages_body())  # type: ignore[arg-type]
    assert req.messages is not None
    assert [m.role for m in req.messages] == ["system", "user", "assistant", "user"]
    assert req.messages[0].content == "你是客服助理"


def test_messages_parts_content() -> None:
    parts: list[dict[str, object]] = [
        {"type": "text", "text": "看一下這張圖與檔案"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
        {"type": "file", "file": {"filename": "report.pdf", "file_data": "data:application/pdf;base64,BBBB"}},
    ]
    req = ChatRequest(model=MODEL, messages=[{"role": "user", "content": parts}])  # type: ignore[list-item]
    assert req.messages is not None
    content = req.messages[0].content
    assert isinstance(content, list)
    assert [p.type for p in content] == ["text", "image_url", "file"]


def test_messages_with_tools_allowed() -> None:
    """tools 與 messages 模式可搭配(互斥僅針對 text/images/files)。"""
    req = ChatRequest(
        model=MODEL,
        messages=[{"role": "user", "content": "查一下"}],  # type: ignore[list-item]
        tools=[{"type": "openrouter:web_search"}],
    )
    assert req.tools == [{"type": "openrouter:web_search"}]


def test_messages_with_empty_string_text_not_conflict() -> None:
    """互斥判定為「同時非空」:text 為空字串不算衝突。"""
    req = ChatRequest(model=MODEL, text="", messages=[{"role": "user", "content": "hi"}])  # type: ignore[list-item]
    assert req.messages is not None


# ---------------------------------------------------------------------------
# 互斥與空陣列
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "extra",
    [
        {"text": "hello"},
        {"images": ["data:image/png;base64,AAAA"]},
        {"files": [{"filename": "a.pdf", "file_data": "data:application/pdf;base64,AA"}]},
    ],
    ids=["text", "images", "files"],
)
def test_messages_exclusive_with_single_turn_fields(extra: dict[str, object]) -> None:
    with pytest.raises(ValidationError) as exc_info:
        ChatRequest(model=MODEL, messages=[{"role": "user", "content": "hi"}], **extra)  # type: ignore[arg-type]
    assert "互斥" in str(exc_info.value)


def test_messages_empty_list_rejected() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ChatRequest(model=MODEL, messages=[])
    assert "不可為空陣列" in str(exc_info.value)


# ---------------------------------------------------------------------------
# role / parts 白名單
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("role", ["tool", "developer", "function", ""])
def test_role_whitelist_rejects_unknown(role: str) -> None:
    with pytest.raises(ValidationError):
        ChatRequest(model=MODEL, messages=[{"role": role, "content": "hi"}])  # type: ignore[list-item]


@pytest.mark.parametrize(
    "part",
    [
        {"type": "video", "video_url": {"url": "https://example.com/v.mp4"}},
        {"type": "input_audio", "input_audio": {"data": "AAAA", "format": "wav"}},
        {"type": "unknown"},
    ],
    ids=["video", "input_audio", "unknown"],
)
def test_content_part_type_whitelist_rejects_unknown(part: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ChatRequest(model=MODEL, messages=[{"role": "user", "content": [part]}])  # type: ignore[list-item]


def test_message_unknown_field_rejected() -> None:
    """未知欄位拒收(白名單透傳,防夾帶 tool_calls 等未開放欄位)。"""
    with pytest.raises(ValidationError):
        ChatRequest(
            model=MODEL,
            messages=[{"role": "assistant", "content": "x", "tool_calls": []}],  # type: ignore[list-item]
        )


# ---------------------------------------------------------------------------
# 生成參數:temperature / max_tokens
# ---------------------------------------------------------------------------


def test_generation_params_default_none() -> None:
    req = ChatRequest(model=MODEL, text="hi")
    assert req.temperature is None
    assert req.max_tokens is None
    assert req.response_format is None


@pytest.mark.parametrize("temperature", [0, 0.7, 2])
def test_temperature_valid_boundaries(temperature: float) -> None:
    req = ChatRequest(model=MODEL, text="hi", temperature=temperature)
    assert req.temperature == temperature


@pytest.mark.parametrize("temperature", [-0.1, 2.1])
def test_temperature_out_of_range(temperature: float) -> None:
    with pytest.raises(ValidationError):
        ChatRequest(model=MODEL, text="hi", temperature=temperature)


def test_max_tokens_valid_boundary() -> None:
    req = ChatRequest(model=MODEL, text="hi", max_tokens=1)
    assert req.max_tokens == 1


@pytest.mark.parametrize("max_tokens", [0, -1])
def test_max_tokens_below_one(max_tokens: int) -> None:
    with pytest.raises(ValidationError):
        ChatRequest(model=MODEL, text="hi", max_tokens=max_tokens)


def test_generation_params_allowed_in_both_modes() -> None:
    """生成參數與內容模式正交:單輪與 messages 模式皆可帶。"""
    single = ChatRequest(model=MODEL, text="hi", temperature=0.5, max_tokens=100)
    multi = ChatRequest(
        model=MODEL,
        messages=[{"role": "user", "content": "hi"}],  # type: ignore[list-item]
        temperature=0.5,
        max_tokens=100,
        response_format={"type": "json_object"},  # type: ignore[arg-type]
    )
    assert single.temperature == multi.temperature == 0.5
    assert single.max_tokens == multi.max_tokens == 100


# ---------------------------------------------------------------------------
# 生成參數:response_format 型別化白名單
# ---------------------------------------------------------------------------


def test_response_format_json_object_valid() -> None:
    req = ChatRequest(model=MODEL, text="hi", response_format={"type": "json_object"})  # type: ignore[arg-type]
    assert req.response_format is not None
    assert req.response_format.type == "json_object"
    assert req.response_format.json_schema is None


def test_response_format_json_schema_valid() -> None:
    schema = {"name": "answer", "strict": True, "schema": {"type": "object"}}
    req = ChatRequest(
        model=MODEL,
        text="hi",
        response_format={"type": "json_schema", "json_schema": schema},  # type: ignore[arg-type]
    )
    assert req.response_format is not None
    assert req.response_format.json_schema == schema


@pytest.mark.parametrize("bad_type", ["text", "json", "xml", ""])
def test_response_format_type_whitelist(bad_type: str) -> None:
    with pytest.raises(ValidationError):
        ChatRequest(model=MODEL, text="hi", response_format={"type": bad_type})  # type: ignore[arg-type]


def test_response_format_json_schema_requires_object() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ChatRequest(model=MODEL, text="hi", response_format={"type": "json_schema"})  # type: ignore[arg-type]
    assert "必須提供 json_schema" in str(exc_info.value)


def test_response_format_json_object_forbids_schema_object() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ChatRequest(
            model=MODEL,
            text="hi",
            response_format={"type": "json_object", "json_schema": {"type": "object"}},  # type: ignore[arg-type]
        )
    assert "不可提供 json_schema" in str(exc_info.value)


def test_response_format_raw_dict_extra_fields_rejected() -> None:
    """禁 raw dict 透傳:未知欄位拒收。"""
    with pytest.raises(ValidationError):
        ChatRequest(
            model=MODEL,
            text="hi",
            response_format={"type": "json_object", "top_p": 0.9},  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# 舊單輪模式不受影響
# ---------------------------------------------------------------------------


def test_legacy_single_turn_text_only_unaffected() -> None:
    req = ChatRequest(model=MODEL, text="hello")
    assert req.text == "hello"
    assert req.messages is None
    assert req.temperature is None
    assert req.max_tokens is None
    assert req.response_format is None


def test_legacy_single_turn_full_fields_unaffected() -> None:
    req = ChatRequest(
        model=MODEL,
        text="hello",
        images=["data:image/png;base64,AAAA"],
        files=[{"filename": "a.pdf", "file_data": "data:application/pdf;base64,AA"}],  # type: ignore[list-item]
        tools=[{"type": "openrouter:web_search"}],
    )
    assert req.messages is None
    assert req.images == ["data:image/png;base64,AAAA"]
    assert req.files is not None and req.files[0].filename == "a.pdf"


# ---------------------------------------------------------------------------
# model_dump 形狀契約(task-432 透傳依據)
# ---------------------------------------------------------------------------


def test_chat_message_model_dump_shapes() -> None:
    str_msg = ChatMessage.model_validate({"role": "system", "content": "你是助理"})
    assert str_msg.model_dump(exclude_none=True) == {"role": "system", "content": "你是助理"}

    parts_msg = ChatMessage.model_validate(
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "看圖"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
                {"type": "file", "file": {"filename": "a.pdf", "file_data": "data:...,AA"}},
            ],
        }
    )
    assert parts_msg.model_dump(exclude_none=True) == {
        "role": "user",
        "content": [
            {"type": "text", "text": "看圖"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
            {"type": "file", "file": {"filename": "a.pdf", "file_data": "data:...,AA"}},
        ],
    }


def test_response_format_model_dump_shapes() -> None:
    json_object = ResponseFormat.model_validate({"type": "json_object"})
    assert json_object.model_dump(exclude_none=True) == {"type": "json_object"}

    schema = {"name": "answer", "schema": {"type": "object"}}
    json_schema = ResponseFormat.model_validate({"type": "json_schema", "json_schema": schema})
    assert json_schema.model_dump(exclude_none=True) == {
        "type": "json_schema",
        "json_schema": schema,
    }
