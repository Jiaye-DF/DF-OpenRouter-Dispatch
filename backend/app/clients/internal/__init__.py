"""Internal LLM client(企業內地端 OpenAI-compatible server)。

對齊 docs/Tasks/v1.2/propose-v1.2.0.md § 7 / § 8。
"""

from app.clients.internal.client import (
    InternalAuthError,
    InternalClient,
    InternalError,
    InternalRateLimitError,
    InternalUnavailableError,
    get_internal_httpx_client,
)

__all__ = [
    "InternalAuthError",
    "InternalClient",
    "InternalError",
    "InternalRateLimitError",
    "InternalUnavailableError",
    "get_internal_httpx_client",
]
