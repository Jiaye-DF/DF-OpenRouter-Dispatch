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
    data = await run_chat(
        db,
        client_factory=client_factory,
        department_uid=caller.department_uid,
        user_uid=caller.user_uid,
        model=body.model,
        text=body.text,
        images=body.images,
        videos=body.videos,
    )
    return success_response(data=data, detail="success")


@router.post("/chat", summary="Chat 代理(canonical;依模型 provider 自動分流)")
async def chat(
    body: ChatRequest,
    caller: SdkCallerDep,
    db: DbDep,
    client_factory: ClientFactoryDep,
):
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
    return await _chat_handler(body, caller, db, client_factory)
