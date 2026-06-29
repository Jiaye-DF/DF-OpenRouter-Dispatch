"""模型適配評審 taskiq task + dispatcher(task-106;對齊 propose-v2.0.1 §4)。

兩個對外名(Acceptance 指定):

- `evaluate_usage_log_task`:`@broker.task` worker 端消費單筆評審。
  經 broker 只能序列化基本型別,故簽名只收 `usage_log_uid` 字串;worker 內自建
  DB session(`SessionLocal`)+ `OpenRouterClient`,再呼叫 task-105
  `evaluate_usage_log`。失敗自動重試(`retry_on_error` + `max_retries` 讀
  `AI_EVAL_TASK_MAX_RETRIES`,配合 broker 的 `SimpleRetryMiddleware`);
  「部分評審失敗」由 service 自行收斂、不丟例外、不觸發重試,只有 DB / 網路等
  非預期錯誤才 raise → 由 taskiq 重試;重試超限後評審全失敗的終局由 service
  落 `status='error'` + `ai_evaluated_status=0`(task-105 已實作)。

- `dispatch_unevaluated`:scheduler 週期觸發,撈待評審筆逐筆 `.kiq` 派發。
  `AI_EVAL_ENABLED` 為 false → 直接 return,不派發。

冪等:父表 `usage_log_uid` UNIQUE(task-104)保證不重複評審;task 端在呼叫
service 前先以 repo 檢查父表是否已存在(含軟刪)→ 已存在則短路跳過,避免重複
投遞 / 重試時重打 3 次 OpenRouter,純省 API 成本。**不**在 dispatch 時以
`ai_evaluated_at` 搶佔(該欄為 worker 完成時寫的實際執行時間,搶寫會破壞
NULL/0/1 游標語意)。

CI-importability:task 標籤(`max_retries` / 排程 `interval`)需在 broker 註冊
task 的當下定型,故於模組載入時讀取。為與 `broker.py` 一致(讓本模組能在「未備妥
完整 .env」的 worker / CI 情境被 import,不被無關欄位驗證牽連),此兩個標籤值
**直讀 `os.environ`**(預設值與 `app/core/config.py` 對應欄位逐字一致),而非
`get_settings()`;函式執行時(worker 有完整 .env)仍走 `get_settings()`。
"""

from __future__ import annotations

import os
from uuid import UUID

import httpx
from sqlalchemy import select

from app.clients.openrouter.client import OpenRouterClient
from app.core.config import coerce_int_env, get_settings
from app.core.logging import get_logger
from app.models.ai_model_evaluation import AiModelEvaluation
from app.repositories.ai_model_evaluation import AiModelEvaluationRepository
from app.services.ai_model_eval import evaluate_usage_log
from app.services.ai_model_eval_rerun import rerun_evaluation
from app.tasks.broker import broker

logger = get_logger(__name__)

# 預設值與 app/core/config.py 的 Settings 對應欄位逐字一致(見 docstring「CI-importability」)。
# task 標籤需在 import 時定型,無法走 get_settings()(裸環境無完整 .env),故直讀 os.environ;
# 容錯(空 → 預設;壞值 → 明確 log 後正常退出)與 Settings 共用 coerce_int_env,語意一致。
_MAX_RETRIES = coerce_int_env("AI_EVAL_TASK_MAX_RETRIES", os.environ.get("AI_EVAL_TASK_MAX_RETRIES"), 3)
_BEAT_INTERVAL = coerce_int_env(
    "AI_EVAL_BEAT_INTERVAL_SECONDS", os.environ.get("AI_EVAL_BEAT_INTERVAL_SECONDS"), 300
)


@broker.task(retry_on_error=True, max_retries=_MAX_RETRIES)
async def evaluate_usage_log_task(usage_log_uid: str) -> None:
    """worker 端:對單筆 usage_log 跑三評審並回寫。

    自建 DB session + OpenRouterClient,呼叫 task-105 service。呼叫前先以 repo
    檢查父表是否已存在該 usage_log_uid(含軟刪)→ 已存在則短路跳過(省 API 成本)。

    Args:
        usage_log_uid: 待評審的 usage_logs.usage_log_uid(序列化為字串)。

    Raises:
        Exception: service 對「部分評審失敗」不拋;DB / 網路等非預期錯誤才會冒出,
            交由 taskiq SimpleRetryMiddleware 依 max_retries 重試。
    """
    # 延遲 import:app.core.database 於 import 時即 get_settings()(需完整 .env);
    # 放進函式體保留本模組的 CI-importability(見模組 docstring)。
    from app.core.database import SessionLocal

    uid = UUID(usage_log_uid)
    settings = get_settings()

    async with SessionLocal() as db:
        # 父表已存在(含軟刪)→ 已評審過,短路跳過,不重打 OpenRouter。
        existing = await AiModelEvaluationRepository(
            db
        ).find_by_usage_log_uid_including_deleted(uid)
        if existing is not None:
            logger.info(
                "模型適配評審略過:父表已存在(冪等短路) usage_log_uid=%s", uid
            )
            return

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(settings.OPENROUTER_API_TIMEOUT),
        ) as http_client:
            client = OpenRouterClient(http_client, settings.OPENROUTER_API_BASE_URL)
            await evaluate_usage_log(uid, db=db, client=client)
        # session 擁有者負責 commit(沿用專案慣例,見 services/proxy.py)。
        # service 內的回寫只 flush 進當前 transaction,未 commit;此處不 commit
        # 則 SessionLocal 結束時會 rollback,評審結果不落地。
        await db.commit()


@broker.task(schedule=[{"interval": _BEAT_INTERVAL}])
async def dispatch_unevaluated() -> int:
    """掃待評審 usage log 逐筆派進 broker;回傳實際派發筆數。

    以 `@broker.task(schedule=[{"interval": AI_EVAL_BEAT_INTERVAL_SECONDS}])` 帶
    排程標籤,供 scheduler 的 `LabelScheduleSource` 每隔此秒數觸發一次。

    - `AI_EVAL_ENABLED` 為 false → 直接 return 0(不派發)。
    - 為真 → 自建 session,`fetch_unevaluated_log_uids(AI_EVAL_DISPATCH_BATCH_SIZE)`
      撈待派,逐筆 `await evaluate_usage_log_task.kiq(str(uid))`。

    防重複派發:依賴 task 端父表短路 + 父表 UNIQUE 冪等,不在此搶佔游標。
    """
    settings = get_settings()
    if not settings.AI_EVAL_ENABLED:
        logger.debug("AI 評審派發略過:AI_EVAL_ENABLED=false")
        return 0

    from app.core.database import SessionLocal  # 延遲 import,見模組 docstring

    async with SessionLocal() as db:
        uids = await AiModelEvaluationRepository(db).fetch_unevaluated_log_uids(
            settings.AI_EVAL_DISPATCH_BATCH_SIZE,
            start_at=settings.ai_eval_start_at_dt,
        )

    for uid in uids:
        await evaluate_usage_log_task.kiq(str(uid))

    logger.info("AI 評審派發完成:派發 %d 筆", len(uids))
    return len(uids)


@broker.task(retry_on_error=True, max_retries=_MAX_RETRIES)
async def rerun_evaluation_task(ai_evaluation_uid: str) -> None:
    """worker 端:對單筆父評審跑真實重跑 + 對比裁決並回寫(task-406;propose-v2.1.0 §5.1)。

    自建 DB session + OpenRouterClient,呼叫 task-405 `rerun_evaluation`。呼叫前先以
    repo 檢查父評審 `ai_reran_at` 是否已非 NULL(已重跑過)→ 已重跑則短路跳過(省 API
    成本;對齊 `evaluate_usage_log_task` 的冪等短路設計)。重跑為終局、不重派,故 no-op 安全。

    重試標籤沿用既有 `_MAX_RETRIES`(讀 `AI_EVAL_TASK_MAX_RETRIES`);service 對「單一
    challenger 失敗」自行收斂落 `status='error'`、不拋,只有 DB / 網路等非預期錯誤才會冒出
    → 交由 taskiq `SimpleRetryMiddleware` 重試。

    Args:
        ai_evaluation_uid: 待重跑的 `ai_model_evaluations.ai_evaluation_uid`(序列化為字串)。

    Raises:
        Exception: service 對「部分重跑失敗」不拋;DB / 網路等非預期錯誤才會冒出,
            交由 taskiq 依 max_retries 重試。
    """
    # 延遲 import:app.core.database 於 import 時即 get_settings()(需完整 .env);
    # 放進函式體保留本模組的 CI-importability(見模組 docstring)。
    from app.core.database import SessionLocal

    uid = UUID(ai_evaluation_uid)
    settings = get_settings()

    async with SessionLocal() as db:
        # 短路:父評審 `ai_reran_at` 已非 NULL → 已重跑過,不重打 OpenRouter。
        # repository 無「以 ai_evaluation_uid 取單列」getter,以 ORM select 直取
        # (對齊 services/ai_model_eval_rerun.py 既有作法;見 docs/Tasks/v2.1/fixed.md §3,非 raw SQL)。
        parent: AiModelEvaluation | None = (
            await db.execute(
                select(AiModelEvaluation).where(
                    AiModelEvaluation.ai_evaluation_uid == uid,
                    AiModelEvaluation.is_deleted.is_(False),
                )
            )
        ).scalar_one_or_none()
        if parent is not None and parent.ai_reran_at is not None:
            logger.info(
                "評審重跑略過:父評審已重跑(冪等短路) ai_evaluation_uid=%s", uid
            )
            return

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(settings.OPENROUTER_API_TIMEOUT),
        ) as http_client:
            client = OpenRouterClient(http_client, settings.OPENROUTER_API_BASE_URL)
            await rerun_evaluation(uid, db=db, client=client)
        # session 擁有者負責 commit(沿用專案慣例;service 內回寫只 flush,未 commit
        # 則 SessionLocal 結束時 rollback,重跑結果不落地)。
        await db.commit()


@broker.task(schedule=[{"interval": _BEAT_INTERVAL}])
async def dispatch_unrerun() -> int:
    """掃待重跑父評審逐筆派進 broker;回傳實際派發筆數(task-406;propose-v2.1.0 §5.1)。

    以 `@broker.task(schedule=[{"interval": AI_EVAL_BEAT_INTERVAL_SECONDS}])` 帶排程標籤
    (**沿用既有評審 beat / batch 常數**,決議 #8;不新增 env),供 scheduler 的
    `LabelScheduleSource` 每隔此秒數觸發一次。

    - `AI_RERUN_ENABLED` 為 false → 直接 return 0(完全不派發,零成本)。
    - 為真 → 自建 session,`fetch_unreran_evaluation_uids(AI_EVAL_DISPATCH_BATCH_SIZE)`
      撈待重跑父評審(`ai_reran_at IS NULL` 且 `status='evaluated'`),逐筆
      `await rerun_evaluation_task.kiq(str(uid))`。

    **不**加抽樣 / 吻合度門檻(決議 #3)。防重複派發:依賴 task 端短路 + 重跑游標
    (`ai_reran_at`),不在此搶佔游標。
    """
    settings = get_settings()
    if not settings.AI_RERUN_ENABLED:
        logger.debug("AI 評審重跑派發略過:AI_RERUN_ENABLED=false")
        return 0

    from app.core.database import SessionLocal  # 延遲 import,見模組 docstring

    async with SessionLocal() as db:
        uids = await AiModelEvaluationRepository(db).fetch_unreran_evaluation_uids(
            settings.AI_EVAL_DISPATCH_BATCH_SIZE,
            start_at=settings.ai_eval_start_at_dt,
        )

    for uid in uids:
        await rerun_evaluation_task.kiq(str(uid))

    logger.info("AI 評審重跑派發完成:派發 %d 筆", len(uids))
    return len(uids)
