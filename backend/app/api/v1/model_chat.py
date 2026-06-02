"""Chat 代理端點(v1.2)。

對齊 docs/Tasks/v1.2/propose-v1.2.0.md § 7.1。

- 新 canonical:`POST /api/v1/model/chat`(所有 provider 共用)
- Deprecated alias:`POST /api/v1/model/openrouter/chat`(內部 forward 到同 handler;至少保留到 v1.4)
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.clients.factory import ChatClientFactory, get_chat_client_factory
from app.core.deps import DbDep, SdkCallerDep
from app.core.response import success_response
from app.schemas.model import ChatRequest
from app.services.proxy import run_chat

router = APIRouter(prefix="/model", tags=["model-chat"])
deprecated_router = APIRouter(prefix="/model/openrouter", tags=["model-chat (deprecated)"])

ClientFactoryDep = Annotated[ChatClientFactory, Depends(get_chat_client_factory)]


async def _chat_handler(
    body: ChatRequest,
    caller: SdkCallerDep,
    db: DbDep,
    client_factory: ClientFactoryDep,
):
    """canonical 與 deprecated 兩端點共用的實際處理邏輯。

    把 HTTP 層的依賴拆解後轉交 service 層 `run_chat`,本身不含商業邏輯。

    Args:
        body: 已驗證的請求 body(model / text / images / videos / tools)。
        caller: 由 SDK Key 解析出的呼叫者身分(department / project / user uid),
            用於白名單、速率限制歸戶與 usage_logs 記帳。
        db: 本次 request 的 DB session。
        client_factory: 產生 OpenRouter / internal HTTP client 的工廠。

    Returns:
        包成統一格式的成功回應,data 為模型回應的純文字內容。
    """
    data = await run_chat(
        db,
        client_factory=client_factory,
        department_uid=caller.department_uid,
        project_uid=caller.project_uid,
        user_uid=caller.user_uid,
        model=body.model,
        text=body.text,
        images=body.images,
        videos=body.videos,
        tools=body.tools,
    )
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
