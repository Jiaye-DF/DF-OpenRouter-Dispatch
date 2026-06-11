from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.clients.openrouter.errors import (
    OpenRouterAuthError,
    OpenRouterError,
    OpenRouterForbiddenError,
    OpenRouterModelNotFoundError,
    OpenRouterRateLimitError,
)
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class OpenRouterClient:
    def __init__(self, client: httpx.AsyncClient, base_url: str) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")

    async def chat_completion(
        self,
        payload: dict[str, Any],
        *,
        api_key: str,
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://df-openrouter-dispatch.local",
            "X-Title": "DF-OpenRouter-Dispatch",
        }
        try:
            resp = await self._client.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
        except httpx.HTTPError as exc:
            logger.exception("OpenRouter HTTP 連線失敗")
            raise OpenRouterError(502, str(exc)) from exc

        if resp.status_code == 401:
            raise OpenRouterAuthError(401, resp.text[:500])
        if resp.status_code == 403:
            raise OpenRouterForbiddenError(403, resp.text[:500])
        if resp.status_code == 404:
            raise OpenRouterModelNotFoundError(404, resp.text[:500])
        if resp.status_code == 429:
            raise OpenRouterRateLimitError(429, resp.text[:500])
        if resp.status_code >= 500:
            raise OpenRouterError(resp.status_code, resp.text[:500])
        if resp.status_code >= 400:
            raise OpenRouterError(resp.status_code, resp.text[:500])

        try:
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            raise OpenRouterError(502, "invalid JSON response") from exc

    async def stream_chat_completion(
        self,
        payload: dict[str, Any],
        *,
        api_key: str,
    ) -> AsyncIterator[str]:
        """串流版 chat completion — 逐行 yield OpenRouter 的 SSE 內容。

        與 `chat_completion` 不同:以 httpx streaming 開連線,**先**依首個回應的 HTTP
        狀態碼拋出對應錯誤(供 service 層在「吐出第一行之前」做 Key failover 判斷);
        狀態為 200 才開始 `yield` SSE 行。一旦開始 yield 即進入「不可重試」階段
        (對齊 docs/Design-Base/50-openrouter.md § 8)。

        逾時採 `OPENROUTER_STREAM_TIMEOUT`(非一般 `OPENROUTER_API_TIMEOUT`),
        以容許串流長時間維持與 chunk 間久無資料。

        Args:
            payload: 已含 `stream=True` 的 `/chat/completions` payload。
            api_key: 解密後的 OpenRouter API Key。

        Yields:
            OpenRouter SSE 的單行字串(不含換行;呼叫端負責還原 `\\n\\n` 框架)。

        Raises:
            OpenRouterAuthError / OpenRouterForbiddenError / OpenRouterModelNotFoundError /
            OpenRouterRateLimitError / OpenRouterError:依首個回應狀態碼,均於 yield
            第一行之前拋出。串流中途的連線錯誤亦以 OpenRouterError(502) 拋出。
        """
        settings = get_settings()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://df-openrouter-dispatch.local",
            "X-Title": "DF-OpenRouter-Dispatch",
        }
        try:
            async with self._client.stream(
                "POST",
                f"{self._base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=httpx.Timeout(settings.OPENROUTER_STREAM_TIMEOUT),
            ) as resp:
                if resp.status_code >= 400:
                    await resp.aread()
                    body = resp.text[:500]
                    if resp.status_code == 401:
                        raise OpenRouterAuthError(401, body)
                    if resp.status_code == 403:
                        raise OpenRouterForbiddenError(403, body)
                    if resp.status_code == 404:
                        raise OpenRouterModelNotFoundError(404, body)
                    if resp.status_code == 429:
                        raise OpenRouterRateLimitError(429, body)
                    raise OpenRouterError(resp.status_code, body)
                async for line in resp.aiter_lines():
                    yield line
        except httpx.HTTPError as exc:
            logger.exception("OpenRouter 串流 HTTP 連線失敗")
            raise OpenRouterError(502, str(exc)) from exc

    async def list_models(self, api_key: str) -> list[dict]:
        """GET /models — 回傳 data[]。同步流程拿任一把 active OR Key 即可。"""
        headers = {"Authorization": f"Bearer {api_key}"}
        try:
            resp = await self._client.get(
                f"{self._base_url}/models",
                headers=headers,
            )
        except httpx.HTTPError as exc:
            logger.exception("OpenRouter /models HTTP 連線失敗")
            raise OpenRouterError(502, str(exc)) from exc

        if resp.status_code == 401:
            raise OpenRouterAuthError(401, resp.text[:500])
        if resp.status_code == 403:
            raise OpenRouterForbiddenError(403, resp.text[:500])
        if resp.status_code == 429:
            raise OpenRouterRateLimitError(429, resp.text[:500])
        if resp.status_code >= 400:
            raise OpenRouterError(resp.status_code, resp.text[:500])

        try:
            body = resp.json()
        except Exception as exc:  # noqa: BLE001
            raise OpenRouterError(502, "invalid JSON response") from exc
        data = body.get("data")
        if not isinstance(data, list):
            raise OpenRouterError(502, "invalid /models response shape")
        return data

    async def get_key_info(self, api_key: str) -> dict:
        """GET /auth/key — 回傳 OpenRouter data,含 label / usage / limit / is_free_tier。"""
        headers = {"Authorization": f"Bearer {api_key}"}
        try:
            resp = await self._client.get(
                f"{self._base_url}/auth/key",
                headers=headers,
            )
        except httpx.HTTPError as exc:
            logger.exception("OpenRouter /auth/key HTTP 連線失敗")
            raise OpenRouterError(502, str(exc)) from exc

        if resp.status_code == 401:
            raise OpenRouterAuthError(401, resp.text[:500])
        if resp.status_code == 403:
            raise OpenRouterForbiddenError(403, resp.text[:500])
        if resp.status_code == 429:
            raise OpenRouterRateLimitError(429, resp.text[:500])
        if resp.status_code >= 400:
            raise OpenRouterError(resp.status_code, resp.text[:500])

        try:
            body = resp.json()
        except Exception as exc:  # noqa: BLE001
            raise OpenRouterError(502, "invalid JSON response") from exc
        data = body.get("data")
        if not isinstance(data, dict):
            raise OpenRouterError(502, "invalid /auth/key response shape")
        return data


_client_singleton: httpx.AsyncClient | None = None


async def get_openrouter_client():
    """FastAPI Dependency — 共用 httpx.AsyncClient 單例。"""
    global _client_singleton
    settings = get_settings()
    if _client_singleton is None:
        _client_singleton = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.OPENROUTER_API_TIMEOUT),
        )
    yield OpenRouterClient(_client_singleton, settings.OPENROUTER_API_BASE_URL)
