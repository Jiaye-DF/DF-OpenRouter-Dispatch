from datetime import datetime
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import BigInteger, DateTime, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Model(Base, TimestampMixin):
    __tablename__ = "models"

    __table_args__ = (
        sa.Index(
            "idx_models_active",
            "is_active",
            postgresql_where=sa.text("is_deleted = false"),
        ),
        sa.Index(
            "idx_models_provider",
            "provider",
            postgresql_where=sa.text("is_deleted = false"),
        ),
        sa.Index(
            "idx_models_tier_key",
            "tier_key",
            postgresql_where=sa.text("is_deleted = false"),
        ),
        {"comment": "模型"},
    )

    pid: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        comment="內部自增主鍵,禁對外暴露 | internal auto-increment PK",
    )
    model_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        unique=True,
        nullable=False,
        comment="對外 UUID 識別(UUIDv7) | external UID",
    )

    provider: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="openrouter",
        server_default="openrouter",
        comment="模型 provider:openrouter(由同步寫入)/ internal(admin 手動建立) | model provider source",
    )
    model_key: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        nullable=False,
        comment="模型對外識別 key:openrouter 為 openai/gpt-4o,internal 為 admin 自訂 | external model key",
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="模型顯示名稱 | model display name",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="模型描述 | model description",
    )

    context_length: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="上下文長度(token 數) | context length in tokens",
    )
    max_completion_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="單次回應最大 token 數 | max completion tokens",
    )
    modality: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="模態描述字串(OpenRouter architecture.modality) | modality string",
    )
    input_modalities: Mapped[list[str]] = mapped_column(
        PG_ARRAY(String(32)),
        nullable=False,
        default=list,
        server_default="{}",
        comment="可接受之輸入模態 tag(如 text/image/file);OpenRouter 由 sync 覆寫,internal 可由 admin 自訂 | input modalities",
    )
    output_modalities: Mapped[list[str]] = mapped_column(
        PG_ARRAY(String(32)),
        nullable=False,
        default=list,
        server_default="{}",
        comment="可產出之輸出模態 tag(如 text);OpenRouter 由 sync 覆寫,internal 可由 admin 自訂 | output modalities",
    )
    tokenizer: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="分詞器類型 | tokenizer type",
    )

    price_prompt_per_token: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 12),
        nullable=True,
        comment="prompt 每 token 單價(USD) | prompt price per token (USD)",
    )
    price_completion_per_token: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 12),
        nullable=True,
        comment="completion 每 token 單價(USD) | completion price per token (USD)",
    )
    price_image_per_image: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 12),
        nullable=True,
        comment="每張圖片單價(USD) | image price per image (USD)",
    )
    price_request_flat: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 12),
        nullable=True,
        comment="每次請求固定費用(USD) | flat price per request (USD)",
    )

    is_moderated: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        server_default="false",
        comment="平台控管(可由 admin 編輯) | moderated flag (admin editable)",
    )
    tier_key: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        comment="model_tiers.key 的軟引用;NULL = 未分級 | tier key soft-reference (NULL = unranked)",
    )

    openrouter_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="OpenRouter 端模型建立時間 | OpenRouter-side created at",
    )
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="最近一次同步時間 | last synced at",
    )
