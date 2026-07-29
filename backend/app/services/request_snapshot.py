"""`usage_logs.request_content` 快照的正規化讀取層(v2.2.1)。

v2.1.2 起 request_content 有**兩種形狀**(見 proxy `_build_request_log`):

- 單輪模式:`{model, text, images, files, tools}`(v1.2 起,DB 內既有歷史列皆為此形狀)
- messages 直傳模式:`{model, messages: [...]}`(**沒有 `text` / `images` 鍵**)

既有列無法回填,寫入端也不宜改形狀(明細頁 / 匯出皆依賴),因此**所有讀取端一律經
本模組正規化**,不得再直接 `request_content.get("text")` —— 那正是 v2.1.2 的實際缺陷:
messages 模式的紀錄被 AI 評估與重跑當成「空輸入」處理,判分與 A/B 勝負全部失效且不報錯。

v2.2.1(附件落 S3)起,**附件值本身**又多出第三種形態(產出端見 `attachment.py`):

| 情境 | 單輪 `images[i]` | `files[i]` / messages `file` part | messages `image_url` part |
| --- | --- | --- | --- |
| 落 S3 成功 | `"<物件 key>"` | `{"type":"file","file":{"filename":..,"key":..}}` | `url` 為物件 key |
| 遠端 URL | 原 URL | 同上,`key` 為原 URL | `url` 為原 URL |
| 上傳失敗 | **dict** 失敗標記(`upload_failed: true`) | `file.upload_failed: true` | 同 images 失敗標記 |
| 開關關閉 | 原 data URI 字串 | `"<檔名>"` 字串 | 原 part |

關鍵是單輪 `images[i]` 會**從字串變成 dict**,而失敗標記本身不帶任何內容 —— 只要哪個
讀取端把它濾掉或當成「無附件」,就會複製一次 v2.1.2 的靜默失效。因此本層一律把新形態
視為「**附件存在**」(數量算進去),只在「內容能不能送下游」這件事上區分
(`attachment_form` / `attachment_ref_of`)。

本模組為純函式、無 I/O、無 DB;不 import 任何 service,避免循環相依。物件 key → presigned
URL 需要 I/O,屬 API 層(task-527),**禁**在本層做。
"""

import re
from collections.abc import Mapping
from typing import Any, Literal

# 快照裡的 role → 給裁判 prompt 用的中文標籤(role 走 schema Literal 白名單,僅此三種;
# 未知 role 一律 fallback 回原字串,不 KeyError)。
ROLE_LABELS: dict[str, str] = {
    "system": "系統提示",
    "user": "使用者",
    "assistant": "助理",
}

# 附件值的形態:四態(v2.2.1)+ `empty`(該附件沒有任何內容參照,如 v2.2.0 只留檔名的 file)。
AttachmentForm = Literal["data_uri", "object_key", "remote_url", "upload_failed", "empty"]

_DATA_URI_PREFIX = "data:"

# 刻意與 `attachment.is_remote_url` 重複一份 —— 本層規範為不 import 任何 service。
_REMOTE_URL_RE = re.compile(r"^https?://", re.IGNORECASE)

# 「值本身就是內容」的形態,可直接送進 challenger 重跑;
# 物件 key 不在此列:換 presigned URL 需要 I/O,不屬本層。
_REPLAYABLE_FORMS: frozenset[str] = frozenset({"data_uri", "remote_url"})

# 附件 part → 內容參照欄位(image 走 `image_url.url`,file 走 v2.2.1 新增的 `file.key`)。
_REF_FIELDS: tuple[tuple[str, str], ...] = (("image_url", "url"), ("file", "key"))


def _raw_messages(request_content: Mapping[str, Any] | None) -> list[Any] | None:
    """取出 messages 模式的原始 messages 陣列;非 messages 模式 → None。"""
    if not request_content:
        return None
    raw = request_content.get("messages")
    return raw if isinstance(raw, list) else None


def is_messages_snapshot(request_content: Mapping[str, Any] | None) -> bool:
    """此快照是否為 messages 直傳模式(v2.1.2 起)。"""
    return _raw_messages(request_content) is not None


def _inner_mapping(part: Mapping[str, Any], key: str) -> Mapping[str, Any] | None:
    inner = part.get(key)
    return inner if isinstance(inner, Mapping) else None


def _form_of_ref(ref: str) -> AttachmentForm:
    """由參照字串判形態;認不出來的一律當**物件 key**(而非丟棄)。

    落在 fallback 的只會是「非 data URI、非 http(s)」的路徑字串,寧可讓讀取端多試一次
    presign 失敗,也不要把有東西的附件判成沒有。
    """
    if ref[: len(_DATA_URI_PREFIX)].lower() == _DATA_URI_PREFIX:
        return "data_uri"
    if _REMOTE_URL_RE.match(ref):
        return "remote_url"
    return "object_key"


def is_upload_failed(value: Any) -> bool:
    """此附件值 / content part 是否為 v2.2.1 的上傳失敗標記。

    標記代表「**有這個附件**,但內容沒留存」—— 計數要算,內容不可取。
    image 走 part 頂層 `upload_failed`,file 走 `file.upload_failed`(見 `attachment.py`)。
    """
    if not isinstance(value, Mapping):
        return False
    if value.get("upload_failed") is True:
        return True
    inner = _inner_mapping(value, "file")
    return inner is not None and inner.get("upload_failed") is True


def attachment_ref_of(value: Any) -> str | None:
    """取附件的內容參照(S3 物件 key / 遠端 URL / data URI);無內容可取 → None。

    吃三種輸入:單輪 `images[i]` 原始值(字串)、`image_url` part、`file` part。
    上傳失敗標記與「只有檔名」的 v2.2.0 file 快照皆回 None。
    """
    if isinstance(value, str):
        return value.strip() or None
    if not isinstance(value, Mapping) or is_upload_failed(value):
        return None
    for key, field in _REF_FIELDS:
        inner = _inner_mapping(value, key)
        if inner is None:
            continue
        ref = inner.get(field)
        if isinstance(ref, str) and ref.strip():
            return ref.strip()
    return None


def attachment_form(value: Any) -> AttachmentForm:
    """判別單一附件值 / content part 的形態(v2.2.1 四態 + `empty`)。

    讀取端據此決定怎麼處理:`object_key` 需由 API 層換 presigned URL(task-527)、
    `upload_failed` 顯示「內容未留存」、`data_uri` / `remote_url` 可直接用。
    **任何形態都代表附件存在**,`empty` 亦然(如 v2.2.0 只留檔名的 file 快照)。
    """
    if is_upload_failed(value):
        return "upload_failed"
    ref = attachment_ref_of(value)
    return _form_of_ref(ref) if ref is not None else "empty"


def as_parts(content: Any) -> list[dict[str, Any]]:
    """把單則訊息的 content 正規化為 content parts 陣列。

    content 為字串 → 包成單一 text part(空字串 → 空陣列);已是陣列 → 濾掉非 dict 的雜訊。
    """
    if isinstance(content, str):
        return [{"type": "text", "text": content}] if content else []
    if isinstance(content, list):
        return [p for p in content if isinstance(p, dict)]
    return []


def text_of(content: Any) -> str:
    """取單則訊息 content 內的純文字(多個 text part 以換行串接;無文字 → 空字串)。"""
    chunks = [
        part["text"]
        for part in as_parts(content)
        if part.get("type") == "text" and isinstance(part.get("text"), str) and part["text"]
    ]
    return "\n".join(chunks)


def count_parts(content: Any, part_type: str) -> int:
    """數單則訊息 content 內指定型別(image_url / file / text)的 part 數量。"""
    return sum(1 for part in as_parts(content) if part.get("type") == part_type)


def _attachment_part(value: Any, part_type: Literal["image_url", "file"]) -> dict[str, Any]:
    """單輪快照的 `images[i]` / `files[i]` → content part。

    v2.2.0(含全部歷史列)為字串:圖片是 data URI、檔案只有檔名 —— 行為與過去逐字相同。
    v2.2.1 起可能已是 **dict**(成功的 file 值、或上傳失敗標記),此時原樣保留並補上
    `type`;若改成往 `image_url.url` 塞一個 dict,下游數量統計與明細頁都會拿到畸形 part。
    """
    if isinstance(value, Mapping):
        part: dict[str, Any] = dict(value)
        if not isinstance(part.get("type"), str) or not part["type"]:
            part["type"] = part_type
        return part
    if part_type == "image_url":
        return {"type": "image_url", "image_url": {"url": value}}
    return {"type": "file", "file": {"filename": value}}


def messages_of(request_content: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """兩種快照形狀 → 統一的 `[{role, content}]`。

    - messages 模式:原樣返回(濾掉缺 role 的雜訊列)。
    - 單輪模式:等價還原成**單一則 user 訊息**(text / images / files 併為 content parts;
      附件的三種形態一律保留為 part,見 `_attachment_part`)。
    - 無任何內容(含 request_content 為 None)→ 空陣列。
    """
    raw = _raw_messages(request_content)
    if raw is not None:
        return [m for m in raw if isinstance(m, dict) and m.get("role")]
    if not request_content:
        return []

    parts: list[dict[str, Any]] = []
    text = request_content.get("text")
    if isinstance(text, str) and text:
        parts.append({"type": "text", "text": text})
    for img in request_content.get("images") or []:
        parts.append(_attachment_part(img, "image_url"))
    for item in request_content.get("files") or []:
        parts.append(_attachment_part(item, "file"))
    return [{"role": "user", "content": parts}] if parts else []


def input_text_of(request_content: Mapping[str, Any] | None) -> str | None:
    """取「任務輸入原文」:**最後一則 user 訊息**的文字;無文字 → None。

    單輪快照下等價於舊的 `request_content["text"]`(單輪只有一則 user 訊息)。
    """
    for msg in reversed(messages_of(request_content)):
        if msg.get("role") == "user":
            text = text_of(msg.get("content"))
            if text:
                return text
    return None


def _is_replayable(part: Mapping[str, Any]) -> bool:
    """此 content part 是否還帶得動內容,可送進 challenger 重跑。

    - `file`:快照從不留 `file_data`,無內容可送(v2.1.3 起既有行為)。
    - `image_url`:僅 data URI 與遠端 URL 可直接送;**S3 物件 key 與 upload_failed 標記
      送下去只是畸形 payload**(下游會拿到一個不是 URL 的字串,或一坨 metadata),
      換 presigned URL 需要 I/O 而不屬本層 → 一律剔除。v2.2.1 不擴大重跑行為。
    - 其餘(text 等)一律保留。
    """
    part_type = part.get("type")
    if part_type == "file":
        return False
    if part_type == "image_url":
        return attachment_form(part) in _REPLAYABLE_FORMS
    return True


def replay_messages(request_content: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """組出「重跑 challenger」用的 messages payload。

    - messages 模式:整段對話原樣重放,但**剔除送不出去的附件 part**(見 `_is_replayable`);
      剔到 content 全空的訊息一併略過。
    - 單輪模式:沿用 v2.1.1 行為 —— 僅重放 `text`,不含圖片 / 檔案(維持既有重跑成本與
      模型相容性,不在本次修正擴大行為)。
    - 兩者皆無內容 → 單一則空 user 訊息(與舊行為一致,由下游模型自行處理)。
    """
    if not is_messages_snapshot(request_content):
        text = request_content.get("text") if request_content else None
        return [{"role": "user", "content": text if isinstance(text, str) else ""}]

    out: list[dict[str, Any]] = []
    for msg in messages_of(request_content):
        content = msg.get("content")
        if isinstance(content, str):
            if content:
                out.append({"role": msg["role"], "content": content})
            continue
        parts = [part for part in as_parts(content) if _is_replayable(part)]
        if parts:
            out.append({"role": msg["role"], "content": parts})
    return out or [{"role": "user", "content": ""}]
