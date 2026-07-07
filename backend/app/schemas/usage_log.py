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

    # pid 作為 admin 端「顯示編號」(#pid):供用量紀錄與 AI 判決總覽兩頁互相對應。
    # 註:pid 原為內部識別,此處刻意對 admin 外露當人類可讀參考號(見 v2.1 fixed.md)。
    pid: int
    usage_log_uid: UUID
    user_uid: UUID | None
    department_uid: UUID | None
    # v2.1.1:每筆呼叫所屬專案。project_uid 為 UsageLog 既有欄位(from_attributes 直讀);
    # project_code / project_name 由 repository LEFT JOIN projects 取得,於 router 以
    # model_copy(update=...) 補上;歷史 project_uid IS NULL 的列三欄皆為 None。
    project_uid: UUID | None = None
    project_code: str | None = None
    project_name: str | None = None
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
