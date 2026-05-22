from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.back_channel import router as back_channel_router
from app.api.v1 import api_v1_router
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging, flush_logging, get_logger
from app.core.response import failure_response
from app.seed import run_seed

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    try:
        await run_seed()
    except Exception:
        logger.exception("Seed 失敗；服務繼續啟動，請檢查資料庫與 .env。")
    yield
    flush_logging()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="DF-OpenRouter-Dispatch API",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(AppError)
    async def _app_error_handler(_: Request, exc: AppError):
        return failure_response(exc.code, exc.detail, exc.data)

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(_: Request, exc: RequestValidationError):
        errs = exc.errors()
        if errs:
            first = errs[0]
            loc = ".".join(str(x) for x in first.get("loc", []) if x != "body")
            msg = first.get("msg", "invalid")
            detail = f"欄位 {loc} {msg}" if loc else msg
        else:
            detail = "invalid_input"
        return failure_response(400, detail)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        logger.exception("Unhandled exception: %s", exc)
        return failure_response(500, "操作失敗")

    app.include_router(api_v1_router, prefix="/api/v1")
    # DF-SSO back-channel logout:路徑由中央寫死,需掛在 /api/auth(非 /api/v1)。
    app.include_router(back_channel_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
