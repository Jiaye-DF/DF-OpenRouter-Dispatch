"""附件落地層(v2.2.1 / task-524)。

把「請求中的 base64 附件 → S3 物件路徑」收斂成單一、可獨立測試的模組,不讓 S3 細節
擴散進 `proxy.py`(propose v2.2.1 §B.2)。

## 三條不可妥協的性質

1. **key 為 deterministic 純函式**(`build_object_key`):相同輸入必得相同 key。遷移
   Phase 1(只上傳)與 Phase 2(改寫 JSONB)靠「重算」取得同一把 key,整個兩階段遷移
   因此**不需要** mapping 表 / 暫存欄位 / migration(§D.6)。530 / 531 **必須** import
   本模組的函式,**禁**各自複製一份實作 —— 兩份實作一旦漂移,Phase 2 會改寫出指向不
   存在物件的路徑,而且不會有任何錯誤訊息。
2. **輸出永遠不含 base64**:本模組只產「快照用值」;`file_data` 的 base64 在任何情況下
   (含上傳失敗)都不會出現在回傳值裡(§D.5 硬規則,user 原話「file 寫進 DB 會炸」)。
3. **best-effort**:任一附件失敗只記失敗標記 + 結構化 log,繼續處理下一個,**絕不**拋
   例外中斷主流程(§D.5;記帳層不該有權力擋掉一個本來會成功的請求)。

## 邊界

- 本模組**只**輸出快照用值;下游 payload(`_rewrite_request`)吃的仍是**原始輸入**,
  一個 byte 都不改(§D.4,user 定調「改的只是平台後端 log 儲存路徑而已」)。
- 遠端 `http(s)://` 輸入**原樣保留、不代抓**(§D.2,避免 SSRF 面)。
- `S3_STORAGE_ENABLED=false` → 直接回 v2.2.0 等價的快照值,**不呼叫** S3。
- 所有 S3 呼叫走 `app/clients/s3`(已包好 `asyncio.to_thread`),本模組**不碰** boto3。

規範:`90-third-party-service/09-object-storage.md`、`00-overview/05-timezone.md`、
`03-backend/05-exceptions-and-logging.md`。
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from app.clients.s3 import S3Client, S3Error, get_s3_client
from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.model import ChatMessage

logger = get_logger(__name__)

__all__ = [
    "AttachmentScope",
    "AttachmentSnapshot",
    "ParsedAttachment",
    "SnapshotValue",
    "build_attachment_snapshot",
    "build_object_key",
    "content_type_for_mime",
    "extension_for_mime",
    "is_remote_url",
    "parse_data_uri",
]

# 全棧鎖 UTC+8(`00-overview/05-timezone.md`);key 的日期分層取台北日曆日。
_TW_TZ = ZoneInfo("Asia/Taipei")

# data URI:`data:<mime>[;參數]*;base64,<payload>`。
# 相容 `;charset=utf-8` 這類中介參數(瀏覽器實務常見),mime 一律取第一段;
# 缺 mime(`data:;base64,...`)不匹配,依 §D.5 視同畸形值走 best-effort。
_DATA_URI_RE = re.compile(
    r"^data:([^;,]+)((?:;[^;,]+)*);base64,(.*)$",
    re.DOTALL | re.IGNORECASE,
)
_REMOTE_URL_RE = re.compile(r"^https?://", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s+")

# key 的路徑片段字元集刻意**不含** `.`:S3Client 會擋掉任何含 `..` 的 key,
# 與其讓 uid 帶點時整批上傳被拒,不如在組 key 時就消滅這個可能性。
_SEGMENT_UNSAFE_RE = re.compile(r"[^A-Za-z0-9_-]")
_SEGMENT_FALLBACK = "unknown"

# key 內的內容雜湊長度(propose §B.3:`<idx>-<sha256[:16]>.<ext>`)。
_KEY_DIGEST_CHARS = 16

# MIME → 副檔名白名單。副檔名**禁**取自使用者輸入的檔名(路徑穿越 / 非 ASCII /
# 長度上限問題),一律由此表推導(`09-object-storage.md` § 物件 key 規則)。
# 白名單外的 MIME 一律落 `bin` + `application/octet-stream`:
# 既不丟資料(仍照常上傳),又讓 presigned URL 開啟時瀏覽器一律走下載而非直接渲染 ——
# `image/svg+xml` 刻意不列入白名單正是為此(SVG 可帶 script,直接渲染等同儲存型 XSS)。
_MIME_EXTENSIONS: dict[str, str] = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
    "image/bmp": "bmp",
    "image/tiff": "tif",
    "image/heic": "heic",
    "application/pdf": "pdf",
    "application/json": "json",
    "application/zip": "zip",
    "application/msword": "doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.ms-excel": "xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.ms-powerpoint": "ppt",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "text/plain": "txt",
    "text/csv": "csv",
    "text/markdown": "md",
}
_FALLBACK_EXT = "bin"
_FALLBACK_MIME = "application/octet-stream"

# 失敗原因(進快照 + 進 log;刻意為短代碼,不帶任何內容或憑證資訊)。
_REASON_INVALID_DATA_URI = "invalid_data_uri"
_REASON_S3_FAILED = "s3_upload_failed"
_REASON_S3_UNAVAILABLE = "s3_unavailable"

AttachmentScope = Literal["chat", "legacy"]

# 快照裡單一附件的值:成功為字串(S3 物件 key,或原樣保留的遠端 URL),
# 失敗為帶 metadata 的失敗標記 dict。
SnapshotValue = str | dict[str, object]

_AttachmentKind = Literal["image_url", "file"]


@dataclass(frozen=True, slots=True)
class ParsedAttachment:
    """從 data URI 解出的附件內容。"""

    mime: str
    content: bytes
    sha256: str

    @property
    def size(self) -> int:
        return len(self.content)


@dataclass(frozen=True, slots=True)
class AttachmentSnapshot:
    """本模組的唯一輸出:寫進 `usage_logs.request_content` 用的附件值。

    - `images` / `files`:單輪模式用;`messages` 模式下為空 list。
    - `messages`:messages 直傳模式用的整段快照(file part 只留檔名 + 路徑);
      單輪模式為 `None`。
    - `enabled`:本次是否實際走 S3(`S3_STORAGE_ENABLED`);`False` 時上三者為
      v2.2.0 等價值。
    - `uploaded` / `failed`:成功與失敗的附件數,供呼叫端記 log / 觀測。
    """

    images: list[SnapshotValue]
    files: list[SnapshotValue]
    messages: list[dict[str, object]] | None
    enabled: bool
    uploaded: int
    failed: int


def _normalize_mime(mime: str) -> str:
    return mime.split(";")[0].strip().lower()


def extension_for_mime(mime: str) -> str:
    """由 MIME 白名單推導副檔名;白名單外一律 `bin`。

    530 / 531 重算 key 時**必須**呼叫本函式,不可自行猜副檔名。
    """
    return _MIME_EXTENSIONS.get(_normalize_mime(mime), _FALLBACK_EXT)


def content_type_for_mime(mime: str) -> str:
    """由 MIME 白名單推導上傳用的 `Content-Type`;白名單外一律 octet-stream。

    why 不直接透傳使用者給的 mime:該值最終會被 presigned URL 回吐給管理端瀏覽器,
    等於讓呼叫端決定我方頁面如何渲染這份內容。
    """
    normalized = _normalize_mime(mime)
    return normalized if normalized in _MIME_EXTENSIONS else _FALLBACK_MIME


def is_remote_url(value: str) -> bool:
    """輸入是否已是遠端 `http(s)://` URL(§D.2:原樣保留、不代抓)。"""
    return _REMOTE_URL_RE.match(value.strip()) is not None


def parse_data_uri(value: str) -> ParsedAttachment | None:
    """解析 base64 data URI。

    Returns:
        解析成功回 `ParsedAttachment`;**任何**畸形情況(不是 data URI / 無 mime /
        base64 解不開 / 內容為空)一律回 `None`,由呼叫端走 best-effort 失敗路徑,
        **不**拋例外。
    """
    match = _DATA_URI_RE.match(value.strip())
    if match is None:
        return None

    mime = _normalize_mime(match.group(1))
    if not mime:
        return None

    payload = _WHITESPACE_RE.sub("", match.group(3))
    if not payload:
        return None

    try:
        content = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError):
        return None
    if not content:
        return None

    return ParsedAttachment(
        mime=mime,
        content=content,
        sha256=hashlib.sha256(content).hexdigest(),
    )


def _safe_segment(value: str) -> str:
    cleaned = _SEGMENT_UNSAFE_RE.sub("-", value.strip())
    return cleaned or _SEGMENT_FALLBACK


def _prefix_segments(key_prefix: str) -> list[str]:
    """把 `S3_KEY_PREFIX` 正規化為路徑片段。

    `dev` / `dev/` / `/dev/` / `` 皆可接受(compose 以 `${VAR}` 引用時可能展開成空字串);
    空前綴回空 list,不會產生前導 `/`(S3Client 會擋)。
    """
    return [_safe_segment(part) for part in key_prefix.split("/") if part.strip()]


def build_object_key(
    *,
    scope: AttachmentScope,
    owner_uid: str,
    index: int,
    content: bytes,
    mime: str,
    key_prefix: str,
    occurred_at: datetime | None = None,
) -> str:
    """組出 deterministic 的 S3 物件 key(**純函式**:相同輸入 → 相同 key)。

    這是 v2.2.1 兩階段遷移的地基:Phase 1 上傳與 Phase 2 改寫各自呼叫本函式重算,
    因而不需要 mapping 表 / 暫存欄位 / migration(§D.6)。**禁**在別處複製實作。

    key 形態(對齊 propose §B.2 / §B.3):

    - `scope="chat"`(新請求):
      `<prefix>/chat/<YYYY>/<MM>/<DD>/<request_uid>/<idx>-<sha256[:16]>.<ext>`
    - `scope="legacy"`(歷史遷移):
      `<prefix>/legacy/<usage_log_uid>/<idx>-<sha256[:16]>.<ext>`

    Args:
        scope: `chat`(新請求)或 `legacy`(歷史遷移)。
        owner_uid: `chat` 為 request uid;`legacy` 為 `usage_log_uid`。
        index: 該附件在同一請求 / 同一列內的序號(由呼叫端依走訪順序給,自 0 起算)。
        content: 附件的**原始 bytes**(已 base64 decode)。
        mime: 附件 MIME;副檔名由白名單推導,不取自使用者檔名。
        key_prefix: `S3_KEY_PREFIX`;dev / test / prod 共用單一 bucket 的唯一隔離手段。
        occurred_at: `scope="chat"` 必填(日期分層取 Asia/Taipei 日曆日);
            naive datetime 視為台北時間。`scope="legacy"` 不使用。

    Returns:
        物件 key(無前導 `/`、無 `..`、無控制字元)。

    Raises:
        ValueError: `scope="chat"` 卻未提供 `occurred_at`,或 `index` 為負。
    """
    if index < 0:
        raise ValueError("index 不可為負")

    digest = hashlib.sha256(content).hexdigest()[:_KEY_DIGEST_CHARS]
    filename = f"{index}-{digest}.{extension_for_mime(mime)}"

    segments = _prefix_segments(key_prefix)
    if scope == "chat":
        if occurred_at is None:
            raise ValueError("scope='chat' 必須提供 occurred_at")
        at = occurred_at if occurred_at.tzinfo else occurred_at.replace(tzinfo=_TW_TZ)
        at = at.astimezone(_TW_TZ)
        segments += [
            "chat",
            f"{at.year:04d}",
            f"{at.month:02d}",
            f"{at.day:02d}",
            _safe_segment(owner_uid),
        ]
    else:
        segments += ["legacy", _safe_segment(owner_uid)]
    segments.append(filename)
    return "/".join(segments)


def _image_marker(detail: dict[str, object]) -> dict[str, object]:
    """單輪 `images` 與 messages `image_url` part 共用的失敗標記(§D.5)。"""
    return {"type": "image_url", "upload_failed": True, **detail}


def _file_marker(filename: str, detail: dict[str, object]) -> dict[str, object]:
    """`file` 附件的失敗標記;**永遠**不含 `file_data`(§D.5 硬規則)。"""
    return {"type": "file", "file": {"filename": filename, "upload_failed": True, **detail}}


def _file_value(filename: str, key: str) -> dict[str, object]:
    """`file` 附件的成功快照值:檔名 + 物件路徑(推翻 v2.1.2「僅記檔名」,§D.3)。

    `key` 為 S3 物件 key;輸入原本就是遠端 URL 時則原樣保留該 URL(§D.2),
    判別方式與 image 一致(`is_remote_url`)。
    """
    return {"type": "file", "file": {"filename": filename, "key": key}}


class _Runner:
    """單次請求內的附件走訪狀態(index 計數 + 成敗統計)。

    index 在**整個請求**內連號(單輪為 images → files,messages 為 content 出現順序),
    確保同一請求內兩份相同內容的附件也拿到不同 key。
    """

    def __init__(
        self,
        *,
        client: S3Client | None,
        request_uid: str,
        key_prefix: str,
        occurred_at: datetime,
    ) -> None:
        self._client = client
        self._request_uid = request_uid
        self._key_prefix = key_prefix
        self._occurred_at = occurred_at
        self._index = 0
        self.uploaded = 0
        self.failed = 0

    async def take(
        self, value: str, *, kind: _AttachmentKind
    ) -> tuple[str | None, dict[str, object] | None]:
        """處理單一附件。

        Returns:
            `(快照字串, None)` 表成功(S3 key 或原樣保留的遠端 URL);
            `(None, 失敗 metadata)` 表失敗。**任何情況下都不拋例外**。
        """
        index = self._index
        self._index += 1

        if is_remote_url(value):
            # §D.2:遠端 URL 原樣保留、不代抓(避免 SSRF 面);不算上傳。
            return value.strip(), None

        parsed = parse_data_uri(value)
        if parsed is None:
            return None, self._fail(
                index=index,
                kind=kind,
                mime="",
                size=0,
                sha256="",
                reason=_REASON_INVALID_DATA_URI,
                extra="",
            )

        if self._client is None:
            return None, self._fail(
                index=index,
                kind=kind,
                mime=parsed.mime,
                size=parsed.size,
                sha256=parsed.sha256,
                reason=_REASON_S3_UNAVAILABLE,
                extra="",
            )

        key = build_object_key(
            scope="chat",
            owner_uid=self._request_uid,
            index=index,
            content=parsed.content,
            mime=parsed.mime,
            key_prefix=self._key_prefix,
            occurred_at=self._occurred_at,
        )
        try:
            await self._client.put_object(key, parsed.content, content_type_for_mime(parsed.mime))
        except S3Error as err:
            return None, self._fail(
                index=index,
                kind=kind,
                mime=parsed.mime,
                size=parsed.size,
                sha256=parsed.sha256,
                reason=_REASON_S3_FAILED,
                extra=f"{type(err).__name__}/{err.aws_code}",
            )
        except Exception as err:  # noqa: BLE001 - best-effort:未預期例外同樣不得中斷主流程
            # 刻意不用 logger.exception:traceback 可能夾帶下層原始訊息(見 s3/errors.py 檔頭),
            # 本專案 log 無機密過濾層,只留例外類別名。
            return None, self._fail(
                index=index,
                kind=kind,
                mime=parsed.mime,
                size=parsed.size,
                sha256=parsed.sha256,
                reason=_REASON_S3_FAILED,
                extra=type(err).__name__,
            )

        self.uploaded += 1
        return key, None

    def _fail(
        self,
        *,
        index: int,
        kind: _AttachmentKind,
        mime: str,
        size: int,
        sha256: str,
        reason: str,
        extra: str,
    ) -> dict[str, object]:
        """記結構化 log 並回失敗 metadata。

        log **禁**帶 base64 內容與 AWS 憑證:只有 index / mime / bytes / sha256 /
        原因代碼與例外類別名(`03-backend/05-exceptions-and-logging.md`)。
        """
        self.failed += 1
        logger.warning(
            "附件落地失敗 request_uid=%s index=%s kind=%s mime=%s bytes=%s sha256=%s reason=%s detail=%s",
            self._request_uid,
            index,
            kind,
            mime or "-",
            size,
            sha256 or "-",
            reason,
            extra or "-",
        )
        return {"mime": mime, "bytes": size, "sha256": sha256, "reason": reason}


def _snapshot_message_passthrough(message: ChatMessage) -> dict[str, object]:
    """`S3_STORAGE_ENABLED=false` 時的 messages 快照 —— 與 v2.2.0 行為完全一致。

    image_url part 原樣保留(含 base64),file part 只留 `filename`
    (`file_data` 依硬規則永遠不入快照)。
    """
    dumped: dict[str, object] = message.model_dump(exclude_none=True)
    content = dumped.get("content")
    if isinstance(content, list):
        dumped["content"] = [
            {"type": "file", "file": {"filename": _filename_of(part)}}
            if isinstance(part, dict) and part.get("type") == "file"
            else part
            for part in content
        ]
    return dumped


def _filename_of(part: Mapping[str, object]) -> str:
    inner = part.get("file")
    if isinstance(inner, Mapping):
        name = inner.get("filename")
        if isinstance(name, str):
            return name
    return ""


def _file_data_of(part: Mapping[str, object]) -> str:
    inner = part.get("file")
    if isinstance(inner, Mapping):
        data = inner.get("file_data")
        if isinstance(data, str):
            return data
    return ""


def _image_url_of(part: Mapping[str, object]) -> str:
    inner = part.get("image_url")
    if isinstance(inner, Mapping):
        url = inner.get("url")
        if isinstance(url, str):
            return url
    return ""


def _passthrough_snapshot(
    *,
    images: Sequence[str] | None,
    files: Sequence[Mapping[str, str]] | None,
    messages: Sequence[ChatMessage] | None,
) -> AttachmentSnapshot:
    """開關關閉時的輸出:與 v2.2.0 的 `_build_request_log` 逐欄等價,**不呼叫** S3。"""
    if messages is not None:
        return AttachmentSnapshot(
            images=[],
            files=[],
            messages=[_snapshot_message_passthrough(m) for m in messages],
            enabled=False,
            uploaded=0,
            failed=0,
        )
    return AttachmentSnapshot(
        images=list(images or []),
        # v2.2.0 單輪快照為 `[filename, ...]`;`file_data` 從不入快照。
        files=[str(f.get("filename", "")) for f in files or []],
        messages=None,
        enabled=False,
        uploaded=0,
        failed=0,
    )


def _resolve_client(client: S3Client | None) -> S3Client | None:
    if client is not None:
        return client
    try:
        return get_s3_client()
    except S3Error as err:
        # 開關已開卻取不到 client(bucket 未設定 / 憑證缺漏)屬設定錯,但仍不得擋主流程:
        # 全部附件走失敗標記,而非降級把 base64 寫進 DB(§D.5:不降級)。
        logger.warning(
            "S3 client 取得失敗,本次附件全數記為 upload_failed error=%s aws_code=%s",
            type(err).__name__,
            err.aws_code or "-",
        )
        return None


async def build_attachment_snapshot(
    *,
    request_uid: str,
    images: Sequence[str] | None = None,
    files: Sequence[Mapping[str, str]] | None = None,
    messages: Sequence[ChatMessage] | None = None,
    client: S3Client | None = None,
    occurred_at: datetime | None = None,
) -> AttachmentSnapshot:
    """把請求中的附件落 S3,回傳**快照用值**(唯一對外入口)。

    單輪模式(`images` / `files`)與 messages 直傳模式共用同一組解析 / key / 上傳邏輯;
    同一份內容在兩種模式下(相同 `request_uid` 與相同走訪序號)得到**相同**的 key。

    Args:
        request_uid: 本次請求的識別碼,作為 key 的擁有者層級。
        images: 單輪模式圖片(data URI 或遠端 URL)。
        files: 單輪模式檔案(`{"filename": ..., "file_data": ...}`)。
        messages: messages 直傳模式的訊息;有值時 `images` / `files` 應為 None
            (互斥性已由 `ChatRequest` schema 保證,本函式不重複驗證)。
        client: S3 client;預設取單例。測試以 stub 注入。
        occurred_at: 請求時間(key 的日期分層用);預設取現在(Asia/Taipei)。

    Returns:
        `AttachmentSnapshot`;**永不**包含 base64,**永不**拋例外(best-effort,§D.5)。
    """
    settings = get_settings()
    if not settings.S3_STORAGE_ENABLED:
        return _passthrough_snapshot(images=images, files=files, messages=messages)

    runner = _Runner(
        client=_resolve_client(client),
        request_uid=request_uid,
        key_prefix=settings.S3_KEY_PREFIX,
        occurred_at=occurred_at or datetime.now(_TW_TZ),
    )

    if messages is not None:
        snapshot_messages = [await _walk_message(m, runner) for m in messages]
        return AttachmentSnapshot(
            images=[],
            files=[],
            messages=snapshot_messages,
            enabled=True,
            uploaded=runner.uploaded,
            failed=runner.failed,
        )

    snapshot_images: list[SnapshotValue] = []
    for raw in images or []:
        key, detail = await runner.take(raw, kind="image_url")
        snapshot_images.append(key if key is not None else _image_marker(detail or {}))

    snapshot_files: list[SnapshotValue] = []
    for item in files or []:
        filename = str(item.get("filename", ""))
        key, detail = await runner.take(str(item.get("file_data", "")), kind="file")
        snapshot_files.append(
            _file_value(filename, key) if key is not None else _file_marker(filename, detail or {})
        )

    return AttachmentSnapshot(
        images=snapshot_images,
        files=snapshot_files,
        messages=None,
        enabled=True,
        uploaded=runner.uploaded,
        failed=runner.failed,
    )


async def _walk_message(message: ChatMessage, runner: _Runner) -> dict[str, object]:
    """走訪單則 messages 直傳訊息的 content parts,替換 image_url / file part。

    text part 原樣保留;`file_data` 一律不複製到輸出(§D.5 硬規則)。
    """
    dumped: dict[str, object] = message.model_dump(exclude_none=True)
    content = dumped.get("content")
    if not isinstance(content, list):
        return dumped

    parts: list[dict[str, object]] = []
    for part in content:
        if not isinstance(part, dict):
            continue
        part_type = part.get("type")
        if part_type == "image_url":
            key, detail = await runner.take(_image_url_of(part), kind="image_url")
            parts.append(
                {"type": "image_url", "image_url": {"url": key}}
                if key is not None
                else _image_marker(detail or {})
            )
        elif part_type == "file":
            filename = _filename_of(part)
            key, detail = await runner.take(_file_data_of(part), kind="file")
            parts.append(
                _file_value(filename, key)
                if key is not None
                else _file_marker(filename, detail or {})
            )
        else:
            parts.append(part)
    dumped["content"] = parts
    return dumped
