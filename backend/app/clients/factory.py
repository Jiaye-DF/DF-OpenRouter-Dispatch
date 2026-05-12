"""Chat Client Factory — 依 `provider` 取得對應 client。

對齊 docs/Tasks/v1.2/propose-v1.2.0.md § 6.3。
"""

from __future__ import annotations

from typing import Annotated, Union

from fastapi import Depends

from app.clients.internal.client import InternalClient, get_internal_client
from app.clients.openrouter.client import OpenRouterClient, get_openrouter_client


class ChatClientFactory:
    """`get(provider)` 對應到具體 client;呼叫端負責 lifecycle(由 FastAPI Depends 注入)。"""

    def __init__(
        self,
        openrouter: OpenRouterClient,
        internal: InternalClient | None,
    ) -> None:
        self._openrouter = openrouter
        self._internal = internal

    def openrouter(self) -> OpenRouterClient:
        return self._openrouter

    def internal(self) -> InternalClient | None:
        return self._internal


async def get_chat_client_factory(
    openrouter: Annotated[OpenRouterClient, Depends(get_openrouter_client)],
    internal: Annotated[Union[InternalClient, None], Depends(get_internal_client)],
) -> ChatClientFactory:
    return ChatClientFactory(openrouter=openrouter, internal=internal)
