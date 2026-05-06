from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    model: str = Field(min_length=1, max_length=128)
    text: str | None = None
    images: list[str] | None = None
    videos: list[str] | None = None  # 本版本不支援；送出即回 400


class ChatResponse(BaseModel):
    """直接回 OpenRouter 原始 body（去除內部識別欄位後）。"""

    id: str | None = None
    model: str | None = None
    choices: list[dict[str, Any]] = []
    usage: dict[str, Any] | None = None
    created: int | None = None


class ModelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    model_uid: UUID
    openrouter_model_id: str
    name: str
    description: str | None = None

    context_length: int | None = None
    max_completion_tokens: int | None = None
    modality: str | None = None
    tokenizer: str | None = None

    price_prompt_per_token: Decimal | None = None
    price_completion_per_token: Decimal | None = None
    price_image_per_image: Decimal | None = None
    price_request_flat: Decimal | None = None

    is_moderated: bool
    tier_key: str | None = None

    openrouter_created_at: datetime | None = None
    last_synced_at: datetime

    is_active: bool
    is_deleted: bool
    created_at: datetime
    updated_at: datetime


class ModelPatch(BaseModel):
    """Admin 編輯模型 — 僅可改 is_active 與 tier_key;name/description/計費/規格皆唯讀,以 OR 為準。"""

    is_active: bool | None = None
    tier_key: str | None = Field(default=None, max_length=32)


class ModelSyncResult(BaseModel):
    """同步流程的計數結果(對齊 propose § 6.2 第 7 步)。"""

    added: int
    updated: int
    deactivated: int
    total: int
    credits_synced: int
    credits_failed: int
    synced_at: datetime
