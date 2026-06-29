"""判別模型設定(AI 判別)Schema(對齊 docs/Tasks/v2.0/propose-v2.0.0.md §5)。

對外一律以 `model_uid`(UUID)識別,禁 dict / 內部 pid。
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class JudgeSettingRead(BaseModel):
    """單一判別模型槽位設定(GET 回傳元素)。"""

    model_config = ConfigDict(from_attributes=True)

    ai_judge_slot: int
    model_uid: UUID
    model_key: str
    name: str


class JudgeSettingsPutRequest(BaseModel):
    """整批設定 3 個判別模型槽位。

    `model_uids` 長度恰 3、不可重複、每個須為 models 既有 active 且未軟刪除模型。
    長度 / 重複於 endpoint 內以 AppError(code=422) 驗證,
    存在 / active 檢查需查 DB,同樣於 endpoint 內驗證。
    """

    model_uids: list[UUID]
