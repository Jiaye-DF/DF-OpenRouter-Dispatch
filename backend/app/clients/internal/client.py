"""Internal LLM Client — OpenAI-compatible (`/chat/completions`)。

v1.2 增量:base_url 與 api_key 改由 DB(`internal_keys` 表)逐次注入;
原 env-based `get_internal_client` Dependency 已移除。

對齊 docs/Tasks/v1.2/propose-v1.2.0.md § 6 / § 7。
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
    """OpenAI-compatible chat completions client(per-Key)。"""

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
            logger.exception("Internal LLM HTTP 連線失敗 base_url=%s", self._base_url)
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


_singleton_httpx_client: httpx.AsyncClient | None = None


async def get_internal_httpx_client() -> httpx.AsyncClient:
    """FastAPI Dependency — 共用 httpx.AsyncClient 單例(timeout 從 env 讀)。

    proxy.py 取得 client 後,逐次以 (base_url, api_key) 構造 InternalClient。
    """
    global _singleton_httpx_client
    settings = get_settings()
    if _singleton_httpx_client is None:
        _singleton_httpx_client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.INTERNAL_LLM_REQUEST_TIMEOUT),
        )
    return _singleton_httpx_client
