"""Chat 代理端點(v1.2)。

對齊 docs/Tasks/v1.2/propose-v1.2.0.md § 7.1。

- 新 canonical:`POST /api/v1/model/chat`(所有 provider 共用)
- Deprecated alias:`POST /api/v1/model/openrouter/chat`(內部 forward 到同 handler;至少保留到 v1.4)
"""

from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.clients.factory import ChatClientFactory, get_chat_client_factory
from app.core.deps import DbDep, SdkCallerDep
from app.core.response import success_response
from app.schemas.model import ChatRequest
from app.services.proxy import run_chat, run_chat_stream

router = APIRouter(prefix="/model", tags=["model-chat"])
deprecated_router = APIRouter(prefix="/model/openrouter", tags=["model-chat (deprecated)"])

ClientFactoryDep = Annotated[ChatClientFactory, Depends(get_chat_client_factory)]


def _chat_kwargs(body: ChatRequest, caller: SdkCallerDep) -> dict[str, Any]:
    """把已驗證的 body + caller 攤成 `run_chat` / `run_chat_stream` 的共用 kwargs。

    兩個 service fn 的簽章一致,非串流 / 串流 / deprecated alias 三條路徑共用同一份轉發,
    新增 ChatRequest 欄位時只需改這裡一處(避免漏改導致某條路徑靜默丟參數)。
    """
    return {
        "department_uid": caller.department_uid,
        "project_uid": caller.project_uid,
        "user_uid": caller.user_uid,
        "model": body.model,
        "text": body.text,
        "images": body.images,
        "videos": body.videos,
        "tools": body.tools,
        "files": [f.model_dump() for f in body.files] if body.files else None,
        "messages": body.messages,
        "temperature": body.temperature,
        "max_tokens": body.max_tokens,
        "response_format": body.response_format,
    }


async def _chat_handler(
    body: ChatRequest,
    caller: SdkCallerDep,
    db: DbDep,
    client_factory: ClientFactoryDep,
):
    """canonical 與 deprecated 兩端點共用的實際處理邏輯。

    把 HTTP 層的依賴拆解後轉交 service 層 `run_chat`,本身不含商業邏輯。

    Args:
        body: 已驗證的請求 body(model / text / images / files / videos / tools;
            v2.1.2 起另含 messages 直傳模式與生成參數 temperature / max_tokens /
            response_format,互斥 / 白名單驗證均由 `ChatRequest` schema 層完成)。
        caller: 由 SDK Key 解析出的呼叫者身分(department / project / user uid),
            用於白名單、速率限制歸戶與 usage_logs 記帳。
        db: 本次 request 的 DB session。
        client_factory: 產生 OpenRouter / internal HTTP client 的工廠。

    Returns:
        包成統一格式的成功回應,data 為模型回應的純文字內容。
    """
    data = await run_chat(db, client_factory=client_factory, **_chat_kwargs(body, caller))
    return success_response(data=data, detail="success")


@router.post("/chat", summary="Chat 代理(canonical;依模型 provider 自動分流)")
async def chat(
    body: ChatRequest,
    caller: SdkCallerDep,
    db: DbDep,
    client_factory: ClientFactoryDep,
):
    """canonical 端點:`POST /api/v1/model/chat`,所有 provider 共用。

    參數意義同 `_chat_handler`;此處僅作路由註冊,實作轉交該 handler。
    """
    return await _chat_handler(body, caller, db, client_factory)


@router.post(
    "/chat/stream",
    summary="Chat 代理(串流;SSE,僅 OpenRouter)",
)
async def chat_stream(
    body: ChatRequest,
    caller: SdkCallerDep,
    db: DbDep,
    client_factory: ClientFactoryDep,
):
    """串流端點:`POST /api/v1/model/chat/stream`。

    回應為 **SSE(`text/event-stream`)**,逐 chunk 解析後**簡化**為僅含
    `{id, content}` 再轉發(`data: {"id":"...","content":"..."}\\n\\n` … `data: [DONE]`;
    OpenRouter 內部欄位不外露),**不**套統一 ApiResponse 包裝
    (對齊 docs/Design-Base/50-openrouter.md § 7)。

    開串流前的錯誤(驗證 / 白名單 / provider=internal / Key 全失敗)仍以 HTTP
    4xx/5xx + ApiResponse 回絕,不開串流;開串流後不重試,呼叫端斷線即取消上游。
    本版本串流僅支援 provider=openrouter;internal 模型回 400 feature_not_supported。

    參數意義同 `_chat_handler`(body / caller / db / client_factory)。
    """
    agen = run_chat_stream(db, client_factory=client_factory, **_chat_kwargs(body, caller))

    # 先 prime 一次:開串流前的 AppError 於此拋出,由 exception handler 轉 ApiResponse
    # (此時尚未送出 200 與 SSE);成功取得第一個 chunk 後才真正開啟串流。
    try:
        first = await agen.__anext__()
    except StopAsyncIteration:
        # 上游無任何內容:回一個僅含 [DONE] 的空串流
        async def _empty() -> AsyncIterator[str]:
            yield "data: [DONE]\n\n"

        return StreamingResponse(_empty(), media_type="text/event-stream")

    async def _body() -> AsyncIterator[str]:
        yield first
        async for chunk in agen:
            yield chunk

    return StreamingResponse(
        _body(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@deprecated_router.post(
    "/chat",
    summary="[Deprecated] OpenRouter Chat 代理 — 請改用 /api/v1/model/chat",
    deprecated=True,
)
async def chat_deprecated(
    body: ChatRequest,
    caller: SdkCallerDep,
    db: DbDep,
    client_factory: ClientFactoryDep,
):
    """[Deprecated] 舊端點:`POST /api/v1/model/openrouter/chat`。

    內部直接 forward 到同一 handler,行為與 canonical 完全一致;至少保留到 v1.4。
    參數意義同 `_chat_handler`。
    """
    return await _chat_handler(body, caller, db, client_factory)
