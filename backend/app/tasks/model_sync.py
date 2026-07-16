"""模型自動同步排程 task(task-502;對齊 propose-v2.2 §B.1 / §D.1-3)。

`scheduled_sync_models`:scheduler 週期觸發,每 N 天 00:00 自動呼叫既有
`sync_models_and_credits(...)` 同步 OpenRouter 模型清單;以 `trigger="scheduler"`
稽核標記區分排程 vs 手動。

- `MODEL_SYNC_SCHEDULE_ENABLED` 為 false → 直接 return(不同步),對齊
  `dispatch_unevaluated` 的短路。
- 系統 actor 以 `INITIAL_ADMIN_ACCOUNT` 反查;查無 → log warning 後 return。
- 節流 / 鎖:`sync_models_and_credits` 拋 `AppError` 且 key ∈
  {"sync_throttled", "sync_in_progress"} → log info 後靜默略過(不 re-raise);
  其他例外照拋,交 taskiq 依 broker 的 `SimpleRetryMiddleware` 重試。

CI-importability:cron 排程標籤需在 broker 註冊 task 的當下定型,故於模組載入時
讀取 `_INTERVAL_DAYS`。為與 `ai_model_eval.py` / `broker.py` 一致(讓本模組能在
「未備妥完整 .env」的 worker / CI 情境被 import),此標籤值**直讀 `os.environ`**
(預設值與 `app/core/config.py` 對應欄位逐字一致),而非 `get_settings()`;
函式執行時(worker 有完整 .env)仍走 `get_settings()`。
"""

from __future__ import annotations

import os

import httpx

from app.clients.openrouter.client import OpenRouterClient
from app.core.config import coerce_int_env, get_settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.repositories.user import UserRepository
from app.services.sync import sync_models_and_credits
from app.tasks.broker import broker

logger = get_logger(__name__)

# 預設值與 app/core/config.py 的 Settings 對應欄位逐字一致(見 docstring「CI-importability」)。
# cron 排程標籤需在 import 時定型,無法走 get_settings()(裸環境無完整 .env),故直讀 os.environ。
_INTERVAL_DAYS = coerce_int_env(
    "MODEL_SYNC_INTERVAL_DAYS", os.environ.get("MODEL_SYNC_INTERVAL_DAYS"), 3
)

# 節流 / 鎖類 AppError:排程觸發時屬預期情形(手動同步剛跑過 / 併發),靜默略過不重試。
_THROTTLE_KEYS = {"sync_throttled", "sync_in_progress"}


@broker.task(schedule=[{"cron": f"0 0 */{_INTERVAL_DAYS} * *"}])
async def scheduled_sync_models() -> None:
    """scheduler 端:每 N 天 00:00 自動同步 OpenRouter 模型 + 餘額。

    以 `@broker.task(schedule=[{"cron": "0 0 */N * *"}])` 帶排程標籤,供 scheduler 的
    `LabelScheduleSource` 依 cron 觸發。自建 DB session + `OpenRouterClient`,以系統
    admin 作為 actor 呼叫既有 `sync_models_and_credits`,並帶 `trigger="scheduler"`
    稽核標記。

    Raises:
        Exception: 節流 / 併發鎖類 `AppError` 靜默略過;其他 `AppError` / DB / 網路等
            非預期錯誤照拋,交由 taskiq 依 max_retries 重試。
    """
    settings = get_settings()
    if not settings.MODEL_SYNC_SCHEDULE_ENABLED:
        logger.debug("模型自動同步略過:MODEL_SYNC_SCHEDULE_ENABLED=false")
        return

    # 延遲 import:app.core.database 於 import 時即 get_settings()(需完整 .env);
    # 放進函式體保留本模組的 CI-importability(見模組 docstring)。
    from app.core.database import SessionLocal

    async with SessionLocal() as db:
        admin = await UserRepository(db).get_by_account(settings.INITIAL_ADMIN_ACCOUNT)
        if admin is None:
            logger.warning(
                "模型自動同步略過:找不到系統 admin(INITIAL_ADMIN_ACCOUNT=%s)",
                settings.INITIAL_ADMIN_ACCOUNT,
            )
            return

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(settings.OPENROUTER_API_TIMEOUT),
        ) as http_client:
            client = OpenRouterClient(http_client, settings.OPENROUTER_API_BASE_URL)
            try:
                await sync_models_and_credits(
                    db,
                    client,
                    actor_user_uid=admin.user_uid,
                    actor_role=admin.role,
                    ip=None,
                    audit_meta={"trigger": "scheduler"},
                )
            except AppError as exc:
                # AppError 的 key 存於 `detail`(見 app/core/exceptions.py)。
                if exc.detail in _THROTTLE_KEYS:
                    logger.info(
                        "模型自動同步略過:%s(節流 / 併發鎖,不重試)", exc.detail
                    )
                    return
                raise
        # sync_models_and_credits 內部已 commit;此處再 commit 為 no-op 安全冪等,
        # 對齊 evaluate_usage_log_task「session 擁有者負責 commit」慣例。
        await db.commit()
