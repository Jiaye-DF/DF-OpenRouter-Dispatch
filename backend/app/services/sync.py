"""模型主檔 + OpenRouter 餘額同步服務(對齊 propose-v1.1.0.md § 6)。

流程:
1. pg_try_advisory_xact_lock 防並發 → 425 sync_in_progress
2. max(last_synced_at) 距今 < 10 min → 425 sync_throttled
3. 拿任一把 active OR Key 取 /models;失敗換下一把,全部失敗 → 502 openrouter_unavailable
4. UPSERT models:
   - 白名單來源:DB 表 `allowed_models`(is_active=TRUE 的 model_key 集合)
   - INSERT 新模型 → is_active = (model_key in whitelist)
   - UPDATE 既有模型 → 強制套用 whitelist 覆寫 is_active(不動 tier_key)
   - DB 有但 OR 無 → is_active=FALSE
   - 編輯 `allowed_models` 表後,下次 sync 自動生效。
5. 對每把 active OR Key 呼叫 /auth/key,best-effort 回填 4 欄
6. 寫稽核 + commit + 釋放 advisory lock
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils import uuid7

from app.clients.openrouter.client import OpenRouterClient
from app.clients.openrouter.errors import OpenRouterError
from app.core.audit import write_audit
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.models.model import Model
from app.models.model_tier import ModelTier
from app.models.openrouter_key import OpenRouterKey
from app.repositories.allowed_model import AllowedModelRepository
from app.repositories.model import ModelRepository
from app.repositories.model_tier import ModelTierRepository
from app.schemas.model import ModelSyncResult
from app.services.openrouter_key import decrypt_key

logger = get_logger(__name__)

# 64-bit advisory lock key — "MODELSY" 的 ASCII 7 byte → BIGINT
LOCK_KEY_MODELS_SYNC: int = 0x4D4F44454C5359  # 21808134934773593

# 同步限流(秒)— 10 分鐘
SYNC_THROTTLE_SECONDS: int = 600

# Sync 模型白名單由 DB 表 `allowed_models` 控制(v1.5+)。
# - 只有該表 is_active=TRUE 的 model_key,sync 後對應 models.is_active=TRUE
# - 其他一律停用(包含 free / ZDR-only / admin 手動開過的)
# - 規則每次 sync 強制套用 → 編輯 allowed_models 表後,下次 sync 自動生效


def _to_decimal(v: Any) -> Decimal | None:
    """OpenRouter pricing 與 created 欄位多半是字串;空值與失敗一律回 None。"""
    if v is None:
        return None
    if isinstance(v, Decimal):
        return v
    try:
        d = Decimal(str(v))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return d


def _to_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _epoch_to_dt(v: Any) -> datetime | None:
    n = _to_int(v)
    if n is None or n <= 0:
        return None
    try:
        return datetime.fromtimestamp(n, tz=UTC)
    except (OSError, OverflowError, ValueError):
        return None


def match_tier(price: Decimal | None, tiers: list[ModelTier]) -> str | None:
    """依 sort_order 升冪掃描,第一個滿足區間的 tier 即為結果。

    - 區間語義:[min, max);max 為 NULL 表無上限。
    - 若 min == max(精確匹配,如 free 用 [0, 0]):price == min 才算。
    - min 與 max 皆 NULL → 不參與自動匹配。
    """
    if price is None:
        return None
    for tier in tiers:
        mn = tier.auto_match_min_price_per_mtok
        mx = tier.auto_match_max_price_per_mtok
        if mn is None and mx is None:
            continue
        if mn is not None and mx is not None and mn == mx:
            if price == mn:
                return tier.key
        else:
            min_ok = mn is None or price >= mn
            max_ok = mx is None or price < mx
            if min_ok and max_ok:
                return tier.key
    return None


def _parse_or_model(item: dict[str, Any]) -> dict[str, Any]:
    """將 OpenRouter /models 單筆 dict 解構為 Model 欄位。"""
    pricing = item.get("pricing") or {}
    arch = item.get("architecture") or {}
    top = item.get("top_provider") or {}
    return {
        "model_key": item.get("id") or "",
        "name": item.get("name") or item.get("id") or "",
        "description": item.get("description"),
        "context_length": _to_int(item.get("context_length") or top.get("context_length")),
        "max_completion_tokens": _to_int(top.get("max_completion_tokens")),
        "modality": (arch.get("modality") or arch.get("input_modalities") or None)
        if not isinstance(arch.get("modality"), list)
        else ",".join(str(x) for x in arch.get("modality") or []),
        "tokenizer": arch.get("tokenizer"),
        "price_prompt_per_token": _to_decimal(pricing.get("prompt")),
        "price_completion_per_token": _to_decimal(pricing.get("completion")),
        "price_image_per_image": _to_decimal(pricing.get("image")),
        "price_request_flat": _to_decimal(pricing.get("request")),
        "is_moderated": bool(top.get("is_moderated", False)),
        "openrouter_created_at": _epoch_to_dt(item.get("created")),
    }


async def _try_acquire_lock(db: AsyncSession) -> bool:
    """取得 transaction 級 advisory lock;transaction 結束自動釋放。"""
    row = await db.execute(
        text("SELECT pg_try_advisory_xact_lock(:k) AS ok"),
        {"k": LOCK_KEY_MODELS_SYNC},
    )
    return bool(row.scalar_one())


async def _max_last_synced_at(db: AsyncSession) -> datetime | None:
    row = await db.execute(select(func.max(Model.last_synced_at)))
    return row.scalar_one_or_none()


async def _list_active_openrouter_keys(db: AsyncSession) -> list[OpenRouterKey]:
    """全平台 active 且未刪除的 OR Key,跨部門。"""
    stmt = select(OpenRouterKey).where(
        OpenRouterKey.is_active.is_(True),
        OpenRouterKey.is_deleted.is_(False),
    )
    return list((await db.execute(stmt)).scalars().all())


async def _fetch_models_with_failover(
    client: OpenRouterClient, keys: list[OpenRouterKey]
) -> list[dict[str, Any]]:
    """逐一嘗試 active OR Key 直到 /models 成功;全部失敗丟 502。"""
    last_err: Exception | None = None
    for key_row in keys:
        try:
            raw = decrypt_key(key_row)
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            logger.exception("解密 OR Key 失敗 uid=%s", key_row.openrouter_key_uid)
            continue
        try:
            data = await client.list_models(raw)
        except OpenRouterError as exc:
            last_err = exc
            logger.warning(
                "OR Key uid=%s 取 /models 失敗(%s),嘗試下一把",
                key_row.openrouter_key_uid,
                exc,
            )
            continue
        return data
    raise AppError("openrouter_unavailable", code=502) from last_err


async def _sync_models(
    db: AsyncSession,
    or_models: list[dict[str, Any]],
    tiers: list[ModelTier],
    whitelist: set[str],
) -> tuple[int, int, int, int]:
    """UPSERT models;回傳 (added, updated, deactivated, total)。"""
    repo = ModelRepository(db)
    now = datetime.now(tz=UTC)
    added = 0
    updated = 0
    seen_ids: set[str] = set()

    for raw in or_models:
        parsed = _parse_or_model(raw)
        mid = parsed["model_key"]
        if not mid:
            continue
        seen_ids.add(mid)
        # 白名單規則:每次 sync 強制套用,覆寫 admin 手動改過的 is_active。
        desired_active = mid in whitelist
        existing = await repo.find_by_key(mid)
        if existing is None:
            tier_key = match_tier(parsed["price_prompt_per_token"], tiers)
            row = Model(
                model_uid=UUID(str(uuid7())),
                model_key=mid,
                provider="openrouter",
                name=parsed["name"],
                description=parsed["description"],
                context_length=parsed["context_length"],
                max_completion_tokens=parsed["max_completion_tokens"],
                modality=parsed["modality"],
                tokenizer=parsed["tokenizer"],
                price_prompt_per_token=parsed["price_prompt_per_token"],
                price_completion_per_token=parsed["price_completion_per_token"],
                price_image_per_image=parsed["price_image_per_image"],
                price_request_flat=parsed["price_request_flat"],
                is_moderated=parsed["is_moderated"],
                tier_key=tier_key,
                openrouter_created_at=parsed["openrouter_created_at"],
                last_synced_at=now,
                is_active=desired_active,
                is_deleted=False,
            )
            repo.add(row)
            added += 1
        else:
            # UPDATE 既有元資料 + 強制以白名單覆寫 is_active(不動 tier_key)
            existing.name = parsed["name"]
            existing.description = parsed["description"]
            existing.context_length = parsed["context_length"]
            existing.max_completion_tokens = parsed["max_completion_tokens"]
            existing.modality = parsed["modality"]
            existing.tokenizer = parsed["tokenizer"]
            existing.price_prompt_per_token = parsed["price_prompt_per_token"]
            existing.price_completion_per_token = parsed["price_completion_per_token"]
            existing.price_image_per_image = parsed["price_image_per_image"]
            existing.price_request_flat = parsed["price_request_flat"]
            existing.is_moderated = parsed["is_moderated"]
            if parsed["openrouter_created_at"] is not None:
                existing.openrouter_created_at = parsed["openrouter_created_at"]
            existing.last_synced_at = now
            existing.is_active = desired_active
            updated += 1
    await db.flush()

    # DB 有但 OR 無 → is_active=FALSE(不動其他 metadata,不動 tier_key)
    deactivated = 0
    if seen_ids:
        # 找出 active 但這次同步沒看到的;空清單時不 deactivate(避免 OR 給空清單把全部關掉)
        stmt = select(Model).where(
            Model.is_deleted.is_(False),
            Model.is_active.is_(True),
            Model.provider == "openrouter",
            Model.model_key.notin_(seen_ids),
        )
        rows = list((await db.execute(stmt)).scalars().all())
        for row in rows:
            row.is_active = False
            deactivated += 1
        if rows:
            await db.flush()

    total = len(seen_ids)
    return added, updated, deactivated, total


async def _sync_credits(
    db: AsyncSession, client: OpenRouterClient, keys: list[OpenRouterKey]
) -> tuple[int, int]:
    """對每把 active OR Key 呼叫 /auth/key,best-effort 回填餘額;個別失敗不 rollback。"""
    synced = 0
    failed = 0
    now = datetime.now(tz=UTC)
    for key_row in keys:
        try:
            raw = decrypt_key(key_row)
            info = await client.get_key_info(raw)
        except Exception as exc:  # noqa: BLE001
            failed += 1
            logger.warning(
                "OR Key uid=%s /auth/key 失敗:%s",
                key_row.openrouter_key_uid,
                exc,
            )
            continue
        try:
            usage = _to_decimal(info.get("usage"))
            limit = _to_decimal(info.get("limit"))
            free_raw = info.get("is_free_tier")
            free = bool(free_raw) if free_raw is not None else None
            key_row.credits_used_usd = usage
            key_row.credits_limit_usd = limit
            key_row.credits_is_free_tier = free
            key_row.credits_synced_at = now
            synced += 1
        except Exception:
            failed += 1
            logger.exception(
                "OR Key uid=%s 回填餘額欄失敗", key_row.openrouter_key_uid
            )
    await db.flush()
    return synced, failed


async def sync_models_and_credits(
    db: AsyncSession,
    client: OpenRouterClient,
    *,
    actor_user_uid: UUID,
    actor_role: str,
    ip: str | None = None,
) -> ModelSyncResult:
    """同步 OpenRouter 模型清單 + 帳號餘額。Admin only;呼叫端負責 dependency。"""

    # 1. advisory lock 防並發
    if not await _try_acquire_lock(db):
        raise AppError("sync_in_progress", code=425)

    # 2. 10 分鐘 throttle(以 max(last_synced_at) 判斷)
    last = await _max_last_synced_at(db)
    if last is not None:
        # 處理 naive vs aware:DB 欄位是 timestamptz;若回傳是 naive(極少)當 UTC
        if last.tzinfo is None:
            last = last.replace(tzinfo=UTC)
        elapsed = (datetime.now(tz=UTC) - last).total_seconds()
        if elapsed < SYNC_THROTTLE_SECONDS:
            retry_after = max(int(SYNC_THROTTLE_SECONDS - elapsed), 1)
            raise AppError(
                "sync_throttled",
                code=425,
                data={"retry_after_seconds": retry_after},
            )

    # 3. 拿 active OR Key,/models 失效切換
    or_keys = await _list_active_openrouter_keys(db)
    if not or_keys:
        raise AppError("openrouter_unavailable", code=502)
    or_models = await _fetch_models_with_failover(client, or_keys)

    # 載入 tiers(自動匹配用)+ 載入白名單(每次 sync 強制套用)
    tiers_repo = ModelTierRepository(db)
    tiers = await tiers_repo.list_active()
    allowed_repo = AllowedModelRepository(db)
    whitelist = await allowed_repo.list_active_keys()

    # 4. UPSERT models
    added, updated, deactivated, total = await _sync_models(db, or_models, tiers, whitelist)

    # 5. 同步餘額(best-effort)
    credits_synced, credits_failed = await _sync_credits(db, client, or_keys)

    # 6. 寫稽核
    synced_at = datetime.now(tz=UTC)
    audit_extra = {
        "added": added,
        "updated": updated,
        "deactivated": deactivated,
        "total": total,
        "credits_synced": credits_synced,
        "credits_failed": credits_failed,
    }
    await write_audit(
        db,
        actor_user_uid=actor_user_uid,
        actor_role=actor_role,
        action="sync_models_and_credits",
        target_type="model",
        target_uid=None,
        ip=ip,
        extra=audit_extra,
    )

    # 7. commit(advisory_xact_lock 隨 transaction 結束自動釋放)
    await db.commit()

    return ModelSyncResult(
        added=added,
        updated=updated,
        deactivated=deactivated,
        total=total,
        credits_synced=credits_synced,
        credits_failed=credits_failed,
        synced_at=synced_at,
    )
