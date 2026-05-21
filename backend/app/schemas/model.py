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
    provider: str
    model_key: str
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


class AllowedModelRead(BaseModel):
    """公開「可用模型」清單的精簡視圖(供 SDK 使用者瀏覽並複製 model_key)。

    刻意只暴露挑選模型所需的基本欄位;定價、tokenizer、時間戳等內部資訊不對外。
    """

    model_config = ConfigDict(from_attributes=True)

    provider: str
    model_key: str
    name: str
    description: str | None = None
    context_length: int | None = None
    modality: str | None = None


class ModelPatch(BaseModel):
    """Admin 編輯模型。

    - openrouter:僅可改 `is_active` 與 `tier_key`;其他欄位以同步資料為準(API 層忽略)。
    - internal:可改 `is_active` / `tier_key` / `name` / `description` / `context_length` / `modality`。
    """

    is_active: bool | None = None
    tier_key: str | None = Field(default=None, max_length=32)
    # 以下 internal-only;openrouter 編輯時忽略
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    context_length: int | None = Field(default=None, ge=0)
    modality: str | None = Field(default=None, max_length=64)


class ModelCreateRequest(BaseModel):
    """手動建立模型(僅接受 provider='internal';openrouter 必須走同步)。"""

    provider: str = Field(min_length=1, max_length=32)
    model_key: str = Field(min_length=1, max_length=128, pattern=r"^[a-z0-9_\-/.]+$")
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    context_length: int | None = Field(default=None, ge=0)
    modality: str | None = Field(default="text->text", max_length=64)
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
