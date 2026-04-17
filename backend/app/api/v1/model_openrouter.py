from typing import Annotated

from fastapi import APIRouter, Depends

from app.clients.openrouter.client import OpenRouterClient, get_openrouter_client
from app.core.deps import DbDep, SdkCallerDep
from app.core.response import success_response
from app.schemas.model import ChatRequest
from app.services.proxy import run_chat

router = APIRouter(prefix="/model/openrouter", tags=["model-openrouter"])


@router.post("/chat", summary="OpenRouter Chat 代理")
async def chat(
    body: ChatRequest,
    caller: SdkCallerDep,
    db: DbDep,
    client: Annotated[OpenRouterClient, Depends(get_openrouter_client)],
):
    data = await run_chat(
        db,
        client=client,
        department_uid=caller.department_uid,
        user_uid=caller.user_uid,
        model=body.model,
        text=body.text,
        images=body.images,
        videos=body.videos,
    )
    return success_response(data=data, detail="success")
