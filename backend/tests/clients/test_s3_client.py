"""S3 client 單元測試 — 全程走 `botocore.stub.Stubber` / monkeypatch,不打真 AWS。"""

from __future__ import annotations

import asyncio
import io
from collections.abc import Callable, Coroutine
from typing import TypeVar

import pytest
from botocore.exceptions import ConnectTimeoutError, ReadTimeoutError
from botocore.response import StreamingBody
from botocore.stub import Stubber

from app.clients.s3 import (
    S3Client,
    S3ConfigError,
    S3Error,
    S3NotFoundError,
    S3TimeoutError,
    S3UploadError,
    map_botocore_error,
)
from app.clients.s3 import client as s3_client_module

_BUCKET = "unit-test-bucket"
_KEY = "test/usage-log/01J/9f2ca1.png"

T = TypeVar("T")


def make_client() -> S3Client:
    """建立指向假 bucket 的 client;憑證為明顯的測試字串,不對應任何真實帳號。"""
    return S3Client(
        bucket=_BUCKET,
        region="ap-northeast-1",
        access_key_id="AKIAUNITTESTKEY00000",
        secret_access_key="unit-test-secret-not-a-real-credential",
    )


class _FakeClientError(Exception):
    """模擬 `botocore` 的 `ClientError`:錯誤細節放在 `response`,訊息夾帶憑證片段。

    專用於驗證錯誤轉換層**不會**把原始訊息或 `AWSAccessKeyId` / `StringToSign` 帶出去。
    """

    def __init__(self, response: dict[str, object]) -> None:
        super().__init__("An error occurred: AKIALEAKEDKEY0000000 / StringToSign=LEAKED")
        self.response = response


# --- 四項能力 ---


async def test_put_object_success() -> None:
    client = make_client()
    with Stubber(client._s3) as stub:
        stub.add_response(
            "put_object",
            {"ETag": '"deadbeef"'},
            {
                "Bucket": _BUCKET,
                "Key": _KEY,
                "Body": b"binary-content",
                "ContentType": "image/png",
                "ServerSideEncryption": "AES256",
            },
        )
        await client.put_object(_KEY, b"binary-content", "image/png")
        stub.assert_no_pending_responses()


async def test_delete_object_success() -> None:
    client = make_client()
    with Stubber(client._s3) as stub:
        stub.add_response("delete_object", {}, {"Bucket": _BUCKET, "Key": _KEY})
        await client.delete_object(_KEY)
        stub.assert_no_pending_responses()


async def test_head_object_returns_true_when_exists() -> None:
    client = make_client()
    with Stubber(client._s3) as stub:
        stub.add_response(
            "head_object",
            {"ContentLength": 12, "ContentType": "image/png"},
            {"Bucket": _BUCKET, "Key": _KEY},
        )
        assert await client.head_object(_KEY) is True
        stub.assert_no_pending_responses()


def _streaming(data: bytes) -> StreamingBody:
    """包成 boto3 實際回傳的 `StreamingBody`(直接塞 bytes 無法 `.read()`)。"""
    return StreamingBody(io.BytesIO(data), len(data))


async def test_get_object_success_returns_body_and_content_type() -> None:
    client = make_client()
    payload = b"\x89PNG\r\n\x1a\nfake-image-bytes"
    with Stubber(client._s3) as stub:
        stub.add_response(
            "get_object",
            {"Body": _streaming(payload), "ContentType": "image/png"},
            {"Bucket": _BUCKET, "Key": _KEY},
        )
        body, content_type = await client.get_object(_KEY)
        stub.assert_no_pending_responses()
    assert body == payload
    assert content_type == "image/png"


async def test_get_object_without_content_type_returns_empty_string() -> None:
    """S3 未回 ContentType 時回空字串:client 不猜 MIME,由呼叫端決定 fallback。"""
    client = make_client()
    with Stubber(client._s3) as stub:
        stub.add_response(
            "get_object", {"Body": _streaming(b"x")}, {"Bucket": _BUCKET, "Key": _KEY}
        )
        body, content_type = await client.get_object(_KEY)
    assert body == b"x"
    assert content_type == ""


async def test_get_object_no_such_key_raises_not_found() -> None:
    """與 `head_object` 不同:`get_object` 對物件不存在一律拋 `S3NotFoundError`。"""
    client = make_client()
    with Stubber(client._s3) as stub:
        stub.add_client_error(
            "get_object",
            service_error_code="NoSuchKey",
            service_message="The specified key does not exist.",
            http_status_code=404,
        )
        with pytest.raises(S3NotFoundError) as excinfo:
            await client.get_object(_KEY)
    assert excinfo.value.aws_code == "NoSuchKey"


async def test_get_object_403_maps_to_upload_error() -> None:
    client = make_client()
    with Stubber(client._s3) as stub:
        stub.add_client_error(
            "get_object",
            service_error_code="AccessDenied",
            http_status_code=403,
        )
        with pytest.raises(S3UploadError) as excinfo:
            await client.get_object(_KEY)
    assert excinfo.value.aws_code == "AccessDenied"
    # botocore 原始訊息不得外洩(權限類錯誤的 response 常夾帶簽章欄位)。
    assert _KEY not in excinfo.value.detail


@pytest.mark.parametrize(
    "exc",
    [
        ReadTimeoutError(endpoint_url="https://example.invalid/"),
        ConnectTimeoutError(endpoint_url="https://example.invalid/"),
    ],
)
async def test_get_object_timeout_maps_to_timeout_error(
    exc: BaseException, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = make_client()

    def _raise(**_kwargs: object) -> None:
        raise exc

    monkeypatch.setattr(client._s3, "get_object", _raise)
    with pytest.raises(S3TimeoutError):
        await client.get_object(_KEY)


async def test_get_object_timeout_while_reading_body_is_mapped() -> None:
    """`Body.read()` 才真正拉資料 —— 讀取階段的逾時同樣要轉型,不可漏接。"""

    class _ExplodingBody:
        def read(self) -> bytes:
            raise ReadTimeoutError(endpoint_url="https://example.invalid/")

    client = make_client()
    with Stubber(client._s3) as stub:
        stub.add_response(
            "get_object",
            {"Body": _ExplodingBody(), "ContentType": "image/png"},
            {"Bucket": _BUCKET, "Key": _KEY},
        )
        with pytest.raises(S3TimeoutError):
            await client.get_object(_KEY)


async def test_get_object_rejects_invalid_key() -> None:
    client = make_client()
    with pytest.raises(S3Error):
        await client.get_object("dev/../../etc/passwd")


async def test_presign_get_returns_url_with_ttl_and_target() -> None:
    """只斷言「有 TTL 參數 + 指向正確 bucket/key」,不斷言完整簽章(會隨時間變動)。"""
    client = make_client()
    url = await client.presign_get(_KEY, 900)
    assert _BUCKET in url
    assert "test/usage-log/01J/9f2ca1.png" in url
    assert "X-Amz-Expires=900" in url
    assert "X-Amz-Signature=" in url


# --- 錯誤轉換:403 / 逾時 → S3UploadError ---


async def test_put_object_403_maps_to_upload_error() -> None:
    client = make_client()
    with Stubber(client._s3) as stub:
        stub.add_client_error(
            "put_object",
            service_error_code="AccessDenied",
            service_message="Access Denied",
            http_status_code=403,
        )
        with pytest.raises(S3UploadError) as excinfo:
            await client.put_object(_KEY, b"x", "image/png")
    err = excinfo.value
    assert err.aws_code == "AccessDenied"
    assert err.http_status == 403


async def test_put_object_no_such_bucket_maps_to_not_found() -> None:
    """bucket 不存在:Design-Base 對照表歸 `S3NotFoundError`,仍是 `S3Error` 子類。

    task-523 對照表標 `S3UploadError`;依規範優先序(Design-Base > Tasks)採前者,
    對 524 的行為一致(catch `S3Error` → 記 `upload_failed`,不擋請求)。
    """
    client = make_client()
    with Stubber(client._s3) as stub:
        stub.add_client_error(
            "put_object",
            service_error_code="NoSuchBucket",
            http_status_code=404,
        )
        with pytest.raises(S3NotFoundError):
            await client.put_object(_KEY, b"x", "image/png")


@pytest.mark.parametrize(
    "exc",
    [
        ReadTimeoutError(endpoint_url="https://example.invalid/"),
        ConnectTimeoutError(endpoint_url="https://example.invalid/"),
    ],
)
async def test_timeout_maps_to_timeout_error_which_is_upload_error(
    exc: BaseException, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = make_client()

    def _raise(**_kwargs: object) -> None:
        raise exc

    monkeypatch.setattr(client._s3, "put_object", _raise)
    with pytest.raises(S3TimeoutError) as excinfo:
        await client.put_object(_KEY, b"x", "image/png")
    # S3TimeoutError 繼承 S3UploadError:上層 best-effort 只 catch S3UploadError 即涵蓋逾時。
    assert isinstance(excinfo.value, S3UploadError)


def test_timeout_error_is_subclass_of_upload_error() -> None:
    assert issubclass(S3TimeoutError, S3UploadError)
    assert issubclass(S3UploadError, S3Error)


# --- head_object 對 404 回 False、對 bucket 不存在照拋 ---


async def test_head_object_returns_false_on_404() -> None:
    client = make_client()
    with Stubber(client._s3) as stub:
        stub.add_client_error(
            "head_object",
            service_error_code="404",
            service_message="Not Found",
            http_status_code=404,
        )
        assert await client.head_object(_KEY) is False


async def test_head_object_returns_false_on_no_such_key() -> None:
    client = make_client()
    with Stubber(client._s3) as stub:
        stub.add_client_error(
            "head_object",
            service_error_code="NoSuchKey",
            http_status_code=404,
        )
        assert await client.head_object(_KEY) is False


async def test_head_object_raises_when_bucket_missing() -> None:
    """bucket 打錯不可偽裝成「物件不存在」,否則 531 會靜默跳過全庫。"""
    client = make_client()
    with Stubber(client._s3) as stub:
        stub.add_client_error(
            "head_object",
            service_error_code="NoSuchBucket",
            http_status_code=404,
        )
        with pytest.raises(S3NotFoundError):
            await client.head_object(_KEY)


async def test_head_object_403_still_raises() -> None:
    client = make_client()
    with Stubber(client._s3) as stub:
        stub.add_client_error(
            "head_object",
            service_error_code="AccessDenied",
            http_status_code=403,
        )
        with pytest.raises(S3UploadError):
            await client.head_object(_KEY)


# --- 無阻塞:所有 boto3 呼叫皆經 asyncio.to_thread ---


async def test_all_capabilities_go_through_to_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client()
    calls: list[str] = []
    real_to_thread = asyncio.to_thread

    def spy(
        fn: Callable[..., T], /, *args: object, **kwargs: object
    ) -> Coroutine[object, object, T]:
        calls.append(getattr(fn, "__name__", repr(fn)))
        return real_to_thread(fn, *args, **kwargs)

    monkeypatch.setattr(s3_client_module.asyncio, "to_thread", spy)

    with Stubber(client._s3) as stub:
        stub.add_response(
            "put_object",
            {},
            {
                "Bucket": _BUCKET,
                "Key": _KEY,
                "Body": b"x",
                "ContentType": "image/png",
                "ServerSideEncryption": "AES256",
            },
        )
        stub.add_response(
            "get_object", {"Body": _streaming(b"x")}, {"Bucket": _BUCKET, "Key": _KEY}
        )
        stub.add_response("delete_object", {}, {"Bucket": _BUCKET, "Key": _KEY})
        stub.add_response("head_object", {"ContentLength": 1}, {"Bucket": _BUCKET, "Key": _KEY})

        await client.put_object(_KEY, b"x", "image/png")
        await client.get_object(_KEY)
        await client.presign_get(_KEY, 900)
        await client.delete_object(_KEY)
        await client.head_object(_KEY)

    assert calls == [
        "_put_object_sync",
        "_get_object_sync",
        "_presign_get_sync",
        "_delete_object_sync",
        "_head_object_sync",
    ]


def test_timeout_and_retry_config_has_hard_ceiling() -> None:
    client = make_client()
    config = client._s3.meta.config
    assert config.connect_timeout == 3.0
    assert config.read_timeout == 10.0
    # botocore 把 Config 的 max_attempts(重試次數)換算為 total_max_attempts = N + 1,
    # 故此處為 2:首次 + 最多 1 次重試。
    assert config.retries["total_max_attempts"] == 2
    assert config.retries["mode"] == "standard"


# --- 機密不外洩 ---


def test_mapped_error_drops_botocore_message_and_credentials() -> None:
    """轉換後的錯誤不得帶原始訊息、AWSAccessKeyId 或 StringToSign。"""
    exc = _FakeClientError(
        {
            "Error": {
                "Code": "SignatureDoesNotMatch",
                "Message": "The request signature we calculated does not match...",
                "AWSAccessKeyId": "AKIALEAKEDKEY0000000",
                "StringToSign": "AWS4-HMAC-SHA256\nLEAKED-STRING-TO-SIGN",
                "SignatureProvided": "leaked-signature",
            },
            "ResponseMetadata": {"HTTPStatusCode": 403},
        }
    )
    err = map_botocore_error(exc, operation="put_object", bucket=_BUCKET, key=_KEY)

    leaked_tokens = (
        "AKIALEAKEDKEY0000000",
        "LEAKED-STRING-TO-SIGN",
        "leaked-signature",
        "does not match",
    )
    surfaces = [err.detail, str(err), repr(err.safe_context())]
    for surface in surfaces:
        for token in leaked_tokens:
            assert token not in surface

    assert isinstance(err, S3UploadError)
    assert err.aws_code == "SignatureDoesNotMatch"
    assert err.http_status == 403
    assert err.safe_context()["botocore_type"] == "_FakeClientError"


def test_error_detail_excludes_bucket_and_key() -> None:
    """detail 會進 API response,禁洩漏內部路徑;bucket / key 只留在屬性供 log 用。"""
    exc = _FakeClientError(
        {
            "Error": {"Code": "AccessDenied"},
            "ResponseMetadata": {"HTTPStatusCode": 403},
        }
    )
    err = map_botocore_error(exc, operation="put_object", bucket=_BUCKET, key=_KEY)
    assert _BUCKET not in err.detail
    assert _KEY not in err.detail
    assert err.bucket == _BUCKET
    assert err.key == _KEY


async def test_raised_error_has_no_cause_chain() -> None:
    """`raise ... from None`:切斷 __cause__,避免上層 logger.exception 印出 botocore 訊息。"""
    client = make_client()
    with Stubber(client._s3) as stub:
        stub.add_client_error(
            "put_object",
            service_error_code="AccessDenied",
            service_message="Access Denied by policy",
            http_status_code=403,
        )
        with pytest.raises(S3UploadError) as excinfo:
            await client.put_object(_KEY, b"x", "image/png")
    assert excinfo.value.__cause__ is None
    assert excinfo.value.__suppress_context__ is True


# --- key 驗證 / ttl 驗證 / 設定把關 ---


@pytest.mark.parametrize(
    "bad_key",
    ["", "/leading-slash.png", "dev/../../etc/passwd", "dev/bad\x00key.png", "a" * 1025],
)
async def test_invalid_key_rejected(bad_key: str) -> None:
    client = make_client()
    with pytest.raises(S3Error):
        await client.put_object(bad_key, b"x", "image/png")


@pytest.mark.parametrize("bad_ttl", [0, -1, 7 * 24 * 60 * 60 + 1])
async def test_presign_rejects_out_of_range_ttl(bad_ttl: int) -> None:
    client = make_client()
    with pytest.raises(S3Error):
        await client.presign_get(_KEY, bad_ttl)


def test_client_requires_bucket() -> None:
    with pytest.raises(S3ConfigError):
        S3Client(bucket="   ", region="ap-northeast-1")


def test_get_s3_client_raises_when_storage_disabled() -> None:
    """S3_STORAGE_ENABLED 預設 false(測試環境未開),未開通即取用視為呼叫端錯誤。"""
    s3_client_module.reset_s3_client()
    with pytest.raises(S3ConfigError):
        s3_client_module.get_s3_client()
