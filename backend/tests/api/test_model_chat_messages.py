"""model_chat 端點 messages 直傳 + 生成參數整合測試(v2.1.2, task-433)。

沿用本專案 mock 風格(見 tests/api/test_usage_logs.py / test_users_disable.py):
- FastAPI app + httpx.AsyncClient(ASGITransport)。
- dependency_overrides 覆寫 require_sdk_caller(假 SdkCallerContext)、get_db(假
  AsyncSession,execute 回白名單模型列)與 get_chat_client_factory(假 OpenRouter
  client,捕捉下游 payload、回 canned response / SSE)。
- monkeypatch proxy 模組的 OpenRouterKeyRepository / decrypt_key / schedule_usage_log
  (捕捉 usage_logs 快照參數)。
- schema 驗證(互斥 / 白名單 / 值域)走真實 `ChatRequest` + main.py 的
  RequestValidationError handler,實測 400 的狀態碼與 body 形狀。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.clients.factory import get_chat_client_factory
from app.core.database import get_db
from app.core.deps import require_sdk_caller
from app.main import create_app
from app.schemas.actor import SdkCallerContext
from app.services import proxy

pytestmark = pytest.mark.asyncio

MODEL = "openai/gpt-4o-mini"
IMAGE_URL = "data:image/png;base64,AAAA"
FILE_DATA = "data:application/pdf;base64,BBBB"

MULTI_TURN = [
    {"role": "system", "content": "你是客服助理"},
    {"role": "user", "content": "上次說到哪?"},
    {"role": "assistant", "content": "說到出貨進度。"},
    {"role": "user", "content": "繼續。"},
]

OPENROUTER_RESPONSE = {
    "id": "gen-test-123",
    "model": MODEL,
    "choices": [{"message": {"role": "assistant", "content": "模型回覆內容"}}],
    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, "cost": 0.001},
}

SSE_LINES = [
    'data: {"id":"gen-test-123","choices":[{"delta":{"content":"哈"}}]}',
    'data: {"id":"gen-test-123","choices":[{"delta":{"content":"囉"}}]}',
    (
        'data: {"id":"gen-test-123","choices":[],'
        '"usage":{"prompt_tokens":10,"completion_tokens":2,"total_tokens":12}}'
    ),
    "data: [DONE]",
]


# --- 假下游 client / factory(捕捉送往 OpenRouter 的 payload) ---


class _FakeOpenRouterClient:
    def __init__(self) -> None:
        self.payloads: list[dict[str, Any]] = []

    async def chat_completion(self, payload: dict[str, Any], *, api_key: str) -> dict[str, Any]:
        assert api_key == "sk-or-test"
        self.payloads.append(payload)
        return OPENROUTER_RESPONSE

    async def stream_chat_completion(
        self, payload: dict[str, Any], *, api_key: str
    ) -> AsyncIterator[str]:
        assert api_key == "sk-or-test"
        self.payloads.append(payload)
        for line in SSE_LINES:
            yield line


class _FakeClientFactory:
    def __init__(self, client: _FakeOpenRouterClient) -> None:
        self._client = client

    def openrouter(self) -> _FakeOpenRouterClient:
        return self._client


# --- 假 DB(白名單查詢)與 Key repo ---


class _FakeResult:
    def __init__(self, row: object) -> None:
        self._row = row

    def scalar_one_or_none(self) -> object:
        return self._row


class _FakeDb:
    """假 AsyncSession:只需承接 `_check_model_whitelist` 的 execute。"""

    def __init__(self, model_row: object) -> None:
        self._model_row = model_row

    async def execute(self, stmt: object) -> _FakeResult:
        return _FakeResult(self._model_row)

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


def _make_key_repo_cls(key_row: SimpleNamespace) -> type:
    class _FakeKeyRepo:
        def __init__(self, db: object) -> None:
            self.db = db

        async def list_active_by_department(self, department_uid: object) -> list[SimpleNamespace]:
            return [key_row]

    return _FakeKeyRepo


# --- world fixture:一次接好所有替身,回傳 client 工廠與捕捉容器 ---


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    model_row = SimpleNamespace(provider="openrouter", model_uid=uuid4(), model_key=MODEL)
    key_row = SimpleNamespace(
        openrouter_key_uid=uuid4(),  # 每測試新 uid,避免共用 in-memory limiter 狀態
        rpm_limit=0,  # 0 = 不限
        min_request_interval_ms=0,
    )
    or_client = _FakeOpenRouterClient()
    usage_logs: list[dict[str, Any]] = []

    monkeypatch.setattr(proxy, "OpenRouterKeyRepository", _make_key_repo_cls(key_row))
    monkeypatch.setattr(proxy, "decrypt_key", lambda row: "sk-or-test")
    monkeypatch.setattr(proxy, "schedule_usage_log", lambda **kw: usage_logs.append(kw))

    caller = SdkCallerContext(
        sdk_api_key_uid=uuid4(),
        department_uid=uuid4(),
        department_code="RD",
        project_uid=uuid4(),
        project_code="PRJ-TEST",
        user_uid=uuid4(),
    )

    app = create_app()

    async def _fake_get_db():
        yield _FakeDb(model_row)

    app.dependency_overrides[get_db] = _fake_get_db
    app.dependency_overrides[require_sdk_caller] = lambda: caller
    app.dependency_overrides[get_chat_client_factory] = lambda: _FakeClientFactory(or_client)

    def _client() -> AsyncClient:
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    return SimpleNamespace(
        make_client=_client,
        or_client=or_client,
        usage_logs=usage_logs,
        model_row=model_row,
        caller=caller,
    )


def _ok_body() -> dict[str, Any]:
    return {"success": True, "code": 200, "data": "模型回覆內容", "detail": "success"}


# ---------------------------------------------------------------------------
# messages 模式:三入口 200 正常回覆
# ---------------------------------------------------------------------------


async def test_messages_mode_multi_turn_200(world: SimpleNamespace) -> None:
    async with world.make_client() as client:
        resp = await client.post(
            "/api/v1/model/chat", json={"model": MODEL, "messages": MULTI_TURN}
        )
    assert resp.status_code == 200, resp.text
    assert resp.json() == _ok_body()
    # 下游 payload:messages 原樣透傳、不重組、無生成參數鍵
    assert world.or_client.payloads == [{"model": MODEL, "messages": MULTI_TURN}]


async def test_messages_mode_parts_content_200(world: SimpleNamespace) -> None:
    """parts content(text / image_url / file)白名單型別可過端到端。"""
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "看一下這張圖與檔案"},
                {"type": "image_url", "image_url": {"url": IMAGE_URL}},
                {"type": "file", "file": {"filename": "report.pdf", "file_data": FILE_DATA}},
            ],
        }
    ]
    async with world.make_client() as client:
        resp = await client.post("/api/v1/model/chat", json={"model": MODEL, "messages": messages})
    assert resp.status_code == 200, resp.text
    assert resp.json() == _ok_body()
    payload = world.or_client.payloads[0]
    assert payload["messages"] == messages  # file_data 完整送下游
    # 快照:file part 僅記檔名(§D.4)
    log = world.usage_logs[0]["request_log"]
    assert log["messages"][0]["content"][2] == {"type": "file", "file": {"filename": "report.pdf"}}


async def test_deprecated_alias_same_behavior(world: SimpleNamespace) -> None:
    """deprecated /model/openrouter/chat 走同 handler,messages 模式行為一致。"""
    body = {"model": MODEL, "messages": MULTI_TURN, "temperature": 0.7}
    async with world.make_client() as client:
        canonical = await client.post("/api/v1/model/chat", json=body)
        deprecated = await client.post("/api/v1/model/openrouter/chat", json=body)
    assert canonical.status_code == deprecated.status_code == 200
    assert canonical.json() == deprecated.json() == _ok_body()
    assert world.or_client.payloads[0] == world.or_client.payloads[1]


# ---------------------------------------------------------------------------
# /chat/stream:同 body 串流正常
# ---------------------------------------------------------------------------


async def test_stream_messages_mode_200(world: SimpleNamespace) -> None:
    async with world.make_client() as client:
        resp = await client.post(
            "/api/v1/model/chat/stream",
            json={"model": MODEL, "messages": MULTI_TURN, "max_tokens": 64},
        )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/event-stream")
    # 簡化 SSE:僅 {id, content};usage / role 等內部 chunk 不外露
    assert 'data: {"id": "gen-test-123", "content": "哈"}' in resp.text
    assert 'data: {"id": "gen-test-123", "content": "囉"}' in resp.text
    assert resp.text.endswith("data: [DONE]\n\n")
    assert "usage" not in resp.text
    # payload:messages 透傳 + 生成參數 + 串流旗標(僅多 stream / stream_options)
    payload = world.or_client.payloads[0]
    assert payload["messages"] == MULTI_TURN
    assert payload["max_tokens"] == 64
    assert payload["stream"] is True
    assert payload["stream_options"] == {"include_usage": True}
    # 串流結束後記帳:快照含 messages 與生成參數
    log = world.usage_logs[0]
    assert log["status"] == "success"
    assert log["request_log"]["messages"] == MULTI_TURN
    assert log["request_log"]["max_tokens"] == 64


async def test_stream_old_client_text_mode_unchanged(world: SimpleNamespace) -> None:
    """串流端點舊模式(只帶 text)回歸:payload 組裝與 v2.1.1 一致。"""
    async with world.make_client() as client:
        resp = await client.post(
            "/api/v1/model/chat/stream", json={"model": MODEL, "text": "hello"}
        )
    assert resp.status_code == 200, resp.text
    payload = world.or_client.payloads[0]
    assert payload["messages"] == [
        {"role": "user", "content": [{"type": "text", "text": "hello"}]}
    ]
    for key in ("temperature", "max_tokens", "response_format"):
        assert key not in payload


# ---------------------------------------------------------------------------
# 舊 client 回歸:只帶 text/images/files → 200,payload 與 v2.1.1 一致
# ---------------------------------------------------------------------------


async def test_old_client_single_turn_unchanged(world: SimpleNamespace) -> None:
    body = {
        "model": MODEL,
        "text": "hello",
        "images": [IMAGE_URL],
        "files": [{"filename": "report.pdf", "file_data": FILE_DATA}],
        "tools": [{"type": "openrouter:web_search"}],
    }
    async with world.make_client() as client:
        resp = await client.post("/api/v1/model/chat", json=body)
    assert resp.status_code == 200, resp.text
    assert resp.json() == _ok_body()
    assert world.or_client.payloads == [
        {
            "model": MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "hello"},
                        {"type": "image_url", "image_url": {"url": IMAGE_URL}},
                        {
                            "type": "file",
                            "file": {"filename": "report.pdf", "file_data": FILE_DATA},
                        },
                    ],
                }
            ],
            "tools": [{"type": "openrouter:web_search"}],
        }
    ]
    # 新欄位不出現在 payload 與快照(v2.1.1 形狀不變)
    log = world.usage_logs[0]["request_log"]
    assert log == {
        "model": MODEL,
        "text": "hello",
        "images": [IMAGE_URL],
        "tools": [{"type": "openrouter:web_search"}],
        "files": ["report.pdf"],
    }


# ---------------------------------------------------------------------------
# 400:互斥 / 空陣列 / 白名單(統一 RequestValidationError → ApiResponse 包裝)
# ---------------------------------------------------------------------------


def _assert_400(resp: Any, detail_contains: str) -> None:
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body["success"] is False
    assert body["code"] == 400
    assert body["data"] is None
    assert detail_contains in body["detail"]


@pytest.mark.parametrize(
    "extra",
    [
        {"text": "hi"},
        {"images": [IMAGE_URL]},
        {"files": [{"filename": "a.pdf", "file_data": FILE_DATA}]},
    ],
)
async def test_messages_conflicts_with_single_turn_fields_400(
    world: SimpleNamespace, extra: dict[str, Any]
) -> None:
    async with world.make_client() as client:
        resp = await client.post(
            "/api/v1/model/chat", json={"model": MODEL, "messages": MULTI_TURN, **extra}
        )
    _assert_400(resp, "互斥")
    assert world.or_client.payloads == []  # 未觸達下游
    assert world.usage_logs == []


async def test_messages_empty_list_400(world: SimpleNamespace) -> None:
    async with world.make_client() as client:
        resp = await client.post("/api/v1/model/chat", json={"model": MODEL, "messages": []})
    _assert_400(resp, "messages 不可為空陣列")


async def test_messages_invalid_role_400(world: SimpleNamespace) -> None:
    async with world.make_client() as client:
        resp = await client.post(
            "/api/v1/model/chat",
            json={"model": MODEL, "messages": [{"role": "tool", "content": "x"}]},
        )
    _assert_400(resp, "messages.0.role")


async def test_messages_invalid_part_type_400(world: SimpleNamespace) -> None:
    async with world.make_client() as client:
        resp = await client.post(
            "/api/v1/model/chat",
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": [{"type": "video", "video": "x"}]}],
            },
        )
    _assert_400(resp, "messages.0.content")


# ---------------------------------------------------------------------------
# 生成參數:合法注入 / 越界 400 / 未帶不出現
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "content_body",
    [
        {"text": "hi"},
        {"messages": MULTI_TURN},
    ],
    ids=["single-turn", "messages"],
)
async def test_generation_params_injected_both_modes(
    world: SimpleNamespace, content_body: dict[str, Any]
) -> None:
    body = {
        "model": MODEL,
        **content_body,
        "temperature": 0.7,
        "max_tokens": 256,
        "response_format": {"type": "json_object"},
    }
    async with world.make_client() as client:
        resp = await client.post("/api/v1/model/chat", json=body)
    assert resp.status_code == 200, resp.text
    payload = world.or_client.payloads[0]
    assert payload["temperature"] == 0.7
    assert payload["max_tokens"] == 256
    assert payload["response_format"] == {"type": "json_object"}
    # usage_logs 快照含生成參數(task-433 Acceptance)
    log = world.usage_logs[0]["request_log"]
    assert log["temperature"] == 0.7
    assert log["max_tokens"] == 256
    assert log["response_format"] == {"type": "json_object"}


async def test_response_format_json_schema_injected(world: SimpleNamespace) -> None:
    schema = {"name": "answer", "strict": True, "schema": {"type": "object"}}
    body = {
        "model": MODEL,
        "messages": MULTI_TURN,
        "response_format": {"type": "json_schema", "json_schema": schema},
    }
    async with world.make_client() as client:
        resp = await client.post("/api/v1/model/chat", json=body)
    assert resp.status_code == 200, resp.text
    assert world.or_client.payloads[0]["response_format"] == {
        "type": "json_schema",
        "json_schema": schema,
    }


@pytest.mark.parametrize(
    ("field", "value", "detail_contains"),
    [
        ("temperature", -0.1, "temperature"),
        ("temperature", 2.1, "temperature"),
        ("max_tokens", 0, "max_tokens"),
        ("response_format", {"type": "text"}, "response_format"),
        ("response_format", {"type": "json_schema"}, "json_schema"),  # 缺 json_schema 物件
    ],
)
async def test_generation_params_invalid_400(
    world: SimpleNamespace, field: str, value: Any, detail_contains: str
) -> None:
    async with world.make_client() as client:
        resp = await client.post(
            "/api/v1/model/chat", json={"model": MODEL, "text": "hi", field: value}
        )
    _assert_400(resp, detail_contains)
    assert world.or_client.payloads == []


async def test_generation_params_absent_not_in_payload(world: SimpleNamespace) -> None:
    async with world.make_client() as client:
        resp = await client.post(
            "/api/v1/model/chat", json={"model": MODEL, "messages": MULTI_TURN}
        )
    assert resp.status_code == 200, resp.text
    payload = world.or_client.payloads[0]
    log = world.usage_logs[0]["request_log"]
    for key in ("temperature", "max_tokens", "response_format"):
        assert key not in payload
        assert key not in log


# ---------------------------------------------------------------------------
# tools 在 messages 模式可用
# ---------------------------------------------------------------------------


async def test_tools_available_in_messages_mode(world: SimpleNamespace) -> None:
    tools = [{"type": "openrouter:web_search"}]
    async with world.make_client() as client:
        resp = await client.post(
            "/api/v1/model/chat",
            json={"model": MODEL, "messages": MULTI_TURN, "tools": tools},
        )
    assert resp.status_code == 200, resp.text
    assert world.or_client.payloads[0]["tools"] == tools
    # used_tools 由快照 tools 鍵推導(schedule_usage_log 現況邏輯)
    assert world.usage_logs[0]["request_log"]["tools"] == tools


# ---------------------------------------------------------------------------
# usage_logs:messages 模式有寫入且 request_content.messages 存在
# ---------------------------------------------------------------------------


async def test_usage_log_written_with_messages_snapshot(world: SimpleNamespace) -> None:
    async with world.make_client() as client:
        resp = await client.post(
            "/api/v1/model/chat",
            json={"model": MODEL, "messages": MULTI_TURN, "temperature": 0.3},
        )
    assert resp.status_code == 200, resp.text
    assert len(world.usage_logs) == 1
    log = world.usage_logs[0]
    assert log["status"] == "success"
    assert log["error_code"] is None
    assert log["model"] == MODEL
    assert log["model_uid"] == world.model_row.model_uid
    assert log["department_uid"] == world.caller.department_uid
    assert log["project_uid"] == world.caller.project_uid
    assert log["user_uid"] == world.caller.user_uid
    assert log["resp"] == OPENROUTER_RESPONSE
    # request_content 快照:messages 原樣 + 生成參數,無單輪欄位
    assert log["request_log"]["messages"] == MULTI_TURN
    assert log["request_log"]["temperature"] == 0.3
    assert "text" not in log["request_log"]


# ---------------------------------------------------------------------------
# OpenAPI:/api/openapi.json 的 ChatRequest 含新欄位
# ---------------------------------------------------------------------------


async def test_openapi_chat_request_has_new_fields(world: SimpleNamespace) -> None:
    async with world.make_client() as client:
        resp = await client.get("/api/openapi.json")
    assert resp.status_code == 200
    props = resp.json()["components"]["schemas"]["ChatRequest"]["properties"]
    for key in ("messages", "temperature", "max_tokens", "response_format"):
        assert key in props, f"ChatRequest 缺 {key} 欄位"
