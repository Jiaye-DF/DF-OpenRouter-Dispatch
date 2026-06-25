"""判別 AI 結構化輸出 schema(對齊 docs/Tasks/v2.0/propose-v2.0.1.md §5 / §6)。

此檔承載「判別模型讀原文後**生成**的判斷」(dim1–4),與既有 `ai_eval.py`
(判別模型**設定** CRUD)職責不同,故獨立成檔,命名一律以 `Judge*` 表「AI 生成判斷」語意。

頂層模型為 `JudgeOutput`,解析判別模型回傳的 JSON。採**寬鬆解析**:
- 容忍模型多回未知欄位(`extra="ignore"`)。
- dim2 意圖不在固定枚舉內 → 落 `TaskIntent.OTHER`(寬鬆 fallback)。
- `output_fit.score` 嚴格限 0–1,超界 raise `ValidationError`(此為唯一可觀察錨點,不容失真)。
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TaskIntent(StrEnum):
    """dim2 任務意圖固定枚舉。

    便於日後跨筆彙總;模型回的意圖不在此集合內時,於 `JudgeOutput` 寬鬆映射為 `OTHER`。
    """

    CODE_GENERATION = "code_generation"
    QA = "qa"
    SUMMARIZATION = "summarization"
    TRANSLATION = "translation"
    REASONING = "reasoning"
    EXTRACTION = "extraction"
    OTHER = "other"


class TaskComplexity(StrEnum):
    """dim2 任務複雜度固定枚舉。"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class OutputFit(BaseModel):
    """dim3 輸出吻合度(唯一可觀察錨點)。

    - `score`:原 output 對任務意圖的吻合度,嚴格 0–1;超界 raise ValidationError。
    - `reason`:吻合 / 不吻合的理由。
    """

    model_config = ConfigDict(extra="ignore")

    score: float = Field(ge=0.0, le=1.0)
    reason: str = ""


class Recommend(BaseModel):
    """dim4 推薦模型(限白名單;tier 由 service 反查所選 model)。

    - `model`:建議改用的 model_key;只能是 prompt 餵入的候選白名單之一(service 層校驗)。
    - `reason`:推薦理由。
    """

    model_config = ConfigDict(extra="ignore")

    model: str = ""
    reason: str = ""


class JudgeOutput(BaseModel):
    """判別模型的結構化判斷(dim1–4),解析自模型回傳 JSON。

    對齊 propose §6 草案:
    - `task_summary`(dim1):使用者輸入摘要。
    - `task_intent` + `task_complexity`(dim2):任務意圖(固定枚舉,越界落 other)+ 複雜度。
    - `output_fit`(dim3):原 output 對意圖的吻合度錨點(score 0–1)。
    - `recommend`(dim4):更適合的模型(限白名單)+ 理由。
    """

    model_config = ConfigDict(extra="ignore")

    task_summary: str = ""
    task_intent: TaskIntent = TaskIntent.OTHER
    task_complexity: TaskComplexity
    output_fit: OutputFit
    recommend: Recommend

    @field_validator("task_intent", mode="before")
    @classmethod
    def _coerce_intent(cls, value: object) -> object:
        """寬鬆映射意圖:不在固定枚舉內(或非字串)→ 落 OTHER。

        枚舉成員本身(已為合法 TaskIntent)直接放行,交由 pydantic 正常驗證。
        """
        if isinstance(value, TaskIntent):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            valid = {member.value for member in TaskIntent}
            if normalized in valid:
                return normalized
            return TaskIntent.OTHER.value
        return TaskIntent.OTHER.value
