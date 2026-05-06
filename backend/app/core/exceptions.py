from typing import Any


class AppError(Exception):
    """統一業務例外;由 exception_handler 轉為 ApiResponse 失敗回應。

    `data` 用於回傳結構化錯誤 payload(例如 sync_throttled 的 retry_after_seconds、
    tier_in_use 的 using_models 列表),前端可直接 `error.data.<field>` 解析。
    """

    def __init__(
        self,
        detail: str,
        code: int = 400,
        data: Any | None = None,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.code = code
        self.data = data
