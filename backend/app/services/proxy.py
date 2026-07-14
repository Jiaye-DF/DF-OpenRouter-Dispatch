"""Chat 代理 — 依 model.provider 分流(v1.2)。

對齊 docs/Tasks/v1.2/propose-v1.2.0.md § 4 / § 6 / § 7。

兩條路徑:
- `openrouter`:per-Key 速率限制(從 `openrouter_keys` 表讀);撞限額 → failover 換下一把
- `internal`:per-Provider 速率限制(從 env 讀);撞限額 → 等待至 `RATE_WAIT_TIMEOUT`,超過 → 429 internal_busy
"""

import asyncio
import json
import random
import time
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils import uuid7

from app.clients.factory import ChatClientFactory
from app.clients.internal.client import (
    InternalAuthError,
    InternalClient,
    InternalError,
    InternalRateLimitError,
    InternalUnavailableError,
)
from app.clients.openrouter.errors import (
    OpenRouterAuthError,
    OpenRouterError,
    OpenRouterForbiddenError,
    OpenRouterModelNotFoundError,
    OpenRouterRateLimitError,
)
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.models.internal_key import InternalKey
from app.models.model import Model
from app.models.usage_log import UsageLog
from app.repositories.internal_key import InternalKeyRepository
from app.repositories.openrouter_key import OpenRouterKeyRepository
from app.schemas.model import ChatMessage, ResponseFormat
from app.services.internal_key import decrypt_key as decrypt_internal_key
from app.services.openrouter_key import decrypt_key
from app.services.rate_limit import RateLimitExceeded, get_limiter

logger = get_logger(__name__)

_MAX_RETRIES = 5

# 持有 fire-and-forget 背景 task(記帳 / key cooldown)的強引用,避免 event loop 只持
# weak ref 時被 GC 在完成前靜默取消。完成後自動移除。
_usage_log_tasks: set[asyncio.Task[None]] = set()

# 壞 key(401 失效 / 402 餘額不足)短期停用秒數;到期後 dispatch 自動再納入。
_KEY_COOLDOWN_SECONDS = 600


def schedule_key_cooldown(key_uid: UUID, *, seconds: int = _KEY_COOLDOWN_SECONDS) -> None:
    """壞 key 後台寫入 disabled_until = now()+seconds(獨立 session,fire-and-forget)。

    用 DB 時鐘(now())避免跨機時鐘不一致;失敗只記 log,不影響當前 dispatch。
    """

    async def _task() -> None:
        async with SessionLocal() as session:
            try:
                await session.execute(
                    text(
                        "UPDATE openrouter_keys "
                        "SET disabled_until = now() + make_interval(secs => :s) "
                        "WHERE openrouter_key_uid = :uid"
                    ),
                    {"s": seconds, "uid": str(key_uid)},
                )
                await session.commit()
            except Exception:
                logger.exception("寫入 key cooldown 失敗 uid=%s", key_uid)
                await session.rollback()

    try:
        task = asyncio.create_task(_task())
    except RuntimeError:
        logger.warning("schedule_key_cooldown 無 running loop,略過")
        return
    _usage_log_tasks.add(task)
    task.add_done_callback(_usage_log_tasks.discard)


def _rewrite_request(
    model: str,
    text: str | None,
    images: list[str] | None,
    tools: list[dict[str, Any]] | None = None,
    files: list[dict[str, str]] | None = None,
    messages: list[ChatMessage] | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    response_format: ResponseFormat | None = None,
) -> dict[str, Any]:
    """組出 OpenAI-compatible 的 `/chat/completions` payload(雙內容模式,v2.1.2)。

    對齊修訂後 50-openrouter.md § 5 / § 6.1 / § 6.2:輸入**僅開放白名單參數**,
    其餘 OpenAI 欄位(top_p / stop / penalties 等)一律不開放;兩種內容模式互斥擇一
    (互斥驗證已由 `ChatRequest` schema 層完成,本 fn 不重複驗證):

    - **單輪模式(預設)**:text / images / files 合併為單一 user 訊息的多模態
      content;皆空時補一個空白 text block,確保 messages 不為空。files 為
      OpenRouter `file` content part(如 PDF);file_data 為 data URL 或遠端 URL。
      組裝邏輯與 v2.1.1 完全一致(舊 client 行為不變)。
    - **messages 直傳模式(v2.1.2)**:呼叫端自帶多輪 `messages[]`(schema 白名單
      驗證後的型別化物件),`model_dump(exclude_none=True)` 後**原樣透傳**、不重組。

    兩模式共用的附掛欄位:

    - tools 有值才放進 payload(格式同 OpenAI tools 規格,原樣透傳給下游)。
    - 生成參數 `temperature` / `max_tokens` / `response_format` 有帶(非 None)才
      注入;None 一律不出現在 payload(走模型預設值)。`response_format` 以型別化
      物件 dump 展開,禁 raw dict 透傳。
    """
    payload: dict[str, Any]
    if messages is not None:
        # messages 直傳模式:schema 驗證後原樣透傳,不重組。
        payload = {
            "model": model,
            "messages": [m.model_dump(exclude_none=True) for m in messages],
        }
    else:
        content: list[dict[str, Any]] = []
        if text:
            content.append({"type": "text", "text": text})
        for img in images or []:
            content.append({"type": "image_url", "image_url": {"url": img}})
        for f in files or []:
            content.append(
                {"type": "file", "file": {"filename": f["filename"], "file_data": f["file_data"]}}
            )
        if not content:
            content.append({"type": "text", "text": ""})
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": content}],
        }
    if tools:
        payload["tools"] = tools
    if temperature is not None:
        payload["temperature"] = temperature
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    if response_format is not None:
        payload["response_format"] = response_format.model_dump(exclude_none=True)
    return payload


def _snapshot_message(message: ChatMessage) -> dict[str, Any]:
    """把單則 ChatMessage 轉成 usage_logs 快照用 dict(file part 僅留檔名)。

    content 為字串或非 file part(text / image_url)時原樣保留(image_url 含
    base64 原樣入 JSONB,與單輪模式 `images` 一致,對齊 propose v2.1.2 §D.4);
    file part 仿單輪模式**只記 `filename` 不記 `file_data`**(法務考量)。
    """
    dumped = message.model_dump(exclude_none=True)
    content = dumped.get("content")
    if isinstance(content, list):
        dumped["content"] = [
            {"type": "file", "file": {"filename": part["file"]["filename"]}}
            if part.get("type") == "file"
            else part
            for part in content
        ]
    return dumped


def _build_request_log(
    model: str,
    text: str | None,
    images: list[str] | None,
    tools: list[dict[str, Any]] | None = None,
    files: list[dict[str, str]] | None = None,
    messages: list[ChatMessage] | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    response_format: ResponseFormat | None = None,
) -> dict[str, Any]:
    """組出寫入 usage_logs.request_content 的請求快照(雙內容模式,v2.1.2)。

    與 `_rewrite_request` 分開:這裡保留使用者「原始輸入語意」供 dashboard 檢視,
    而非下游實際送出的 payload 結構。tools 有值才記。

    - 單輪模式:`{model, text, images}`(+ tools / files),結構與 v2.1.1 一致。
      files 刻意**只記錄檔名**(`filename`)、不記 `file_data`:避免將使用者上傳的
      檔案內容留存於系統(法務考量)。
    - messages 直傳模式:`{model, messages: <原樣快照>}`;file part 同樣僅記檔名,
      image_url part 原樣保留(見 `_snapshot_message`)。
    - 生成參數(兩模式皆同):有帶的 `temperature` / `max_tokens` /
      `response_format` 一併記入,供用量明細追溯呼叫條件;未帶不出現(不記 None)。
    """
    log: dict[str, Any]
    if messages is not None:
        log = {"model": model, "messages": [_snapshot_message(m) for m in messages]}
        if tools:
            log["tools"] = tools
    else:
        log = {"model": model, "text": text, "images": list(images or [])}
        if tools:
            log["tools"] = tools
        if files:
            log["files"] = [f["filename"] for f in files]
    if temperature is not None:
        log["temperature"] = temperature
    if max_tokens is not None:
        log["max_tokens"] = max_tokens
    if response_format is not None:
        log["response_format"] = response_format.model_dump(exclude_none=True)
    return log


def _extract_content(resp: dict[str, Any]) -> str:
    """從 OpenRouter / Internal 回應抽出最終文字內容,回給 SDK 使用者。

    SDK 使用者只關心「模型講了什麼」,內部 id / usage / provider / metadata 一律不外露
    (但仍會完整寫入 usage_logs 供 dashboard 統計)。

    Args:
        resp: 下游 `/chat/completions` 的原始 JSON body。

    Returns:
        第一個 choice 的文字內容;content 為多模態 list 時串接所有 text block,
        非 text 區塊(及尚未開放的 tool_calls)一律忽略。無 choices 時回空字串。
    """
    choices = resp.get("choices") or []
    if not choices:
        return ""
    msg = choices[0].get("message") or {}
    raw = msg.get("content")
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        # 多模態輸出:把所有 text block 串起來;非 text 區塊忽略。
        parts: list[str] = []
        for blk in raw:
            if isinstance(blk, dict) and blk.get("type") == "text":
                t = blk.get("text")
                if isinstance(t, str):
                    parts.append(t)
        return "".join(parts)
    return ""


def _summarize_response(resp: dict[str, Any]) -> dict[str, Any]:
    """把下游回應壓成寫入 usage_logs.response_summary 的摘要。

    v1.6.2 起改存**完整**模型回覆文字(`output_text`),供用量紀錄詳情頁完整檢視
    (本版本前的舊紀錄僅有截斷的 `first_text`,詳情頁需做相容 fallback)。同保留 usage。

    Args:
        resp: 下游 `/chat/completions` 的原始 JSON body。

    Returns:
        含 `output_text`(完整文字,沿用 `_extract_content` 抽取邏輯)與
        `usage`(若有)的字典。
    """
    summary: dict[str, Any] = {"output_text": _extract_content(resp)}
    if "usage" in resp:
        summary["usage"] = resp["usage"]
    return summary


def _simplify_sse_line(line: str, state: dict[str, Any]) -> str | None:
    """解析一行 OpenRouter SSE:更新記帳狀態,並回傳「簡化後」要轉給呼叫端的 SSE。

    平台**不**把 OpenRouter 原始 chunk(含 provider / cost / model 路由 / role /
    finish_reason 等內部欄位)外露,只回 `{ id, content }`;對齊非串流端點僅回純文字
    的精簡原則(見 50-openrouter.md § 6),並避免洩漏成本與供應商等內部資訊。

    Args:
        line: OpenRouter SSE 的單行字串(不含換行)。
        state: 記帳累積狀態,含 `parts`(文字片段)、`usage`、`id`;就地更新。

    Returns:
        要寫給呼叫端的簡化 SSE 字串(已含 `\\n\\n` 框架);遇 `[DONE]` 回簡化結束事件;
        此行無需轉發(空行 / keep-alive 註解 / 僅 role 或結束、無文字的 chunk)時回 None
        (但仍會把可記帳資訊累積進 state)。
    """
    s = line.strip()
    if not s.startswith("data:"):
        return None  # 空行 / `: OPENROUTER PROCESSING` keep-alive 註解不轉發
    data = s[len("data:") :].strip()
    if not data:
        return None
    if data == "[DONE]":
        return "data: [DONE]\n\n"
    try:
        obj = json.loads(data)
    except (ValueError, TypeError):
        return None
    if obj.get("error"):
        # OpenRouter 串流中途回報錯誤(無 content):不靜默吞掉,轉成簡化 error 事件,
        # 並標記 state 供記帳判定 status=error;不外露 OpenRouter 原始錯誤明細。
        state["error"] = True
        return 'data: {"error":"upstream_error"}\n\n'
    if state.get("id") is None and obj.get("id"):
        state["id"] = obj["id"]
    if obj.get("usage"):
        state["usage"] = obj["usage"]
    content_piece = ""
    for choice in obj.get("choices") or []:
        delta = choice.get("delta") or {}
        content = delta.get("content")
        if isinstance(content, str):
            content_piece += content
    if not content_piece:
        return None  # role 宣告 / 結束 / usage chunk 無文字 → 不轉發,但已累積記帳
    state["parts"].append(content_piece)
    payload = {"id": state.get("id"), "content": content_piece}
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _stream_state_to_resp(state: dict[str, Any]) -> dict[str, Any]:
    """把串流累積狀態合成 `schedule_usage_log` 可用的 resp dict。

    形狀對齊非串流的下游 body(`choices[0].message.content` 為串接後完整文字),
    使既有 `_extract_content` / `_summarize_response` 可直接沿用。
    """
    resp: dict[str, Any] = {
        "id": state.get("id"),
        "choices": [{"message": {"content": "".join(state["parts"])}}],
    }
    if state.get("usage"):
        resp["usage"] = state["usage"]
    return resp


async def _check_model_whitelist(db: AsyncSession, model: str) -> Model:
    """白名單由 DB 驅動;不存在 / 停用 / 軟刪除 一律 403 model_forbidden(避免列舉差異)。

    Args:
        db: 本次 request 的 DB session。
        model: 使用者指定的 model_key。

    Returns:
        命中白名單且啟用中的 Model 資料列。

    Raises:
        AppError: code=403 model_forbidden — 查無此模型或已停用 / 軟刪除。
    """
    stmt = select(Model).where(
        Model.model_key == model,
        Model.is_active.is_(True),
        Model.is_deleted.is_(False),
    )
    instance = (await db.execute(stmt)).scalar_one_or_none()
    if instance is None:
        raise AppError("model_forbidden", code=403)
    return instance


def schedule_usage_log(
    *,
    department_uid: UUID | None,
    project_uid: UUID | None,
    user_uid: UUID | None,
    openrouter_key_uid: UUID | None,
    model: str,
    model_uid: UUID | None,
    resp: dict[str, Any] | None,
    latency_ms: int,
    status: str,
    error_code: str | None,
    request_log: dict[str, Any],
) -> None:
    """Fire-and-forget 寫入一筆 usage_logs(獨立 session,不受主 request 影響)。

    以 asyncio.create_task 背景寫入,不阻塞回應;寫入失敗只記 log 不影響主流程。

    Args:
        department_uid: 呼叫者所屬部門 uid(歸戶用)。
        project_uid: 呼叫者所屬專案 uid。
        user_uid: 呼叫者使用者 uid。
        openrouter_key_uid: 本次實際使用的 OpenRouter Key uid;internal 路徑或
            全失敗無對應 Key 時為 None。
        model: 使用者指定的 model_key。
        model_uid: 對應的 Model 主鍵;無法解析時為 None。
        resp: 下游原始回應 body,用於抽 usage / cost / generation id;失敗時為 None。
        latency_ms: 本次呼叫耗時(毫秒)。
        status: "success" 或 "error"。
        error_code: 失敗時的錯誤碼(如 rate_limited / model_not_found);成功為 None。
        request_log: 請求快照(見 `_build_request_log`);本 fn 另由其 `tools` 鍵
            推導 `used_tools` 欄(有非空 tools → True)。
    """

    async def _task() -> None:
        async with SessionLocal() as session:
            try:
                usage = (resp or {}).get("usage") or {}
                prompt = int(usage.get("prompt_tokens") or 0)
                completion = int(usage.get("completion_tokens") or 0)
                total = int(usage.get("total_tokens") or (prompt + completion))
                # OpenRouter 用 `cost`;保留 total_cost 作為 fallback。internal 一般無 cost,預設 0。
                cost = Decimal(str(usage.get("cost") or usage.get("total_cost") or 0))
                gen_id = (resp or {}).get("id")
                # used_tools 直接由請求快照推導,避免在 6 個呼叫點各自傳參。
                used_tools = bool((request_log or {}).get("tools"))

                row = UsageLog(
                    usage_log_uid=UUID(str(uuid7())),
                    user_uid=user_uid,
                    department_uid=department_uid,
                    project_uid=project_uid,
                    openrouter_key_uid=openrouter_key_uid,
                    model=model,
                    model_uid=model_uid,
                    prompt_tokens=prompt,
                    completion_tokens=completion,
                    total_tokens=total,
                    cost_usd=cost,
                    latency_ms=latency_ms,
                    status=status,
                    error_code=error_code,
                    request_content=request_log,
                    response_summary=_summarize_response(resp) if resp else None,
                    openrouter_generation_id=gen_id,
                    used_tools=used_tools,
                )
                session.add(row)
                await session.commit()
            except Exception:
                logger.exception("usage_log 寫入失敗")
                await session.rollback()

    try:
        task = asyncio.create_task(_task())
    except RuntimeError:
        logger.warning("schedule_usage_log 無 running loop,略過")
        return
    # 持強引用直到完成,避免 task 被 GC 中途取消而漏記帳。
    _usage_log_tasks.add(task)
    task.add_done_callback(_usage_log_tasks.discard)


async def run_chat(
    db: AsyncSession,
    *,
    client_factory: ChatClientFactory,
    department_uid: UUID,
    project_uid: UUID,
    user_uid: UUID,
    model: str,
    text: str | None,
    images: list[str] | None,
    videos: list[str] | None,
    tools: list[dict[str, Any]] | None = None,
    files: list[dict[str, str]] | None = None,
    messages: list[ChatMessage] | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    response_format: ResponseFormat | None = None,
) -> str:
    """依 model.provider 分流到對應路徑;白名單檢查由本 fn 統一執行。

    回傳值刻意精簡為純文字內容(模型回應的 first content);usage / id / provider 等
    OpenRouter 原始欄位完整寫入 usage_logs 供 dashboard,但不暴露給 SDK 使用者。

    `tools` 直接透傳給下游(格式同 OpenAI tools 規格);OpenRouter 內建工具
    (如 `openrouter:web_search`)由 OpenRouter server 端執行,最終回應仍為純文字。

    v2.1.2 起支援 messages 直傳模式與生成參數(payload 組裝見 `_rewrite_request`);
    互斥 / 白名單驗證已由 `ChatRequest` schema 層完成,本 fn 不重複驗證。
    internal provider 的 payload 結構相同,messages 模式自然支援。

    Args:
        db: 本次 request 的 DB session。
        client_factory: 產生 OpenRouter / internal HTTP client 的工廠。
        department_uid: 呼叫者所屬部門 uid(白名單 Key 範圍與歸戶用)。
        project_uid: 呼叫者所屬專案 uid。
        user_uid: 呼叫者使用者 uid。
        model: 使用者指定的 model_key(須通過白名單)。
        text: 使用者文字輸入,可為 None(單輪模式)。
        images: 圖片 URL / data URI 清單,可為 None(單輪模式)。
        videos: 影片清單;本版本不支援,非空即回 400。
        tools: 可選工具清單,原樣透傳給下游;目前僅支援 server 端工具。
        files: 上傳檔案清單(filename / file_data),如 PDF;用量紀錄僅留檔名。
        messages: messages 直傳模式的多輪訊息(與 text/images/files 互斥);
            schema 驗證後原樣透傳;用量紀錄 file part 僅留檔名。
        temperature: 生成溫度(0-2);None 不注入 payload,走模型預設。
        max_tokens: 回覆 token 上限(≥1);None 不注入 payload,走模型預設。
        response_format: 型別化回覆格式(json_object / json_schema);None 不注入。

    Returns:
        模型回應的純文字內容。

    Raises:
        AppError: 各種失敗狀況,如 feature_not_supported(400)、model_forbidden(403)、
            rate_limited(429)、openrouter_unavailable / internal_unavailable(502) 等。
    """
    if videos:
        raise AppError("feature_not_supported", code=400)
    model_row = await _check_model_whitelist(db, model)

    payload = _rewrite_request(
        model,
        text,
        images,
        tools,
        files,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format=response_format,
    )
    request_log = _build_request_log(
        model,
        text,
        images,
        tools,
        files,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format=response_format,
    )

    if model_row.provider == "internal":
        return await _run_chat_internal(
            db,
            client_factory=client_factory,
            model_row=model_row,
            department_uid=department_uid,
            project_uid=project_uid,
            user_uid=user_uid,
            payload=payload,
            request_log=request_log,
        )
    return await _run_chat_openrouter(
        db,
        client_factory=client_factory,
        model_row=model_row,
        department_uid=department_uid,
        project_uid=project_uid,
        user_uid=user_uid,
        payload=payload,
        request_log=request_log,
    )


async def _run_chat_openrouter(
    db: AsyncSession,
    *,
    client_factory: ChatClientFactory,
    model_row: Model,
    department_uid: UUID,
    project_uid: UUID,
    user_uid: UUID,
    payload: dict[str, Any],
    request_log: dict[str, Any],
) -> str:
    """OpenRouter 流程 — 每把 Key 經 rate limiter,撞限額 failover 換下一把。

    最多重試 `_MAX_RETRIES` 把 Key;全部撞速率 → 429 rate_limited,
    曾實際打過 OR 仍失敗 → 502 openrouter_unavailable。

    Args:
        db: 本次 request 的 DB session。
        client_factory: HTTP client 工廠。
        model_row: 已通過白名單的 Model 資料列。
        department_uid: 呼叫者部門 uid(決定可用的 OpenRouter Key 範圍)。
        project_uid: 呼叫者專案 uid(記帳用)。
        user_uid: 呼叫者使用者 uid(記帳用)。
        payload: 已重組好的 `/chat/completions` payload(含 model / messages / tools)。
        request_log: 請求快照,寫入 usage_logs 用。

    Returns:
        模型回應的純文字內容。

    Raises:
        AppError: model_not_found(404)、model_forbidden(403)、rate_limited(429)、
            openrouter_unavailable(502)。
    """
    client = client_factory.openrouter()
    model = payload["model"]
    model_uid = model_row.model_uid

    last_err: Exception | None = None
    rate_limited_all = True  # 全部撞速率才回 rate_limited,否則回 openrouter_unavailable
    started = time.monotonic()

    # 迴圈外查一次 active key,記憶體內 shuffle 後依序取(最多 _MAX_RETRIES 把);
    # 對齊 internal 路徑,避免 failover 每圈重查整張表。
    keys = await OpenRouterKeyRepository(db).list_active_by_department(department_uid)
    for key_row in random.sample(keys, len(keys))[:_MAX_RETRIES]:
        # rate limiter:不等待,撞速率即換下一把
        limiter = await get_limiter(key_row.openrouter_key_uid)
        try:
            await limiter.acquire(
                rpm_limit=key_row.rpm_limit,
                min_interval_ms=key_row.min_request_interval_ms,
                wait_timeout=0,
            )
        except RateLimitExceeded:
            logger.warning(
                "OR Key uid=%s 速率限制(rpm=%d / min=%dms);切下一把",
                key_row.openrouter_key_uid,
                key_row.rpm_limit,
                key_row.min_request_interval_ms,
            )
            continue

        # 拿到 slot 後,後續任何失敗皆視為「實際打過 OR」失敗,不再全 rate_limited
        rate_limited_all = False

        try:
            raw_key = decrypt_key(key_row)
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            logger.exception("OpenRouter Key 解密失敗:%s", key_row.openrouter_key_uid)
            continue

        try:
            resp_body = await client.chat_completion(payload, api_key=raw_key)
        except OpenRouterAuthError as exc:
            last_err = exc
            schedule_key_cooldown(key_row.openrouter_key_uid)  # 401 失效 → 短期停用
            logger.warning("OpenRouter 401;切換下一把 Key")
            continue
        except OpenRouterModelNotFoundError as exc:
            schedule_usage_log(
                department_uid=department_uid,
                project_uid=project_uid,
                user_uid=user_uid,
                openrouter_key_uid=key_row.openrouter_key_uid,
                model=model,
                model_uid=model_uid,
                resp=None,
                latency_ms=int((time.monotonic() - started) * 1000),
                status="error",
                error_code="model_not_found",
                request_log=request_log,
            )
            raise AppError("model_not_found", code=404) from exc
        except OpenRouterForbiddenError as exc:
            schedule_usage_log(
                department_uid=department_uid,
                project_uid=project_uid,
                user_uid=user_uid,
                openrouter_key_uid=key_row.openrouter_key_uid,
                model=model,
                model_uid=model_uid,
                resp=None,
                latency_ms=int((time.monotonic() - started) * 1000),
                status="error",
                error_code="model_forbidden",
                request_log=request_log,
            )
            raise AppError("model_forbidden", code=403) from exc
        except OpenRouterRateLimitError as exc:
            schedule_usage_log(
                department_uid=department_uid,
                project_uid=project_uid,
                user_uid=user_uid,
                openrouter_key_uid=key_row.openrouter_key_uid,
                model=model,
                model_uid=model_uid,
                resp=None,
                latency_ms=int((time.monotonic() - started) * 1000),
                status="error",
                error_code="rate_limited",
                request_log=request_log,
            )
            raise AppError("rate_limited", code=429) from exc
        except OpenRouterError as exc:
            last_err = exc
            if exc.status == 402:
                schedule_key_cooldown(key_row.openrouter_key_uid)  # 402 餘額不足 → 短期停用
            logger.exception("OpenRouter 其他錯誤;嘗試下一把")
            continue

        # 成功
        latency_ms = int((time.monotonic() - started) * 1000)
        schedule_usage_log(
            department_uid=department_uid,
            project_uid=project_uid,
            user_uid=user_uid,
            openrouter_key_uid=key_row.openrouter_key_uid,
            model=model,
            model_uid=model_uid,
            resp=resp_body,
            latency_ms=latency_ms,
            status="success",
            error_code=None,
            request_log=request_log,
        )
        return _extract_content(resp_body)

    # 全部失敗
    latency_ms = int((time.monotonic() - started) * 1000)
    error_code = "rate_limited" if rate_limited_all else "openrouter_unavailable"
    code = 429 if rate_limited_all else 502
    schedule_usage_log(
        department_uid=department_uid,
        project_uid=project_uid,
        user_uid=user_uid,
        openrouter_key_uid=None,
        model=model,
        model_uid=model_uid,
        resp=None,
        latency_ms=latency_ms,
        status="error",
        error_code=error_code,
        request_log=request_log,
    )
    raise AppError(error_code, code=code) from last_err


async def _internal_call_once(
    *,
    client_factory: ChatClientFactory,
    key_row: InternalKey,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """以一把 InternalKey 構造 InternalClient 並發出單次呼叫。

    Args:
        client_factory: HTTP client 工廠(提供共用 httpx client)。
        key_row: 本次要使用的 internal_key 資料列(含 base_url 與加密 api_key)。
        payload: 已重組好的 `/chat/completions` payload。

    Returns:
        下游原始回應 body。

    Raises:
        InternalError 及其子類:由 InternalClient 依 HTTP 狀態碼拋出。
    """
    raw_key = decrypt_internal_key(key_row)
    client = InternalClient(
        client_factory.internal_httpx(),
        key_row.base_url,
        raw_key,
    )
    return await client.chat_completion(payload)


async def _run_chat_internal(
    db: AsyncSession,
    *,
    client_factory: ChatClientFactory,
    model_row: Model,
    department_uid: UUID,
    project_uid: UUID,
    user_uid: UUID,
    payload: dict[str, Any],
    request_log: dict[str, Any],
) -> str:
    """Internal 流程(v1.2 增量,DB-driven per-Key):

    1. 拿全平台 active internal_keys
    2. **Phase 1 failover**:對每把 Key acquire(wait_timeout=0);拿到的直接打,撞限額 / 連線錯 → 換下一把
    3. **Phase 2 wait**:全部 Key 撞限額 → 對其中一把(隨機)acquire(wait_timeout=RATE_WAIT_TIMEOUT),
       拿到了就打;再失敗 → 429 internal_busy

    Args:
        db: 本次 request 的 DB session。
        client_factory: HTTP client 工廠。
        model_row: 已通過白名單的 Model 資料列。
        department_uid: 呼叫者部門 uid(記帳用)。
        project_uid: 呼叫者專案 uid(記帳用)。
        user_uid: 呼叫者使用者 uid(記帳用)。
        payload: 已重組好的 `/chat/completions` payload。
        request_log: 請求快照,寫入 usage_logs 用。

    Returns:
        模型回應的純文字內容。

    Raises:
        AppError: provider_misconfigured(500,無任何 active key)、
            internal_busy(429,Phase 2 仍撞速率)、internal_unavailable(502,全失敗)。
    """
    settings = get_settings()
    model = payload["model"]
    model_uid = model_row.model_uid
    started = time.monotonic()

    repo = InternalKeyRepository(db)
    keys = await repo.list_active()
    if not keys:
        # 沒有任何 active key — 等同 provider 未設定
        raise AppError("provider_misconfigured", code=500)

    last_err: Exception | None = None
    rate_limited_all = True  # 全部僅因速率限制失敗 → 才走 Phase 2 wait
    tried_uids: set[UUID] = set()

    # Phase 1:全 failover(wait_timeout=0)
    shuffled = random.sample(keys, len(keys))
    for key_row in shuffled:
        tried_uids.add(key_row.internal_key_uid)
        limiter = await get_limiter(("INTERNAL", key_row.internal_key_uid))
        try:
            await limiter.acquire(
                rpm_limit=key_row.rpm_limit,
                min_interval_ms=key_row.min_request_interval_ms,
                wait_timeout=0,
            )
        except RateLimitExceeded:
            logger.warning(
                "Internal Key uid=%s 速率限制(rpm=%d / min=%dms);切下一把",
                key_row.internal_key_uid,
                key_row.rpm_limit,
                key_row.min_request_interval_ms,
            )
            continue

        # 拿到 slot
        rate_limited_all = False
        result = await _try_internal_call(
            client_factory=client_factory,
            key_row=key_row,
            payload=payload,
            request_log=request_log,
            started=started,
            department_uid=department_uid,
            project_uid=project_uid,
            user_uid=user_uid,
            model=model,
            model_uid=model_uid,
        )
        if result is not None:
            return result
        # _try_internal_call 已記 log;繼續換下一把
        last_err = AppError("internal_unavailable", code=502)

    # Phase 2:全撞牆 → 隨機選一把 wait
    if rate_limited_all and keys:
        chosen = random.choice(keys)
        limiter = await get_limiter(("INTERNAL", chosen.internal_key_uid))
        try:
            await limiter.acquire(
                rpm_limit=chosen.rpm_limit,
                min_interval_ms=chosen.min_request_interval_ms,
                wait_timeout=float(settings.INTERNAL_LLM_RATE_WAIT_TIMEOUT),
            )
        except RateLimitExceeded as exc:
            latency_ms = int((time.monotonic() - started) * 1000)
            schedule_usage_log(
                department_uid=department_uid,
                project_uid=project_uid,
                user_uid=user_uid,
                openrouter_key_uid=None,
                model=model,
                model_uid=model_uid,
                resp=None,
                latency_ms=latency_ms,
                status="error",
                error_code="internal_busy",
                request_log=request_log,
            )
            raise AppError(
                "internal_busy",
                code=429,
                data={"retry_after_seconds": exc.retry_after_seconds},
            ) from exc

        # wait 到了 slot,嘗試呼叫
        result = await _try_internal_call(
            client_factory=client_factory,
            key_row=chosen,
            payload=payload,
            request_log=request_log,
            started=started,
            department_uid=department_uid,
            project_uid=project_uid,
            user_uid=user_uid,
            model=model,
            model_uid=model_uid,
        )
        if result is not None:
            return result

    # 全失敗(且不全是速率因素 / 或 Phase 2 也失敗)
    raise AppError("internal_unavailable", code=502) from last_err


async def _try_internal_call(
    *,
    client_factory: ChatClientFactory,
    key_row: InternalKey,
    payload: dict[str, Any],
    request_log: dict[str, Any],
    started: float,
    department_uid: UUID,
    project_uid: UUID,
    user_uid: UUID,
    model: str,
    model_uid: UUID,
) -> str | None:
    """用單一 Key 嘗試呼叫;成功 → 寫 success log + 回純文字內容;
    失敗 → 記 log + 回 None(供呼叫端決定 failover 或 abort)。

    InternalAuthError / RateLimit / Unavailable 都當成「換下一把」可接受。

    Args:
        client_factory: HTTP client 工廠。
        key_row: 本次嘗試使用的 internal_key 資料列。
        payload: 已重組好的 `/chat/completions` payload。
        request_log: 請求快照,寫入 usage_logs 用。
        started: 本次請求起算的 time.monotonic() 起點,用於算 latency。
        department_uid: 呼叫者部門 uid(記帳用)。
        project_uid: 呼叫者專案 uid(記帳用)。
        user_uid: 呼叫者使用者 uid(記帳用)。
        model: 使用者指定的 model_key。
        model_uid: 對應的 Model 主鍵。

    Returns:
        成功時回模型回應的純文字內容;失敗(可 failover)時回 None。
    """
    try:
        resp_body = await _internal_call_once(
            client_factory=client_factory, key_row=key_row, payload=payload
        )
    except InternalAuthError:
        logger.warning("Internal Key uid=%s 401;檢查 api_key", key_row.internal_key_uid)
        return None
    except InternalRateLimitError:
        # server 端 429:這把當前過載,記 log 但讓上層繼續試其他 key
        logger.warning("Internal Key uid=%s server-side 429", key_row.internal_key_uid)
        return None
    except (InternalUnavailableError, InternalError):
        logger.exception("Internal Key uid=%s 呼叫失敗", key_row.internal_key_uid)
        return None

    # 成功
    latency_ms = int((time.monotonic() - started) * 1000)
    schedule_usage_log(
        department_uid=department_uid,
        project_uid=project_uid,
        user_uid=user_uid,
        openrouter_key_uid=None,
        model=model,
        model_uid=model_uid,
        resp=resp_body,
        latency_ms=latency_ms,
        status="success",
        error_code=None,
        request_log=request_log,
    )
    return _extract_content(resp_body)


async def run_chat_stream(
    db: AsyncSession,
    *,
    client_factory: ChatClientFactory,
    department_uid: UUID,
    project_uid: UUID,
    user_uid: UUID,
    model: str,
    text: str | None,
    images: list[str] | None,
    videos: list[str] | None,
    tools: list[dict[str, Any]] | None = None,
    files: list[dict[str, str]] | None = None,
    messages: list[ChatMessage] | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    response_format: ResponseFormat | None = None,
) -> AsyncIterator[str]:
    """串流版 chat 代理(v1.7;僅 OpenRouter)。

    與 `run_chat` 對應,但回應改以 SSE 串流逐 chunk 回傳。白名單 / provider 檢查在
    「吐出第一個 chunk 之前」完成,失敗以 AppError 拋出(由端點轉成 ApiResponse,
    不開串流;對齊 docs/Design-Base/50-openrouter.md § 7)。

    本版本串流**僅支援** provider=openrouter;internal 模型回 400 feature_not_supported。

    v2.1.2 起支援 messages 直傳模式與生成參數,payload 組裝與 `run_chat` 共用
    `_rewrite_request`(串流僅多 `stream` / `stream_options` 注入,現況不變)。

    Args:
        db: 本次 request 的 DB session。
        client_factory: HTTP client 工廠。
        department_uid: 呼叫者部門 uid。
        project_uid: 呼叫者專案 uid。
        user_uid: 呼叫者使用者 uid。
        model: 使用者指定的 model_key(須通過白名單)。
        text: 文字輸入,可為 None(單輪模式)。
        images: 圖片 URL / data URI 清單,可為 None(單輪模式)。
        videos: 影片清單;本版本不支援,非空即 400。
        tools: 可選工具清單,原樣透傳。
        files: 上傳檔案清單(filename / file_data),如 PDF;用量紀錄僅留檔名。
        messages: messages 直傳模式的多輪訊息(與 text/images/files 互斥);
            schema 驗證後原樣透傳;用量紀錄 file part 僅留檔名。
        temperature: 生成溫度(0-2);None 不注入 payload,走模型預設。
        max_tokens: 回覆 token 上限(≥1);None 不注入 payload,走模型預設。
        response_format: 型別化回覆格式(json_object / json_schema);None 不注入。

    Yields:
        OpenRouter SSE 字串(已含換行框架),可直接寫入 text/event-stream 回應。

    Raises:
        AppError: feature_not_supported(400,影片 / internal)、model_forbidden(403)、
            model_not_found(404)、rate_limited(429)、openrouter_unavailable(502);
            均於吐出第一個 chunk 之前拋出。
    """
    if videos:
        raise AppError("feature_not_supported", code=400)
    model_row = await _check_model_whitelist(db, model)
    if model_row.provider != "openrouter":
        # 本版本串流僅支援 OpenRouter;internal 串流留待後續版本。
        raise AppError("feature_not_supported", code=400)

    payload = _rewrite_request(
        model,
        text,
        images,
        tools,
        files,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format=response_format,
    )
    payload["stream"] = True
    # 確保最後一個 chunk 帶 usage,供記帳;對 SDK 為 OpenAI 標準欄位,透明無害。
    payload["stream_options"] = {"include_usage": True}
    request_log = _build_request_log(
        model,
        text,
        images,
        tools,
        files,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format=response_format,
    )

    async for chunk in _stream_openrouter(
        db,
        client_factory=client_factory,
        model_row=model_row,
        department_uid=department_uid,
        project_uid=project_uid,
        user_uid=user_uid,
        payload=payload,
        request_log=request_log,
    ):
        yield chunk


async def _stream_openrouter(
    db: AsyncSession,
    *,
    client_factory: ChatClientFactory,
    model_row: Model,
    department_uid: UUID,
    project_uid: UUID,
    user_uid: UUID,
    payload: dict[str, Any],
    request_log: dict[str, Any],
) -> AsyncIterator[str]:
    """OpenRouter 串流流程 — Key failover 在「收到第一個 chunk 之前」完成。

    連上(收到第一個 chunk)即為 commit point,之後進入不可重試的 relay 階段:
    逐行原樣轉發 OpenRouter SSE,同時累積 content / usage 供記帳;串流結束、中途
    出錯或呼叫端斷線,皆於 finally 寫入一筆 usage_logs。

    Args:
        db: 本次 request 的 DB session(僅 commit point 前使用)。
        client_factory: HTTP client 工廠。
        model_row: 已通過白名單的 Model 資料列。
        department_uid: 呼叫者部門 uid(決定可用 Key 範圍)。
        project_uid: 呼叫者專案 uid(記帳用)。
        user_uid: 呼叫者使用者 uid(記帳用)。
        payload: 已含 stream=True 的 `/chat/completions` payload。
        request_log: 請求快照,寫入 usage_logs 用。

    Yields:
        OpenRouter SSE 字串(已含換行框架)。

    Raises:
        AppError: model_not_found / model_forbidden / rate_limited / openrouter_unavailable;
            均於吐出第一個 chunk 之前拋出。
    """
    client = client_factory.openrouter()
    model = payload["model"]
    model_uid = model_row.model_uid

    last_err: Exception | None = None
    rate_limited_all = True
    started = time.monotonic()

    agen: AsyncIterator[str] | None = None
    first_line: str | None = None
    key_uid: UUID | None = None

    def _log_error(error_code: str, *, key: UUID | None) -> None:
        schedule_usage_log(
            department_uid=department_uid,
            project_uid=project_uid,
            user_uid=user_uid,
            openrouter_key_uid=key,
            model=model,
            model_uid=model_uid,
            resp=None,
            latency_ms=int((time.monotonic() - started) * 1000),
            status="error",
            error_code=error_code,
            request_log=request_log,
        )

    # --- Phase 1:Key failover,直到成功連上(收到第一個 chunk)---
    # 迴圈外查一次 active key,記憶體內 shuffle 後依序取(最多 _MAX_RETRIES 把),
    # 對齊 internal 路徑,避免每圈重查整張表。
    keys = await OpenRouterKeyRepository(db).list_active_by_department(department_uid)
    for key_row in random.sample(keys, len(keys))[:_MAX_RETRIES]:

        limiter = await get_limiter(key_row.openrouter_key_uid)
        try:
            await limiter.acquire(
                rpm_limit=key_row.rpm_limit,
                min_interval_ms=key_row.min_request_interval_ms,
                wait_timeout=0,
            )
        except RateLimitExceeded:
            logger.warning(
                "OR 串流 Key uid=%s 速率限制;切下一把", key_row.openrouter_key_uid
            )
            continue

        # 拿到 slot 後,後續失敗皆視為「實際打過 OR」,不再全 rate_limited
        rate_limited_all = False

        try:
            raw_key = decrypt_key(key_row)
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            logger.exception("OpenRouter Key 解密失敗:%s", key_row.openrouter_key_uid)
            continue

        candidate = client.stream_chat_completion(payload, api_key=raw_key)
        try:
            first_line = await candidate.__anext__()
        except StopAsyncIteration:
            # 上游直接結束、無任何 chunk:視為成功但空輸出
            first_line = None
            agen = candidate
            key_uid = key_row.openrouter_key_uid
            break
        except OpenRouterAuthError as exc:
            last_err = exc
            await candidate.aclose()
            schedule_key_cooldown(key_row.openrouter_key_uid)  # 401 失效 → 短期停用
            logger.warning("OR 串流 401;切換下一把 Key")
            continue
        except OpenRouterModelNotFoundError as exc:
            await candidate.aclose()
            _log_error("model_not_found", key=key_row.openrouter_key_uid)
            raise AppError("model_not_found", code=404) from exc
        except OpenRouterForbiddenError as exc:
            await candidate.aclose()
            _log_error("model_forbidden", key=key_row.openrouter_key_uid)
            raise AppError("model_forbidden", code=403) from exc
        except OpenRouterRateLimitError as exc:
            await candidate.aclose()
            _log_error("rate_limited", key=key_row.openrouter_key_uid)
            raise AppError("rate_limited", code=429) from exc
        except OpenRouterError as exc:
            last_err = exc
            await candidate.aclose()
            if exc.status == 402:
                schedule_key_cooldown(key_row.openrouter_key_uid)  # 402 餘額不足 → 短期停用
            logger.exception("OR 串流其他錯誤;嘗試下一把")
            continue

        # 成功連上 = commit point
        agen = candidate
        key_uid = key_row.openrouter_key_uid
        break

    # --- 全部失敗(未連上):pre-stream 回絕,轉成 ApiResponse ---
    if agen is None:
        error_code = "rate_limited" if rate_limited_all else "openrouter_unavailable"
        code = 429 if rate_limited_all else 502
        _log_error(error_code, key=None)
        raise AppError(error_code, code=code) from last_err

    # --- Phase 2:relay(不可重試)---
    state: dict[str, Any] = {"parts": [], "usage": None, "id": None}
    status = "error"
    error_code: str | None = "stream_incomplete"  # 預設涵蓋呼叫端中途斷線
    try:
        if first_line is not None:
            out = _simplify_sse_line(first_line, state)
            if out is not None:
                yield out
        async for line in agen:
            out = _simplify_sse_line(line, state)
            if out is not None:
                yield out
        # OpenRouter 中途回報 error chunk 時 _simplify 會標記 state["error"]
        if state.get("error"):
            status = "error"
            error_code = "openrouter_unavailable"
        else:
            status = "success"
            error_code = None
    except OpenRouterError as exc:
        # 後端側無預警斷線:不靜默截斷,補送 error chunk 後收尾(對齊 § 7)
        last_err = exc
        error_code = "openrouter_unavailable"
        logger.exception("OR 串流中途失敗")
        yield 'data: {"error":"openrouter_unavailable"}\n\n'
        yield "data: [DONE]\n\n"
    except Exception as exc:  # noqa: BLE001
        # 非 OpenRouterError(逾時 / 連線中斷等)同樣不靜默截斷,補送收尾,避免 SSE 客戶端 hang。
        # CancelledError 屬 BaseException 不會落此分支;呼叫端斷線交由 finally 記帳後自然傳播。
        last_err = exc
        error_code = "stream_incomplete"
        logger.exception("串流中途非預期失敗")
        yield 'data: {"error":"stream_incomplete"}\n\n'
        yield "data: [DONE]\n\n"
    finally:
        try:
            await agen.aclose()
        except Exception:  # noqa: BLE001 - 上游已壞時 aclose 可能拋例外,不可蓋掉下方記帳
            logger.exception("串流 aclose 失敗")
        resp = _stream_state_to_resp(state)
        schedule_usage_log(
            department_uid=department_uid,
            project_uid=project_uid,
            user_uid=user_uid,
            openrouter_key_uid=key_uid,
            model=model,
            model_uid=model_uid,
            resp=resp,
            latency_ms=int((time.monotonic() - started) * 1000),
            status=status,
            error_code=error_code,
            request_log=request_log,
        )
