"""評審結果對外讀取 schema(對齊 docs/Tasks/v2.0/propose-v2.0.3.md §4.2 / §5)。

本檔承載「評審結果**唯讀展示**」對外結構:依 `usage_log_uid` 取該筆三評審收斂後的
判決結果(父表 dim1/2 任務分析 + 本版彙總 + 三子候選),供 usage-logs 明細頁內嵌的
「AI 分析」基礎摘要區塊消費,並預留 v2.0.4 細看專頁重用完整 `candidates`。

職責邊界:
- 全為**唯讀** response 模型,不含任何 CRUD / 驗證邏輯。
- **Decimal → 字串傳輸**:所有 `*_fit_score` 一律宣告為 `str | None`,避免 JS 浮點誤差
  (專案既有慣例,propose §8 已明列)。實際 Decimal → str 轉換由 service(task-303)負責,
  此檔僅負責「型別宣告」。
- **無評審時**:頂層 `EvaluationResultResponse.evaluation` 為 `None`(對齊 propose §4.2 /
  決議 #6:`200 + evaluation=null`,非 404)。

命名與既有 `ai_model_eval.py`(判別模型生成判斷的解析 schema)區隔:此檔以 `Eval*` /
`Evaluation*` 表「評審結果對外讀取視圖」語意。
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TaskAnalysis(BaseModel):
    """任務分析(父表 dim1/2,v2.0.1 已取首個成功評審值存為單一值)。

    對齊 propose §4.2 `task_analysis`:
    - `summary`:使用者輸入摘要(dim1)。
    - `intent`:任務意圖**原始枚舉字串**(如 `code_generation`);中文對照由前端維護,
      後端一律傳原始值。
    - `complexity`:任務複雜度(low / medium / high)。
    """

    summary: str
    intent: str
    complexity: str


class RecommendConsensus(BaseModel):
    """推薦共識(三評審 `ai_recommend_model` 收斂,對齊 propose §5)。

    - `model`:多數推薦模型;分歧時為票數最高者;全 null → `None`。
    - `tier`:眾數模型對應 tier(同模型應一致);null 安全。
    - `votes`:眾數模型得票數。
    - `is_split`:`True` 表無嚴格過半共識(分歧),由 service 依
      `(top_votes*2 <= succeeded) and succeeded>1` 計算。
    """

    model: str | None
    tier: str | None
    votes: int
    is_split: bool


class EvaluationSummary(BaseModel):
    """本版計算的彙總(三評審 → 單一判決,對齊 propose §5)。

    - `judge_count`:候選總數。
    - `succeeded_count`:其中 AI 欄位非 null(評審成功)數,用於「部分成功」標示。
    - `avg_fit_score` / `min_fit_score` / `max_fit_score`:非 null `ai_fit_score` 的平均
      (四捨五入 3 位)與極值;全 null → `None`。**Decimal → 字串**(`str | None`)。
    - `recommend_consensus`:推薦共識(見 `RecommendConsensus`)。
    - `self_vote_count`:`ai_self_vote = True` 的候選數(自我偏好警示,裁判推薦自家廠商)。
    """

    judge_count: int
    succeeded_count: int
    avg_fit_score: str | None
    min_fit_score: str | None
    max_fit_score: str | None
    recommend_consensus: RecommendConsensus
    self_vote_count: int


class EvalCandidate(BaseModel):
    """單一評審候選(子表 dim3/4,失敗裁判 AI 欄位為 null;對齊 propose §4.2)。

    - `ai_candidate_uid` / `judge_model_uid`:候選與裁判模型 UID。
    - `judge_model_key` / `judge_model_name`:join `models` 補上的裁判 key 與顯示名
      (子表只有 `model_uid`);軟刪或取不到時為 `None`,前端顯示 UUID 尾碼。
    - `ai_recommend_model` / `ai_recommend_tier` / `ai_recommend_reason`:該裁判推薦。
    - `ai_fit_score`:吻合度,**Decimal → 字串**(`str | None`)。
    - `ai_self_vote`:該裁判是否推薦自家廠商(偏差語意,已於 0024/0025 更正)。
    """

    ai_candidate_uid: UUID
    judge_model_uid: UUID
    judge_model_key: str | None
    judge_model_name: str | None
    ai_recommend_model: str | None
    ai_recommend_tier: str | None
    ai_recommend_reason: str | None
    ai_fit_score: str | None
    ai_self_vote: bool | None


class EvaluationResult(BaseModel):
    """評審結果(父表 + 任務分析 + 彙總 + 三子候選;對齊 propose §4.2)。

    - `ai_evaluation_uid` / `usage_log_uid`:評審與來源 usage log UID(1:1)。
    - `ai_original_model`:被評審原文所用的原始模型 key。
    - `status`:評審狀態(pending / evaluated / error)。
    - `ai_evaluated_at`:評審完成時間;未完成為 `None`。
    - `task_analysis`:任務分析(父表 dim1/2);無成功評審值時為 `None`。
    - `summary`:本版彙總;失敗 / 無候選時為 `None`。
    - `candidates`:三評審明細(最多 3 筆),供 v2.0.4 細看專頁重用。
    """

    ai_evaluation_uid: UUID
    usage_log_uid: UUID
    ai_original_model: str
    status: str
    ai_evaluated_at: datetime | None
    task_analysis: TaskAnalysis | None
    summary: EvaluationSummary | None
    candidates: list[EvalCandidate]


class EvaluationResultResponse(BaseModel):
    """頂層 wrapper(對齊 propose §4.2 / 決議 #6)。

    `evaluation`:評審結果;**無評審列時為 `None`**(對應 `200 + evaluation=null`,
    非 404,避免與「log 不存在」混淆)。
    """

    evaluation: EvaluationResult | None
