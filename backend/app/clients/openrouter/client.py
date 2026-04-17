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
