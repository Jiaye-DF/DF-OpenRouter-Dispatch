"""S3 物件儲存 client(boto3)。

`boto3` 為**同步** SDK。本專案跑單 worker(`UVICORN_WORKERS=1`),在 async 函式內裸呼叫
會卡住 event loop 上的**所有**請求,因此五項能力一律以 `asyncio.to_thread` 包裹
(對齊 `03-backend/03-async-and-tx.md` / `03-backend/08-performance.md`)。

`generate_presigned_url` 雖為本地簽章計算(不打網路),仍一併包裹,讓「本檔所有 boto3
呼叫皆在 `to_thread` 內」成為可機械驗證的單一規則,不留例外給後續維護者誤判。

timeout / retry 採**秒級 timeout + 總嘗試 2 次**:上傳失敗屬 best-effort(不擋主請求),
但**會拖延遲** —— boto3 預設 legacy retry mode 最多重試 5 次,疊上長 timeout 足以拖垮
單 worker 的 thread pool,因此必須有硬上限(`09-object-storage.md` § 同步 SDK 的 async 規則)。
"""

from __future__ import annotations

import asyncio
import logging

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.clients.s3.errors import (
    S3ConfigError,
    S3Error,
    S3NotFoundError,
    is_missing_object,
    map_botocore_error,
)
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# --- timeout / retry 硬上限(禁沿用 boto3 預設)---
_CONNECT_TIMEOUT_SECONDS = 3.0
_READ_TIMEOUT_SECONDS = 10.0
# ⚠ botocore quirk:`Config(retries={"max_attempts": N})` 的 N 是「**重試**次數」,
# 內部換算為 `total_max_attempts = N + 1`。故 1 = 首次 + 最多 1 次重試 = 總嘗試 2 次,
# 對齊 task-523「重試 ≤ 1 次」與 01-client-design.md「attempts ≤ 3」。
_MAX_ATTEMPTS = 1

# S3 物件 key 上限為 1024 bytes(UTF-8 編碼後)。
_MAX_KEY_BYTES = 1024

# SigV4 + 長期 IAM 憑證下 presigned URL 的硬上限為 7 天;本專案實務值取分鐘級。
_MAX_PRESIGN_TTL_SECONDS = 7 * 24 * 60 * 60


def _ensure_valid_key(key: str, *, operation: str) -> str:
    """驗證物件 key(對齊 `09-object-storage.md` § 物件 key 規則)。

    key 由上層(524 / 530)組出,但驗證放在 client 這個唯一出入口,確保任何呼叫路徑
    都擋得住路徑穿越與控制字元 —— 少一個地方驗,防線就等於沒有。
    """
    if not key:
        raise S3Error("S3 物件 key 不可為空", operation=operation, code=500)
    if key.startswith("/"):
        raise S3Error("S3 物件 key 禁含前導 /", operation=operation, code=500)
    if ".." in key:
        raise S3Error("S3 物件 key 禁含 ..", operation=operation, code=500)
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in key):
        raise S3Error("S3 物件 key 禁含控制字元", operation=operation, code=500)
    if len(key.encode("utf-8")) > _MAX_KEY_BYTES:
        raise S3Error(
            f"S3 物件 key 超過 {_MAX_KEY_BYTES} bytes 上限", operation=operation, code=500
        )
    return key


class S3Client:
    """S3 物件儲存 client — 上傳 / 下載 / 簽發短期讀取 URL / 刪除 / 存在檢查。

    boto3 的 `client` 物件為 thread-safe(`resource` 不是),可安全在多個
    `asyncio.to_thread` 執行緒間共用;建 client 有 metadata 載入成本,故以單例重用
    (見本檔 `get_s3_client`)。
    """

    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        access_key_id: str = "",
        secret_access_key: str = "",
        connect_timeout: float = _CONNECT_TIMEOUT_SECONDS,
        read_timeout: float = _READ_TIMEOUT_SECONDS,
        max_attempts: int = _MAX_ATTEMPTS,
    ) -> None:
        if not bucket.strip():
            raise S3ConfigError("S3_BUCKET 未設定", operation="init", code=500)

        self._bucket = bucket.strip()
        # 憑證留空 → 交回 boto3 預設 credential chain(IAM role / ~/.aws);
        # 明確傳空字串會被當成「空憑證」而簽出必然失敗的請求。
        self._s3 = boto3.client(
            "s3",
            region_name=region or None,
            aws_access_key_id=access_key_id or None,
            aws_secret_access_key=secret_access_key or None,
            config=Config(
                connect_timeout=connect_timeout,
                read_timeout=read_timeout,
                retries={"max_attempts": max_attempts, "mode": "standard"},
                signature_version="s3v4",
            ),
        )

    @property
    def bucket(self) -> str:
        return self._bucket

    # --- 五項能力(對外皆為 async,boto3 呼叫全在 to_thread 內)---

    async def put_object(self, key: str, body: bytes, content_type: str) -> None:
        """上傳物件。

        Args:
            key: 物件 key(由上層組出的 deterministic key)。
            body: 物件內容(bytes)。
            content_type: MIME type(由 MIME 白名單推導,禁取自使用者輸入)。

        Raises:
            S3TimeoutError: 連線 / 讀取逾時。
            S3UploadError: 權限不足 / bucket 設定錯 / 其他 `ClientError`。
            S3Error: 其他未預期的 botocore 錯誤,或 key 不合法。
        """
        safe_key = _ensure_valid_key(key, operation="put_object")
        await asyncio.to_thread(self._put_object_sync, safe_key, body, content_type)

    async def get_object(self, key: str) -> tuple[bytes, str]:
        """下載物件內容。

        用於後端**自行取回內容**的場景(如 AI 重跑把 S3 圖片重新 inline 成 base64 送下游),
        避免動用 presigned URL —— 後者視同臨時憑證,禁送第三方 / 下游模型
        (`09-object-storage.md` § presigned URL)。

        Args:
            key: 物件 key。

        Returns:
            `(內容 bytes, Content-Type)`。S3 未回 `ContentType` 時第二元素為空字串;
            本 client **不猜** MIME,由呼叫端決定 fallback。

        Raises:
            S3NotFoundError: 物件或 bucket 不存在。**與 `head_object` 不同**:本方法對
                「物件不存在」一律拋出而非回 None —— 呼叫端多為 best-effort 下載,
                `except S3Error` 一句即涵蓋所有失敗路徑,無需再分辨回傳值。
            S3TimeoutError: 連線 / 讀取逾時。
            S3UploadError: 權限不足 / 其他 `ClientError`。
            S3Error: 其他未預期的 botocore 錯誤,或 key 不合法。
        """
        safe_key = _ensure_valid_key(key, operation="get_object")
        return await asyncio.to_thread(self._get_object_sync, safe_key)

    async def presign_get(self, key: str, ttl: int) -> str:
        """簽發短期唯讀 URL。

        presigned URL 視同**臨時憑證**:禁寫入 log、禁存 DB、禁送下游模型;
        每次讀取都重新簽發,不快取(`09-object-storage.md` § presigned URL)。

        Args:
            key: 物件 key。
            ttl: 有效秒數(取 `S3_PRESIGN_TTL_SECONDS`,分鐘級)。

        Returns:
            可直接給已認證管理端使用者開啟的 URL。

        Raises:
            S3Error: ttl 超出合法範圍,或 key 不合法。
        """
        safe_key = _ensure_valid_key(key, operation="presign_get")
        if ttl <= 0 or ttl > _MAX_PRESIGN_TTL_SECONDS:
            raise S3Error(
                f"presign ttl 須介於 1 ~ {_MAX_PRESIGN_TTL_SECONDS} 秒",
                operation="presign_get",
                code=500,
            )
        url = await asyncio.to_thread(self._presign_get_sync, safe_key, ttl)
        return url

    async def delete_object(self, key: str) -> None:
        """刪除物件(S3 的 DeleteObject 對不存在的 key 亦回 204,天然冪等)。

        Raises:
            S3TimeoutError / S3UploadError / S3Error: 同 `put_object`。
        """
        safe_key = _ensure_valid_key(key, operation="delete_object")
        await asyncio.to_thread(self._delete_object_sync, safe_key)

    async def head_object(self, key: str) -> bool:
        """存在檢查(530 / 531 的冪等與安全網)。

        Returns:
            物件存在為 True;**物件層級**不存在回 False(不拋)。

        Raises:
            S3NotFoundError: bucket 不存在 —— 屬設定錯,不可與「物件不存在」混為一談,
                否則 bucket 打錯時全庫檢查都回 False 卻無人察覺。
            S3TimeoutError / S3UploadError / S3Error: 其他失敗照常拋出。
        """
        safe_key = _ensure_valid_key(key, operation="head_object")
        try:
            await asyncio.to_thread(self._head_object_sync, safe_key)
        except S3NotFoundError as err:
            if is_missing_object(err):
                return False
            raise
        return True

    # --- 同步實作(僅由上方 to_thread 呼叫,禁在 async 函式內直接呼叫)---

    def _put_object_sync(self, key: str, body: bytes, content_type: str) -> None:
        try:
            self._s3.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=body,
                ContentType=content_type,
                # bucket 未設預設加密時仍保證靜態加密(09-object-storage.md § 存取權)。
                ServerSideEncryption="AES256",
            )
        except (BotoCoreError, ClientError) as exc:
            raise self._to_app_error(exc, operation="put_object", key=key) from None

    def _get_object_sync(self, key: str) -> tuple[bytes, str]:
        try:
            resp = self._s3.get_object(Bucket=self._bucket, Key=key)
            # `Body` 為 StreamingBody:讀取才真正拉資料,故 read() 一併納入 try
            # (逾時 / 連線中斷會在此拋出,不能漏接)。
            body: bytes = resp["Body"].read()
        except (BotoCoreError, ClientError) as exc:
            raise self._to_app_error(exc, operation="get_object", key=key) from None
        content_type = resp.get("ContentType") or ""
        return body, str(content_type)

    def _presign_get_sync(self, key: str, ttl: int) -> str:
        try:
            url = self._s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=ttl,
            )
        except (BotoCoreError, ClientError) as exc:
            raise self._to_app_error(exc, operation="presign_get", key=key) from None
        return str(url)

    def _delete_object_sync(self, key: str) -> None:
        try:
            self._s3.delete_object(Bucket=self._bucket, Key=key)
        except (BotoCoreError, ClientError) as exc:
            raise self._to_app_error(exc, operation="delete_object", key=key) from None

    def _head_object_sync(self, key: str) -> None:
        try:
            self._s3.head_object(Bucket=self._bucket, Key=key)
        except (BotoCoreError, ClientError) as exc:
            raise self._to_app_error(exc, operation="head_object", key=key) from None

    def _to_app_error(self, exc: BaseException, *, operation: str, key: str) -> S3Error:
        """轉錯誤 + 記結構化 log。

        log **只**寫 `safe_context()`(操作 / bucket / key / 錯誤碼 / status / 例外類別名),
        且刻意不帶 `exc_info` —— botocore 原始訊息可能夾帶憑證或簽章,本專案 log 無機密
        過濾層,traceback 一旦進 Seq 就等同金鑰外洩(詳見 `errors.py` 檔頭)。
        """
        err = map_botocore_error(exc, operation=operation, bucket=self._bucket, key=key)
        # head_object 查無物件是預期路徑(遷移腳本每列都會遇到),壓成 debug 免洗版 log。
        level = (
            logging.DEBUG
            if operation == "head_object" and is_missing_object(err)
            else logging.WARNING
        )
        logger.log(
            level,
            "S3 操作失敗 operation=%s bucket=%s key=%s aws_code=%s http_status=%s botocore_type=%s",
            err.operation,
            err.bucket,
            err.key,
            err.aws_code,
            err.http_status,
            err.botocore_type,
        )
        return err


_client_singleton: S3Client | None = None


def get_s3_client() -> S3Client:
    """取得共用的 `S3Client` 單例。

    boto3 建 client 有 metadata 載入成本,且 `client` 物件 thread-safe,故全程重用。

    Raises:
        S3ConfigError: `S3_STORAGE_ENABLED=false`(未開通即呼叫屬呼叫端錯誤)
            或 bucket 未設定。
    """
    global _client_singleton
    settings = get_settings()
    if not settings.S3_STORAGE_ENABLED:
        raise S3ConfigError("S3_STORAGE_ENABLED=false,未啟用物件儲存", operation="init", code=500)
    if _client_singleton is None:
        _client_singleton = S3Client(
            bucket=settings.S3_BUCKET,
            region=settings.AWS_REGION,
            access_key_id=settings.AWS_ACCESS_KEY_ID,
            secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
    return _client_singleton


def reset_s3_client() -> None:
    """清掉單例(測試用;正式流程不呼叫)。"""
    global _client_singleton
    _client_singleton = None
