from typing import Any

from pydantic import BaseModel, Field


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
