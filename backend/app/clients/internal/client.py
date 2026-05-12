"""Internal LLM Client — OpenAI-compatible (`/chat/completions`)。

對齊 docs/Tasks/v1.2/propose-v1.2.0.md § 5.3 / § 6 / § 7。
"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class InternalError(Exception):
    """地端模型呼叫一般錯誤。"""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(f"{status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


class InternalAuthError(InternalError):
    """401:api_key 錯誤。"""


class InternalRateLimitError(InternalError):
    """429:server 端速率限制。"""


class InternalUnavailableError(InternalError):
    """連線失敗 / 5xx / invalid JSON。"""


class InternalClient:
    """OpenAI-compatible chat completions client。"""

    def __init__(self, client: httpx.AsyncClient, base_url: str, api_key: str | None) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key

    async def chat_completion(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        try:
            resp = await self._client.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
        except httpx.HTTPError as exc:
            logger.exception("Internal LLM HTTP 連線失敗")
            raise InternalUnavailableError(502, str(exc)) from exc

        if resp.status_code == 401:
            raise InternalAuthError(401, resp.text[:500])
        if resp.status_code == 429:
            raise InternalRateLimitError(429, resp.text[:500])
        if resp.status_code >= 500:
            raise InternalUnavailableError(resp.status_code, resp.text[:500])
        if resp.status_code >= 400:
            raise InternalError(resp.status_code, resp.text[:500])

        try:
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            raise InternalUnavailableError(502, "invalid JSON response") from exc


_singleton_client: httpx.AsyncClient | None = None


async def get_internal_client():
    """FastAPI Dependency — 共用 httpx.AsyncClient 單例。

    base_url 未設 → yield None,呼叫端應拒絕 provider=internal 的呼叫(provider_misconfigured)。
    """
    global _singleton_client
    settings = get_settings()
    if not settings.INTERNAL_LLM_BASE_URL:
        yield None
        return
    if _singleton_client is None:
        _singleton_client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.INTERNAL_LLM_REQUEST_TIMEOUT),
        )
    yield InternalClient(
        _singleton_client,
        settings.INTERNAL_LLM_BASE_URL,
        settings.INTERNAL_LLM_API_KEY or None,
    )
