from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UsageLogListItem(BaseModel):
    """列表用精簡視圖 — 刻意**不含** request_content / response_summary。

    這兩欄為 JSONB,且 request_content 可能內含 base64 圖片(體積極大)。列表每頁
    多筆,若回傳完整內容會造成巨大 payload 浪費;完整內容改由單筆詳情端點按需取得。
    """

    model_config = ConfigDict(from_attributes=True)

    usage_log_uid: UUID
    user_uid: UUID | None
    department_uid: UUID | None
    openrouter_key_uid: UUID | None
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: Decimal
    latency_ms: int
    status: str
    error_code: str | None
    used_tools: bool
    openrouter_generation_id: str | None
    created_at: datetime


class UsageLogDetail(UsageLogListItem):
    """單筆詳情視圖 — 在列表欄位之上補回完整 request_content / response_summary。

    供用量紀錄詳情頁顯示使用者實際傳入內容(Input,含圖片)與模型回覆(Output)。
    """

    request_content: dict[str, Any] | None
    response_summary: dict[str, Any] | None
