class OpenRouterError(Exception):
    def __init__(self, status: int, detail: str = "") -> None:
        super().__init__(f"OpenRouter error {status}: {detail}")
        self.status = status
        self.detail = detail


class OpenRouterAuthError(OpenRouterError):
    """401 — Key 失效，應換下一把。"""


class OpenRouterForbiddenError(OpenRouterError):
    """403 — 模型不可用。"""


class OpenRouterModelNotFoundError(OpenRouterError):
    """404 — 模型不存在。"""


class OpenRouterRateLimitError(OpenRouterError):
    """429 — Rate limit。"""
