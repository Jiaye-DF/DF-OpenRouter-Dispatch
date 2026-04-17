from fastapi import APIRouter, Depends

from app.core.deps import AdminDep
from app.core.response import success_response

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", summary="Health check")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/openrouter", summary="OpenRouter 通路檢查（admin）")
async def openrouter_health(actor: AdminDep):
    return success_response(data={"status": "ok"}, detail="success")
