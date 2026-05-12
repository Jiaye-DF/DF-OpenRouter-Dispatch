"""Chat 代理 — 依 model.provider 分流(v1.2)。

對齊 docs/Tasks/v1.2/propose-v1.2.0.md § 4 / § 6 / § 7。

兩條路徑:
- `openrouter`:per-Key 速率限制(從 `openrouter_keys` 表讀);撞限額 → failover 換下一把
- `internal`:per-Provider 速率限制(從 env 讀);撞限額 → 等待至 `RATE_WAIT_TIMEOUT`,超過 → 429 internal_busy
"""

import asyncio
import time
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils import uuid7

from app.clients.factory import ChatClientFactory
from app.clients.internal.client import (
    InternalAuthError,
    InternalError,
    InternalRateLimitError,
    InternalUnavailableError,
)
from app.clients.openrouter.errors import (
    OpenRouterAuthError,
    OpenRouterError,
    OpenRouterForbiddenError,
    OpenRouterModelNotFoundError,
    OpenRouterRateLimitError,
)
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.models.model import Model
from app.models.usage_log import UsageLog
from app.services.openrouter_key import decrypt_key, pick_random_active
from app.services.rate_limit import RateLimitExceeded, get_limiter

logger = get_logger(__name__)

_MAX_RETRIES = 5
_INTERNAL_LIMITER_KEY = "INTERNAL"


def _rewrite_request(model: str, text: str | None, images: list[str] | None) -> dict[str, Any]:
    content: list[dict[str, Any]] = []
    if text:
        content.append({"type": "text", "text": text})
    for img in images or []:
        content.append({"type": "image_url", "image_url": {"url": img}})
    if not content:
        content.append({"type": "text", "text": ""})
    return {
        "model": model,
        "messages": [{"role": "user", "content": content}],
    }


def _build_request_log(
    model: str, text: str | None, images: list[str] | None
) -> dict[str, Any]:
    return {"model": model, "text": text, "images": list(images or [])}


def _summarize_response(resp: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    choices = resp.get("choices") or []
    if choices:
        msg = choices[0].get("message") or {}
        raw = msg.get("content")
        if isinstance(raw, str):
            summary["first_text"] = raw[:500]
        elif isinstance(raw, list):
            for blk in raw:
                if isinstance(blk, dict) and blk.get("type") == "text":
                    summary["first_text"] = (blk.get("text") or "")[:500]
                    break
    if "usage" in resp:
        summary["usage"] = resp["usage"]
    return summary


async def _check_model_whitelist(db: AsyncSession, model: str) -> Model:
    """白名單由 DB 驅動;不存在 / 停用 / 軟刪除 一律 403 model_forbidden(避免列舉差異)。"""
    stmt = select(Model).where(
        Model.model_key == model,
        Model.is_active.is_(True),
        Model.is_deleted.is_(False),
    )
    instance = (await db.execute(stmt)).scalar_one_or_none()
    if instance is None:
        raise AppError("model_forbidden", code=403)
    return instance


def schedule_usage_log(
    *,
    department_uid: UUID | None,
    user_uid: UUID | None,
    openrouter_key_uid: UUID | None,
    model: str,
    model_uid: UUID | None,
    resp: dict[str, Any] | None,
    latency_ms: int,
    status: str,
    error_code: str | None,
    request_log: dict[str, Any],
) -> None:
    """Fire-and-forget 寫入一筆 usage_logs(獨立 session,不受主 request 影響)。"""

    async def _task() -> None:
        async with SessionLocal() as session:
            try:
                usage = (resp or {}).get("usage") or {}
                prompt = int(usage.get("prompt_tokens") or 0)
                completion = int(usage.get("completion_tokens") or 0)
                total = int(usage.get("total_tokens") or (prompt + completion))
                # OpenRouter 用 `cost`;保留 total_cost 作為 fallback。internal 一般無 cost,預設 0。
                cost = Decimal(str(usage.get("cost") or usage.get("total_cost") or 0))
                gen_id = (resp or {}).get("id")

                row = UsageLog(
                    usage_log_uid=UUID(str(uuid7())),
                    user_uid=user_uid,
                    department_uid=department_uid,
                    openrouter_key_uid=openrouter_key_uid,
                    model=model,
                    model_uid=model_uid,
                    prompt_tokens=prompt,
                    completion_tokens=completion,
                    total_tokens=total,
                    cost_usd=cost,
                    latency_ms=latency_ms,
                    status=status,
                    error_code=error_code,
                    request_content=request_log,
                    response_summary=_summarize_response(resp) if resp else None,
                    openrouter_generation_id=gen_id,
                )
                session.add(row)
                await session.commit()
            except Exception:
                logger.exception("usage_log 寫入失敗")
                await session.rollback()

    try:
        asyncio.create_task(_task())
    except RuntimeError:
        logger.warning("schedule_usage_log 無 running loop,略過")


async def run_chat(
    db: AsyncSession,
    *,
    client_factory: ChatClientFactory,
    department_uid: UUID,
    user_uid: UUID,
    model: str,
    text: str | None,
    images: list[str] | None,
    videos: list[str] | None,
) -> dict[str, Any]:
    """依 model.provider 分流到對應路徑;白名單檢查由本 fn 統一執行。"""
    if videos:
        raise AppError("feature_not_supported", code=400)
    model_row = await _check_model_whitelist(db, model)

    payload = _rewrite_request(model, text, images)
    request_log = _build_request_log(model, text, images)

    if model_row.provider == "internal":
        return await _run_chat_internal(
            client_factory=client_factory,
            model_row=model_row,
            department_uid=department_uid,
            user_uid=user_uid,
            payload=payload,
            request_log=request_log,
        )
    return await _run_chat_openrouter(
        db,
        client_factory=client_factory,
        model_row=model_row,
        department_uid=department_uid,
        user_uid=user_uid,
        payload=payload,
        request_log=request_log,
    )


async def _run_chat_openrouter(
    db: AsyncSession,
    *,
    client_factory: ChatClientFactory,
    model_row: Model,
    department_uid: UUID,
    user_uid: UUID,
    payload: dict[str, Any],
    request_log: dict[str, Any],
) -> dict[str, Any]:
    """OpenRouter 流程 — 每把 Key 經 rate limiter,撞限額 failover 換下一把。"""
    client = client_factory.openrouter()
    model = payload["model"]
    model_uid = model_row.model_uid

    tried: set[UUID] = set()
    last_err: Exception | None = None
    rate_limited_all = True  # 全部撞速率才回 rate_limited,否則回 openrouter_unavailable
    started = time.monotonic()

    for _ in range(_MAX_RETRIES):
        key_row = await pick_random_active(
            db, department_uid=department_uid, exclude_uids=tried
        )
        if key_row is None:
            break
        tried.add(key_row.openrouter_key_uid)

        # rate limiter:不等待,撞速率即換下一把
        limiter = await get_limiter(key_row.openrouter_key_uid)
        try:
            await limiter.acquire(
                rpm_limit=key_row.rpm_limit,
                min_interval_ms=key_row.min_request_interval_ms,
                wait_timeout=0,
            )
        except RateLimitExceeded:
            logger.warning(
                "OR Key uid=%s 速率限制(rpm=%d / min=%dms);切下一把",
                key_row.openrouter_key_uid,
                key_row.rpm_limit,
                key_row.min_request_interval_ms,
            )
            continue

        # 拿到 slot 後,後續任何失敗皆視為「實際打過 OR」失敗,不再全 rate_limited
        rate_limited_all = False

        try:
            raw_key = decrypt_key(key_row)
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            logger.exception("OpenRouter Key 解密失敗:%s", key_row.openrouter_key_uid)
            continue

        try:
            resp_body = await client.chat_completion(payload, api_key=raw_key)
        except OpenRouterAuthError as exc:
            last_err = exc
            logger.warning("OpenRouter 401;切換下一把 Key")
            continue
        except OpenRouterModelNotFoundError as exc:
            schedule_usage_log(
                department_uid=department_uid,
                user_uid=user_uid,
                openrouter_key_uid=key_row.openrouter_key_uid,
                model=model,
                model_uid=model_uid,
                resp=None,
                latency_ms=int((time.monotonic() - started) * 1000),
                status="error",
                error_code="model_not_found",
                request_log=request_log,
            )
            raise AppError("model_not_found", code=404) from exc
        except OpenRouterForbiddenError as exc:
            schedule_usage_log(
                department_uid=department_uid,
                user_uid=user_uid,
                openrouter_key_uid=key_row.openrouter_key_uid,
                model=model,
                model_uid=model_uid,
                resp=None,
                latency_ms=int((time.monotonic() - started) * 1000),
                status="error",
                error_code="model_forbidden",
                request_log=request_log,
            )
            raise AppError("model_forbidden", code=403) from exc
        except OpenRouterRateLimitError as exc:
            schedule_usage_log(
                department_uid=department_uid,
                user_uid=user_uid,
                openrouter_key_uid=key_row.openrouter_key_uid,
                model=model,
                model_uid=model_uid,
                resp=None,
                latency_ms=int((time.monotonic() - started) * 1000),
                status="error",
                error_code="rate_limited",
                request_log=request_log,
            )
            raise AppError("rate_limited", code=429) from exc
        except OpenRouterError as exc:
            last_err = exc
            logger.exception("OpenRouter 其他錯誤;嘗試下一把")
            continue

        # 成功
        latency_ms = int((time.monotonic() - started) * 1000)
        schedule_usage_log(
            department_uid=department_uid,
            user_uid=user_uid,
            openrouter_key_uid=key_row.openrouter_key_uid,
            model=model,
            model_uid=model_uid,
            resp=resp_body,
            latency_ms=latency_ms,
            status="success",
            error_code=None,
            request_log=request_log,
        )
        sanitized = dict(resp_body)
        for k in ("metadata", "provider_metadata"):
            sanitized.pop(k, None)
        return sanitized

    # 全部失敗
    latency_ms = int((time.monotonic() - started) * 1000)
    error_code = "rate_limited" if rate_limited_all else "openrouter_unavailable"
    code = 429 if rate_limited_all else 502
    schedule_usage_log(
        department_uid=department_uid,
        user_uid=user_uid,
        openrouter_key_uid=None,
        model=model,
        model_uid=model_uid,
        resp=None,
        latency_ms=latency_ms,
        status="error",
        error_code=error_code,
        request_log=request_log,
    )
    raise AppError(error_code, code=code) from last_err


async def _run_chat_internal(
    *,
    client_factory: ChatClientFactory,
    model_row: Model,
    department_uid: UUID,
    user_uid: UUID,
    payload: dict[str, Any],
    request_log: dict[str, Any],
) -> dict[str, Any]:
    """Internal 流程 — 全域 rate limiter,撞限額等待至 timeout,超過 → 429 internal_busy。"""
    settings = get_settings()
    model = payload["model"]
    model_uid = model_row.model_uid

    client = client_factory.internal()
    if client is None:
        # env 沒設 base_url 但有 internal 模型被呼叫
        raise AppError("provider_misconfigured", code=500)

    started = time.monotonic()
    limiter = await get_limiter(_INTERNAL_LIMITER_KEY)
    try:
        await limiter.acquire(
            rpm_limit=settings.INTERNAL_LLM_RPM_LIMIT,
            min_interval_ms=settings.INTERNAL_LLM_MIN_REQUEST_INTERVAL_MS,
            wait_timeout=float(settings.INTERNAL_LLM_RATE_WAIT_TIMEOUT),
        )
    except RateLimitExceeded as exc:
        latency_ms = int((time.monotonic() - started) * 1000)
        schedule_usage_log(
            department_uid=department_uid,
            user_uid=user_uid,
            openrouter_key_uid=None,
            model=model,
            model_uid=model_uid,
            resp=None,
            latency_ms=latency_ms,
            status="error",
            error_code="internal_busy",
            request_log=request_log,
        )
        raise AppError(
            "internal_busy",
            code=429,
            data={"retry_after_seconds": exc.retry_after_seconds},
        ) from exc

    try:
        resp_body = await client.chat_completion(payload)
    except InternalAuthError as exc:
        latency_ms = int((time.monotonic() - started) * 1000)
        schedule_usage_log(
            department_uid=department_uid,
            user_uid=user_uid,
            openrouter_key_uid=None,
            model=model,
            model_uid=model_uid,
            resp=None,
            latency_ms=latency_ms,
            status="error",
            error_code="internal_unavailable",
            request_log=request_log,
        )
        logger.warning("Internal LLM 401;檢查 INTERNAL_LLM_API_KEY")
        raise AppError("internal_unavailable", code=502) from exc
    except InternalRateLimitError as exc:
        latency_ms = int((time.monotonic() - started) * 1000)
        schedule_usage_log(
            department_uid=department_uid,
            user_uid=user_uid,
            openrouter_key_uid=None,
            model=model,
            model_uid=model_uid,
            resp=None,
            latency_ms=latency_ms,
            status="error",
            error_code="internal_busy",
            request_log=request_log,
        )
        # server 端速率,語意上等同 internal_busy(但已超出 limiter 控制)
        raise AppError("internal_busy", code=429) from exc
    except (InternalUnavailableError, InternalError) as exc:
        latency_ms = int((time.monotonic() - started) * 1000)
        schedule_usage_log(
            department_uid=department_uid,
            user_uid=user_uid,
            openrouter_key_uid=None,
            model=model,
            model_uid=model_uid,
            resp=None,
            latency_ms=latency_ms,
            status="error",
            error_code="internal_unavailable",
            request_log=request_log,
        )
        raise AppError("internal_unavailable", code=502) from exc

    # 成功
    latency_ms = int((time.monotonic() - started) * 1000)
    schedule_usage_log(
        department_uid=department_uid,
        user_uid=user_uid,
        openrouter_key_uid=None,
        model=model,
        model_uid=model_uid,
        resp=resp_body,
        latency_ms=latency_ms,
        status="success",
        error_code=None,
        request_log=request_log,
    )
    sanitized = dict(resp_body)
    for k in ("metadata", "provider_metadata"):
        sanitized.pop(k, None)
    return sanitized
