from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.deps import AdminDep, DbDep
from app.core.logging import get_logger
from app.core.response import success_response

logger = get_logger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", summary="Health check")
async def health(db: DbDep) -> JSONResponse:
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Health check：DB 連線失敗")
        return JSONResponse(status_code=503, content={"status": "down", "db": "down"})
    return JSONResponse(content={"status": "ok", "db": "ok"})


@router.get("/openrouter", summary="OpenRouter 通路檢查（admin）")
async def openrouter_health(actor: AdminDep):
    return success_response(data={"status": "ok"}, detail="success")
