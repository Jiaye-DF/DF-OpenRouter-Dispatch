"""`usage_logs.request_content` 快照的正規化讀取層(v2.1.3)。

v2.1.2 起 request_content 有**兩種形狀**(見 proxy `_build_request_log`):

- 單輪模式:`{model, text, images, files, tools}`(v1.2 起,DB 內既有歷史列皆為此形狀)
- messages 直傳模式:`{model, messages: [...]}`(**沒有 `text` / `images` 鍵**)

既有列無法回填,寫入端也不宜改形狀(明細頁 / 匯出皆依賴),因此**所有讀取端一律經
本模組正規化**,不得再直接 `request_content.get("text")` —— 那正是 v2.1.2 的實際缺陷:
messages 模式的紀錄被 AI 評估與重跑當成「空輸入」處理,判分與 A/B 勝負全部失效且不報錯。

本模組為純函式、無 I/O、無 DB;不 import 任何 service,避免循環相依。
"""

from collections.abc import Mapping
from typing import Any

# 快照裡的 role → 給裁判 prompt 用的中文標籤(role 走 schema Literal 白名單,僅此三種;
# 未知 role 一律 fallback 回原字串,不 KeyError)。
ROLE_LABELS: dict[str, str] = {
    "system": "系統提示",
    "user": "使用者",
    "assistant": "助理",
}


def _raw_messages(request_content: Mapping[str, Any] | None) -> list[Any] | None:
    """取出 messages 模式的原始 messages 陣列;非 messages 模式 → None。"""
    if not request_content:
        return None
    raw = request_content.get("messages")
    return raw if isinstance(raw, list) else None


def is_messages_snapshot(request_content: Mapping[str, Any] | None) -> bool:
    """此快照是否為 messages 直傳模式(v2.1.2 起)。"""
    return _raw_messages(request_content) is not None


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


def messages_of(request_content: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """兩種快照形狀 → 統一的 `[{role, content}]`。

    - messages 模式:原樣返回(濾掉缺 role 的雜訊列)。
    - 單輪模式:等價還原成**單一則 user 訊息**(text / images / files 併為 content parts;
      files 快照僅有檔名,還原為只含 `filename` 的 file part)。
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
        parts.append({"type": "image_url", "image_url": {"url": img}})
    for filename in request_content.get("files") or []:
        parts.append({"type": "file", "file": {"filename": filename}})
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


def replay_messages(request_content: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """組出「重跑 challenger」用的 messages payload。

    - messages 模式:整段對話原樣重放,但**剔除 file part** —— 快照為法務考量僅留
      `filename`、不留 `file_data`,無內容可送下游;剔到 content 全空的訊息一併略過。
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
        parts = [part for part in as_parts(content) if part.get("type") != "file"]
        if parts:
            out.append({"role": msg["role"], "content": parts})
    return out or [{"role": "user", "content": ""}]
