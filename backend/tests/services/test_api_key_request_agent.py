"""api_key_request_agent.validate_fields() 單元測試 — 對齊 tasks-v1.9.1.md § AI 欄位驗證。

以假 OpenRouterClient + 假 settings 測:JSON 解析、圍欄去除、信心 clamp、
金鑰未設與呼叫失敗的優雅降級(confidence=0 + error)。
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

import app.services.api_key_request_agent as agent
from app.models.api_key_request import ApiKeyRequest
from app.models.department import Department


def _req() -> ApiKeyRequest:
    return ApiKeyRequest(
        department_name="資訊部",
        department_code="IT",
        project_name="客服機器人",
        project_url="https://github.com/df/bot",
        owner_name="王小明",
        owner_email="ming@df-recycle.com.tw",
    )


def _dept() -> Department:
    return Department(department_uid=uuid4(), code="IT", name="資訊部")


def _patch_settings(monkeypatch, *, key: str = "sk-test", model: str = "test-model"):
    monkeypatch.setattr(
        agent,
        "get_settings",
        lambda: SimpleNamespace(
            DEFAULT_OPENROUTER_KEY=key, API_KEY_AGENT_MODEL=model
        ),
    )


class _FakeClient:
    """可指定回傳 content 或拋例外的假 OpenRouterClient。"""

    def __init__(self, *, content: str | None = None, raises: Exception | None = None):
        self._content = content
        self._raises = raises
        self.calls: list[dict] = []

    async def chat_completion(self, payload, *, api_key):
        self.calls.append({"payload": payload, "api_key": api_key})
        if self._raises is not None:
            raise self._raises
        return {"choices": [{"message": {"content": self._content}}]}


@pytest.mark.asyncio
async def test_valid_json_returns_confidence_and_reason(monkeypatch):
    _patch_settings(monkeypatch)
    client = _FakeClient(content='{"confidence": 97, "reason": "看似合理"}')
    res = await agent.validate_fields(client, _req(), _dept())
    assert res.confidence == 97
    assert res.reason == "看似合理"
    assert res.error is None
    # 確認用 DEFAULT_OPENROUTER_KEY 與設定模型送出
    assert client.calls[0]["api_key"] == "sk-test"
    assert client.calls[0]["payload"]["model"] == "test-model"


@pytest.mark.asyncio
async def test_json_with_code_fence_is_parsed(monkeypatch):
    _patch_settings(monkeypatch)
    client = _FakeClient(content='```json\n{"confidence": 80, "reason": "x"}\n```')
    res = await agent.validate_fields(client, _req(), _dept())
    assert res.confidence == 80
    assert res.error is None


@pytest.mark.asyncio
async def test_confidence_is_clamped(monkeypatch):
    _patch_settings(monkeypatch)
    client = _FakeClient(content='{"confidence": 150, "reason": "超界"}')
    res = await agent.validate_fields(client, _req(), _dept())
    assert res.confidence == 100


@pytest.mark.asyncio
async def test_malformed_json_degrades_to_zero(monkeypatch):
    _patch_settings(monkeypatch)
    client = _FakeClient(content="這不是 JSON")
    res = await agent.validate_fields(client, _req(), _dept())
    assert res.confidence == 0
    assert res.error is not None


@pytest.mark.asyncio
async def test_client_error_degrades_to_zero(monkeypatch):
    _patch_settings(monkeypatch)
    client = _FakeClient(raises=RuntimeError("boom"))
    res = await agent.validate_fields(client, _req(), _dept())
    assert res.confidence == 0
    assert "boom" in res.error


@pytest.mark.asyncio
async def test_empty_key_degrades_without_calling(monkeypatch):
    """DEFAULT_OPENROUTER_KEY 未設 → 直接降級,不呼叫 client。"""
    _patch_settings(monkeypatch, key="")
    client = _FakeClient(content='{"confidence": 99, "reason": "x"}')
    res = await agent.validate_fields(client, _req(), _dept())
    assert res.confidence == 0
    assert "DEFAULT_OPENROUTER_KEY" in res.error
    assert client.calls == []
