"""Chat Client Factory(v1.2)。

對齊 docs/Tasks/v1.2/propose-v1.2.0.md § 6.3。

- `openrouter`:回 OpenRouter client(httpx 單例)
- `internal`:回 internal httpx.AsyncClient,由 proxy.py 用 (base_url, api_key) 逐次構造 InternalClient
"""

from __future__ import annotations

from typing import Annotated

import httpx
from fastapi import Depends

from app.clients.internal.client import get_internal_httpx_client
from app.clients.openrouter.client import OpenRouterClient, get_openrouter_client


class ChatClientFactory:
    def __init__(
        self,
        openrouter: OpenRouterClient,
        internal_httpx: httpx.AsyncClient,
    ) -> None:
        self._openrouter = openrouter
        self._internal_httpx = internal_httpx

    def openrouter(self) -> OpenRouterClient:
        return self._openrouter

    def internal_httpx(self) -> httpx.AsyncClient:
        """供 proxy.py 用來構造每把 Key 的 InternalClient。"""
        return self._internal_httpx


async def get_chat_client_factory(
    openrouter: Annotated[OpenRouterClient, Depends(get_openrouter_client)],
    internal_httpx: Annotated[httpx.AsyncClient, Depends(get_internal_httpx_client)],
) -> ChatClientFactory:
    return ChatClientFactory(openrouter=openrouter, internal_httpx=internal_httpx)
