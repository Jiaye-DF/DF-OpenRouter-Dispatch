import asyncio
import time
from decimal import Decimal
from hashlib import sha256
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils import uuid7

from app.clients.openrouter.client import OpenRouterClient
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
from app.models.usage_log import UsageLog
from app.services.openrouter_key import decrypt_key, pick_random_active

logger = get_logger(__name__)

_MAX_RETRIES = 5


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


def _sanitize_request_for_log(
    model: str, text: str | None, images: list[str] | None
) -> dict[str, Any]:
    sanitized_images: list[str] = []
    for img in images or []:
        if img.startswith("data:"):
            fp = sha256(img.encode("utf-8")).hexdigest()[:16]
            sanitized_images.append(f"data:<base64:{fp}>")
        else:
            sanitized_images.append(img)
    return {"model": model, "text": text, "images": sanitized_images}


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


def _check_model_whitelist(model: str) -> None:
    settings = get_settings()
    allow = settings.allowed_models_list
    if allow and model not in allow:
        raise AppError("model_forbidden", code=403)


def schedule_usage_log(
    *,
    department_uid: UUID | None,
    user_uid: UUID | None,
    openrouter_key_uid: UUID | None,
    model: str,
    resp: dict[str, Any] | None,
    latency_ms: int,
    status: str,
    error_code: str | None,
    request_log: dict[str, Any],
) -> None:
    """Fire-and-forget 寫入一筆 usage_logs（獨立 session，不受主 request 影響）。"""

    async def _task() -> None:
        async with SessionLocal() as session:
            try:
                usage = (resp or {}).get("usage") or {}
                prompt = int(usage.get("prompt_tokens") or 0)
                completion = int(usage.get("completion_tokens") or 0)
                total = int(usage.get("total_tokens") or (prompt + completion))
                # OpenRouter 用 `cost`；保留 total_cost 作為 fallback。
                cost = Decimal(str(usage.get("cost") or usage.get("total_cost") or 0))
                gen_id = (resp or {}).get("id")

                row = UsageLog(
                    usage_log_uid=UUID(str(uuid7())),
                    user_uid=user_uid,
                    department_uid=department_uid,
                    openrouter_key_uid=openrouter_key_uid,
                    model=model,
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
        # 沒有 running loop — 不應發生於 FastAPI context
        logger.warning("schedule_usage_log 無 running loop，略過")


async def run_chat(
    db: AsyncSession,
    *,
    client: OpenRouterClient,
    department_uid: UUID,
    user_uid: UUID,
    model: str,
    text: str | None,
    images: list[str] | None,
    videos: list[str] | None,
) -> dict[str, Any]:
    if videos:
        raise AppError("feature_not_supported", code=400)
    _check_model_whitelist(model)

    payload = _rewrite_request(model, text, images)
    request_log = _sanitize_request_for_log(model, text, images)

    tried: set[UUID] = set()
    last_err: Exception | None = None
    started = time.monotonic()

    for _ in range(_MAX_RETRIES):
        key_row = await pick_random_active(
            db, department_uid=department_uid, exclude_uids=tried
        )
        if key_row is None:
            break
        tried.add(key_row.openrouter_key_uid)
        try:
            raw_key = decrypt_key(key_row)
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            logger.exception("OpenRouter Key 解密失敗：%s", key_row.openrouter_key_uid)
            continue
        try:
            resp_body = await client.chat_completion(payload, api_key=raw_key)
        except OpenRouterAuthError as exc:
            last_err = exc
            logger.warning("OpenRouter 401；切換下一把 Key")
            continue
        except OpenRouterModelNotFoundError as exc:
            schedule_usage_log(
                department_uid=department_uid,
                user_uid=user_uid,
                openrouter_key_uid=key_row.openrouter_key_uid,
                model=model,
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
                resp=None,
                latency_ms=int((time.monotonic() - started) * 1000),
                status="error",
                error_code="rate_limited",
                request_log=request_log,
            )
            raise AppError("rate_limited", code=429) from exc
        except OpenRouterError as exc:
            last_err = exc
            logger.exception("OpenRouter 其他錯誤；嘗試下一把")
            continue

        # 成功
        latency_ms = int((time.monotonic() - started) * 1000)
        schedule_usage_log(
            department_uid=department_uid,
            user_uid=user_uid,
            openrouter_key_uid=key_row.openrouter_key_uid,
            model=model,
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
    schedule_usage_log(
        department_uid=department_uid,
        user_uid=user_uid,
        openrouter_key_uid=None,
        model=model,
        resp=None,
        latency_ms=latency_ms,
        status="error",
        error_code="openrouter_unavailable",
        request_log=request_log,
    )
    raise AppError("openrouter_unavailable", code=502) from last_err
