from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import BigInteger, DateTime, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AiModelEvalRerun(Base, TimestampMixin):
    """challenger 真實重跑 + 對比裁決結果表(一筆 = 一個 challenger;v2.1.0)。

    記錄評審推薦模型(challenger)的真實 API 呼叫結果與「原輸出 vs challenger 輸出」
    的 AI discriminator 裁決(GAN/champion-challenger 閉環)。與 `usage_logs` 結構相似
    但**獨立**——標記「因 AI 推薦而觸發」,不混入正常用量/計費統計。

    軟引用:
    - `ai_evaluation_uid` → `ai_model_evaluations.ai_evaluation_uid`(來自哪次評審)。
    - `usage_log_uid` → `usage_logs.usage_log_uid`(同輸入來源)。
    - `ai_candidate_uid` → `ai_model_eval_candidates.ai_candidate_uid`(哪個裁判候選推薦;去重取代表者)。
    - `model_uid` → `models.model_uid`(challenger 模型)。

    冪等:`UNIQUE(ai_evaluation_uid, rerun_model)`(不分軟刪),避免同 challenger 重複重跑。

    金額精度:`cost_usd` / `original_cost_usd` / `cost_delta_usd` 採 `Numeric(12,6)`、
    `compare_score` 採 `Numeric(4,3)`(信心分數 0–1),非預設 `Numeric(18,2)`——
    OpenRouter 計費以美元微量計(單筆成本常 < 0.01 USD),需小數第 6 位精度;
    信心分數為 0–1 三位小數。依 `05-precision.md` 允許依語意調整。
    """

    __tablename__ = "ai_model_eval_reruns"

    __table_args__ = (
        sa.UniqueConstraint(
            "ai_evaluation_uid",
            "rerun_model",
            name="uq_ai_model_eval_reruns_evaluation_uid_rerun_model",
        ),
        sa.Index(
            "idx_ai_model_eval_reruns_usage_log_uid",
            "usage_log_uid",
        ),
        sa.Index(
            "idx_ai_model_eval_reruns_evaluation_uid",
            "ai_evaluation_uid",
            postgresql_where=sa.text("(is_deleted = false)"),
        ),
        {"comment": "模型評審 challenger 真實重跑與對比裁決"},
    )

    pid: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        comment="內部自增主鍵,禁對外暴露 | internal auto-increment PK",
    )
    ai_eval_rerun_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        unique=True,
        nullable=False,
        comment="對外 UUID 識別(UUIDv7) | external UID",
    )
    # 軟引用 ai_model_evaluations.ai_evaluation_uid:來自哪次評審的推薦
    ai_evaluation_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        comment="軟引用父評審(來自哪次評審的推薦) | parent evaluation",
    )
    # 軟引用 usage_logs.usage_log_uid:同輸入來源
    usage_log_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        comment="軟引用原始 log(同輸入來源) | source usage log",
    )
    # 軟引用 ai_model_eval_candidates.ai_candidate_uid:去重合併時取代表者
    ai_candidate_uid: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="軟引用是哪個裁判候選推薦的(去重取代表者) | source candidate",
    )
    # 原模型 key(denormalize,對比顯示)
    original_model: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="原模型 key(denormalize,對比顯示) | original model key",
    )
    # challenger 模型 key(實際重跑)
    rerun_model: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="challenger 模型 key(實際重跑) | challenger model key",
    )
    # 軟引用 models.model_uid:challenger 模型
    model_uid: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="challenger model_uid(軟引用 models.model_uid) | challenger model",
    )
    # 重跑輸入快照(可重現;沿用原 log 輸入)
    request_content: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="重跑輸入快照(可重現;沿用原 log 輸入) | request snapshot",
    )
    # challenger 真實輸出 {output_text, usage?}
    response_summary: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="challenger 真實輸出({output_text, usage?}) | challenger response",
    )
    # challenger 真實 prompt token
    prompt_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="challenger 真實 prompt token | prompt tokens",
    )
    # challenger 真實 completion token
    completion_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="challenger 真實 completion token | completion tokens",
    )
    # challenger 真實 total token
    total_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="challenger 真實 total token | total tokens",
    )
    # challenger 真實成本(USD,微量計,6 位精度)
    cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6),
        nullable=True,
        comment="challenger 真實成本(USD,6 位精度) | challenger cost (USD)",
    )
    # 原呼叫成本(denormalize,對比)
    original_cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6),
        nullable=True,
        comment="原呼叫成本(denormalize,對比;USD) | original cost (USD)",
    )
    # challenger − original(客觀指標)
    cost_delta_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6),
        nullable=True,
        comment="成本差 challenger − original(客觀指標;USD) | cost delta (USD)",
    )
    # challenger 延遲(毫秒)
    latency_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="challenger 延遲(毫秒) | latency (ms)",
    )
    # success / error
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="success",
        server_default="success",
        comment="重跑狀態:success/error | rerun status",
    )
    # NULL=無錯誤
    error_code: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="錯誤碼(NULL=無錯誤) | error code",
    )
    # OpenRouter 生成 ID
    openrouter_generation_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="OpenRouter 生成 ID | OpenRouter generation id",
    )
    # discriminator 判決:original / challenger / tie
    compare_winner: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
        comment="裁決:original/challenger/tie | discriminator winner",
    )
    # 信心分數 0–1(對原推薦合理度的信心;(B) 啟用必填,停用 NULL)
    compare_score: Mapped[Decimal | None] = mapped_column(
        Numeric(4, 3),
        nullable=True,
        comment="信心分數 0–1(對原推薦合理度的信心) | confidence score 0–1",
    )
    # 裁決理由
    compare_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="裁決理由 | discriminator reason",
    )
    # 擔任 discriminator 的模型 key(=推薦該 challenger 的評審模型本人)
    compare_judge_model: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="擔任裁決的模型 key(推薦該 challenger 的評審本人) | judge model key",
    )
    # 重跑執行時間(UTC+8)
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="重跑執行時間(UTC+8) | triggered at",
    )
