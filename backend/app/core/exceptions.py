class AppError(Exception):
    """統一業務例外；由 exception_handler 轉為 ApiResponse 失敗回應。"""

    def __init__(self, detail: str, code: int = 400) -> None:
        super().__init__(detail)
        self.detail = detail
        self.code = code
