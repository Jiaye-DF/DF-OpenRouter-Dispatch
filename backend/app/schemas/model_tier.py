from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ModelTierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tier_uid: UUID
    key: str
    label_zh: str
    label_en: str | None = None
    color: str | None = None
    sort_order: int
    auto_match_min_price_per_mtok: Decimal | None = None
    auto_match_max_price_per_mtok: Decimal | None = None

    is_active: bool
    is_deleted: bool
    created_at: datetime
    updated_at: datetime


class ModelTierCreate(BaseModel):
    key: str = Field(min_length=1, max_length=32)
    label_zh: str = Field(min_length=1, max_length=64)
    label_en: str | None = Field(default=None, max_length=64)
    color: str | None = Field(default=None, max_length=16)
    sort_order: int = 0
    auto_match_min_price_per_mtok: Decimal | None = None
    auto_match_max_price_per_mtok: Decimal | None = None


class ModelTierPatch(BaseModel):
    """key 建立後不可改,排除於 patch 欄位。"""

    label_zh: str | None = Field(default=None, min_length=1, max_length=64)
    label_en: str | None = Field(default=None, max_length=64)
    color: str | None = Field(default=None, max_length=16)
    sort_order: int | None = None
    auto_match_min_price_per_mtok: Decimal | None = None
    auto_match_max_price_per_mtok: Decimal | None = None
