from fastapi import APIRouter

from app.api.v1 import (
    auth,
    departments,
    health,
    internal_keys,
    model_chat,
    model_tiers,
    models,
    openrouter_keys,
    projects,
    sdk_keys,
    stats,
    usage_logs,
    user_tokens,
    users,
)

api_v1_router = APIRouter()
api_v1_router.include_router(auth.router)
api_v1_router.include_router(users.router)
api_v1_router.include_router(user_tokens.router)
api_v1_router.include_router(departments.router)
api_v1_router.include_router(projects.router)
api_v1_router.include_router(openrouter_keys.router)
api_v1_router.include_router(internal_keys.router)
api_v1_router.include_router(sdk_keys.router)
api_v1_router.include_router(model_chat.router)             # canonical: /model/chat
api_v1_router.include_router(model_chat.deprecated_router)  # alias: /model/openrouter/chat
api_v1_router.include_router(models.router)
api_v1_router.include_router(models.allowed_router)  # 公開精簡清單: /allowed/models
api_v1_router.include_router(model_tiers.router)
api_v1_router.include_router(usage_logs.router)
api_v1_router.include_router(stats.router)
api_v1_router.include_router(health.router)
