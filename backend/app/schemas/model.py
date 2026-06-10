from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    """Chat 代理的請求 body。

    輸入刻意收斂為「純文字 / 多模態 + 可選工具」,不暴露 OpenAI 全部欄位:

    - `text` / `images`:組成單一 user 訊息的多模態內容。
    - `videos`:本版本不支援,送出即回 400(僅佔位,待未來版本)。
    - `tools`:見下方欄位說明。
    """

    model: str = Field(min_length=1, max_length=128)
    text: str | None = None
    images: list[str] | None = None
    videos: list[str] | None = None  # 本版本不支援；送出即回 400
    # 直接透傳給下游(OpenRouter / internal),格式同 OpenAI tools 規格。
    # 例:OpenRouter 內建工具 [{"type": "openrouter:web_search"}]。
    # 注意:本版本僅支援「server 端工具」(回應仍為純文字);尚未開放會回
    # tool_calls 的 function calling。
    tools: list[dict[str, Any]] | None = None


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
    input_modalities: list[str] = Field(default_factory=list)
    output_modalities: list[str] = Field(default_factory=list)
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
    input_modalities: list[str] = Field(default_factory=list)
    output_modalities: list[str] = Field(default_factory=list)


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
    input_modalities: list[str] | None = Field(default=None, max_length=16)
    output_modalities: list[str] | None = Field(default=None, max_length=16)


class ModelCreateRequest(BaseModel):
    """手動建立模型(僅接受 provider='internal';openrouter 必須走同步)。"""

    provider: str = Field(min_length=1, max_length=32)
    model_key: str = Field(min_length=1, max_length=128, pattern=r"^[a-z0-9_\-/.]+$")
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    context_length: int | None = Field(default=None, ge=0)
    modality: str | None = Field(default="text->text", max_length=64)
    input_modalities: list[str] = Field(default_factory=lambda: ["text"], max_length=16)
    output_modalities: list[str] = Field(default_factory=lambda: ["text"], max_length=16)
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


class ModelBulkActivateRequest(BaseModel):
    """批次切換 OpenRouter 模型可用性(admin)。

    - `all`:啟用全部 OpenRouter 模型(is_active=TRUE)。
    - `defaults`:僅保留白名單(allowed_models)模型 —— 白名單內的啟用、其餘停用,
      等同重新套用 sync 的白名單規則(但不向 OpenRouter 重新拉取)。

    兩種模式皆只作用於 provider='openrouter' 的模型,不影響 internal 模型。
    """

    mode: Literal["all", "defaults"]


class ModelBulkActivateResult(BaseModel):
    """批次切換結果計數。"""

    mode: Literal["all", "defaults"]
    activated: int
    deactivated: int
