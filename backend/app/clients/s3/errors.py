"""S3 client 錯誤類 + botocore 原生例外的轉換。

## why:為什麼只擷取安全欄位,不轉傳 botocore 原始訊息

botocore 的原生例外訊息**可能夾帶憑證片段**:S3 在 `SignatureDoesNotMatch` /
`InvalidAccessKeyId` 這類簽章錯誤的回應中會回吐 `AWSAccessKeyId`、`StringToSign`、
`SignatureProvided` 等欄位,`EndpointConnectionError` 則會把完整 URL(含 presigned
query string)放進訊息。

本專案目前**沒有** log 機密過濾層(`app/core/logging.py` 只有 request-id filter),
所有 log 會原樣送進 Seq。因此只要原始訊息被帶進我方錯誤類、又被上層 `logger.exception`
記下,就等同金鑰進 Seq —— 這正是本平台立案要解決的問題。

對策(本檔一律遵守):

1. 轉換時**只**擷取安全欄位:AWS 錯誤碼 / HTTP status / 操作名稱 / bucket / key /
   botocore 例外**類別名**。原始訊息(`str(exc)`)**任何情況下不取用**。
2. 一律 `raise ... from None`(見 `client.py`)切斷 `__cause__` 鏈 —— 若保留
   `from exc`,上層一旦 `logger.exception(...)`,traceback 仍會把 botocore 原始訊息
   整段印出,防線等於沒有。損失的除錯資訊由 `botocore_type` + `aws_code` 補回。
3. 錯誤訊息(`detail`,會進 API response)**不含** bucket / key;bucket / key 只放
   在屬性與 `safe_context()`,供結構化 log 使用(對齊
   `03-backend/05-exceptions-and-logging.md` § response 禁洩漏內部路徑)。
"""

from __future__ import annotations

from app.core.exceptions import AppError

# 物件層級的「不存在」:HeadObject 缺物件時 botocore 只回 code "404"(無 XML body),
# GetObject 則回 "NoSuchKey"。
_OBJECT_MISSING_CODES = frozenset({"NoSuchKey", "NotFound", "404"})

# bucket 不存在:HTTP status 同樣是 404,但語意是「設定錯」而非「物件缺」,
# 必須與物件層級區分,否則 head_object 會把 bucket 打錯誤判成「物件不存在」,
# 讓 531 遷移 Phase 2 全庫跳過卻無人察覺。
_BUCKET_MISSING_CODES = frozenset({"NoSuchBucket"})

# 憑證 / 權限類:一律不得把 key 內容帶進訊息(09-object-storage.md § 錯誤轉換契約)。
_PERMISSION_CODES = frozenset(
    {
        "AccessDenied",
        "403",
        "InvalidAccessKeyId",
        "SignatureDoesNotMatch",
        "ExpiredToken",
        "InvalidToken",
        "TokenRefreshRequired",
    }
)

# 逾時類 botocore 例外的類別名。why 用類別名而非 import:轉換層刻意不相依 botocore 的
# 例外階層(不同 botocore 版本階層有變動),只吃已知類別名,行為穩定且易測。
_TIMEOUT_TYPES = frozenset({"ConnectTimeoutError", "ReadTimeoutError", "ConnectionClosedError"})

# 憑證缺漏類 botocore 例外的類別名。
_CREDENTIAL_TYPES = frozenset({"NoCredentialsError", "PartialCredentialsError", "ProfileNotFound"})


class S3Error(AppError):
    """S3 操作錯誤基底。

    `botocore` / `boto3` 原生例外**禁**流到 service / api 層,一律於 client 內轉為本類
    或其子類(`90-third-party-service/00-overview.md` § 錯誤轉換契約)。
    """

    def __init__(
        self,
        detail: str,
        *,
        operation: str = "",
        bucket: str = "",
        key: str = "",
        aws_code: str = "",
        http_status: int | None = None,
        botocore_type: str = "",
        code: int = 502,
    ) -> None:
        super().__init__(detail, code=code)
        self.operation = operation
        self.bucket = bucket
        self.key = key
        self.aws_code = aws_code
        self.http_status = http_status
        self.botocore_type = botocore_type

    def safe_context(self) -> dict[str, str | int | None]:
        """可安全寫入 log 的欄位集合。

        僅含錯誤碼 / status / 操作 / bucket / key / botocore 類別名;
        **不含**憑證、簽章、presigned URL 與物件內容。
        """
        return {
            "operation": self.operation,
            "bucket": self.bucket,
            "key": self.key,
            "aws_code": self.aws_code,
            "http_status": self.http_status,
            "botocore_type": self.botocore_type,
        }


class S3ConfigError(S3Error):
    """S3 設定缺漏 / 憑證未注入(呼叫前置條件未滿足,非第三方故障)。"""


class S3NotFoundError(S3Error):
    """bucket 或物件不存在(`NoSuchKey` / `404` / `NoSuchBucket`)。"""


class S3UploadError(S3Error):
    """S3 操作失敗(權限 / 連線 / 未預期的 `ClientError`)。

    上層(524)對本類採 best-effort:記 `upload_failed` + 結構化 log,**不擋**主請求。
    """


class S3TimeoutError(S3UploadError):
    """S3 連線 / 讀取逾時。

    why 繼承 `S3UploadError`:`09-object-storage.md` 要求逾時有專屬錯誤類別,
    而 task-523 錯誤對照表要求逾時對上層等同「操作失敗」語意。以繼承同時滿足兩者 ——
    需要細分時 `except S3TimeoutError`,只要 best-effort 時 `except S3UploadError` 即涵蓋。
    """


def is_missing_object(err: S3Error) -> bool:
    """判斷錯誤是否為「物件層級不存在」(可安全視為 not found)。

    bucket 不存在雖然 HTTP status 同為 404,但屬設定錯,**必須**回 False 讓錯誤往上拋。
    """
    if err.aws_code in _BUCKET_MISSING_CODES:
        return False
    return err.aws_code in _OBJECT_MISSING_CODES or err.http_status == 404


def _extract_safe_fields(exc: BaseException) -> tuple[str, int | None]:
    """從 `ClientError` 取出 (AWS 錯誤碼, HTTP status)。

    只讀 `response` 內的 `Error.Code` 與 `ResponseMetadata.HTTPStatusCode` 兩欄;
    **刻意不讀** `Error.Message` / `Error.AWSAccessKeyId` / `Error.StringToSign`
    等可能夾帶憑證或簽章的欄位。
    """
    response = getattr(exc, "response", None)
    if not isinstance(response, dict):
        return "", None

    aws_code = ""
    error_block = response.get("Error")
    if isinstance(error_block, dict):
        raw_code = error_block.get("Code")
        aws_code = str(raw_code) if raw_code is not None else ""

    http_status: int | None = None
    metadata = response.get("ResponseMetadata")
    if isinstance(metadata, dict):
        raw_status = metadata.get("HTTPStatusCode")
        if isinstance(raw_status, int):
            http_status = raw_status

    return aws_code, http_status


def map_botocore_error(
    exc: BaseException,
    *,
    operation: str,
    bucket: str,
    key: str,
) -> S3Error:
    """把 botocore 原生例外轉成我方 `S3Error` 子類。

    回傳(而非直接 raise)例外物件,讓呼叫端能在 `raise ... from None` 之前先記結構化 log。

    Args:
        exc: botocore 原生例外(`ClientError` 或 `BotoCoreError` 子類)。
        operation: 我方操作名稱(如 `put_object`),供 log 定位。
        bucket: 目標 bucket。
        key: 目標物件 key。

    Returns:
        對應的 `S3Error` 子類;訊息只含操作名稱與 AWS 錯誤碼,**不含**原始例外訊息。
    """
    botocore_type = type(exc).__name__
    aws_code, http_status = _extract_safe_fields(exc)

    def build(cls: type[S3Error], detail: str, *, code: int = 502) -> S3Error:
        return cls(
            detail,
            operation=operation,
            bucket=bucket,
            key=key,
            aws_code=aws_code,
            http_status=http_status,
            botocore_type=botocore_type,
            code=code,
        )

    if botocore_type in _TIMEOUT_TYPES:
        return build(S3TimeoutError, f"S3 {operation} 逾時")

    if botocore_type in _CREDENTIAL_TYPES:
        return build(S3ConfigError, f"S3 憑證未正確注入:{botocore_type}", code=500)

    if aws_code:
        if aws_code in _BUCKET_MISSING_CODES:
            return build(S3NotFoundError, f"S3 bucket 不存在:{aws_code}")
        if aws_code in _OBJECT_MISSING_CODES:
            return build(S3NotFoundError, f"S3 物件不存在:{aws_code}")
        if aws_code in _PERMISSION_CODES:
            # 權限類:訊息只留錯誤碼,禁帶 key / 憑證內容。
            return build(S3UploadError, f"S3 {operation} 權限不足:{aws_code}")
        return build(S3UploadError, f"S3 {operation} 失敗:{aws_code}")

    if http_status == 404:
        return build(S3NotFoundError, f"S3 物件不存在:{operation}")

    # 其餘 BotoCoreError(EndpointConnectionError / SSLError / 未預期)→ 基底 S3Error。
    return build(S3Error, f"S3 {operation} 失敗:{botocore_type}")
