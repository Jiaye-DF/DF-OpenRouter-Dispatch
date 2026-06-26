"""challenger 重跑結果對外讀取 schema(v2.1.0;對齊 docs/Tasks/v2.1/propose-v2.1.0.md §5.4)。

本檔承載「challenger 真實重跑 + 對比裁決**唯讀展示**」對外結構:依 `usage_log_uid` 取
該筆評審觸發的所有 challenger 重跑(真實 API 結果)與「原輸出 vs challenger 輸出」的
AI discriminator 裁決(GAN/champion-challenger 閉環),供查詢 API(task-408)消費。

職責邊界(對齊既有 `ai_model_eval_result.py`):
- 全為**唯讀** response 模型,不含任何 CRUD / 驗證邏輯。
- **Decimal → 字串傳輸**:所有金額(`cost_usd` / `original_cost_usd` / `cost_delta_usd`)
  與信心分數(`compare_score`)一律宣告為 `str | None`,避免 JS 浮點誤差(專案既有慣例,
  對齊 `docs/Design-Base/04-databases/05-precision.md`)。實際 Decimal → str 轉換由
  service(`ai_model_eval_rerun_result.build_rerun_results`)負責,此檔僅負責「型別宣告」。
- **無重跑列時**:`RerunListResponse.reruns` 為空 list `[]`(對齊 propose 對外承諾
  「無則 `200 + data.reruns=[]`」,非 None / 非 404)。
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class RerunResult(BaseModel):
    """單一 challenger 重跑 + 對比裁決結果(對應一筆 `ai_model_eval_reruns`;對齊 propose §5.4)。

    模型:
    - `rerun_model`:challenger 模型 key(實際重跑)。
    - `model_uid`:challenger `models.model_uid`(軟引用;取不到為 `None`)。

    真實用量 / 成本(challenger 真實 API 結果;失敗列可能為 `None`):
    - `prompt_tokens` / `completion_tokens` / `total_tokens`:真實 token 數。
    - `cost_usd`:challenger 真實成本(USD);**Decimal → 字串**(`str | None`)。
    - `original_cost_usd`:原呼叫成本(denormalize,對比);**Decimal → 字串**。
    - `cost_delta_usd`:成本差 challenger − original(客觀指標);**Decimal → 字串**。
    - `latency_ms`:challenger 延遲(毫秒)。

    狀態:
    - `status`:重跑狀態(success / error)。
    - `error_code`:錯誤碼;無錯誤為 `None`。

    對比裁決(discriminator;子開關停用時整組為 `None`):
    - `compare_winner`:裁決 original / challenger / tie。
    - `compare_score`:信心分數 0–1;**Decimal → 字串**(`str | None`)。
    - `compare_reason`:裁決理由。
    - `compare_judge_model`:擔任裁決的模型 key(推薦該 challenger 的評審本人)。

    `triggered_at`:重跑執行時間。
    """

    rerun_model: str
    model_uid: UUID | None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    cost_usd: str | None
    original_cost_usd: str | None
    cost_delta_usd: str | None
    latency_ms: int | None
    status: str
    error_code: str | None
    compare_winner: str | None
    compare_score: str | None
    compare_reason: str | None
    compare_judge_model: str | None
    triggered_at: datetime


class RerunListResponse(BaseModel):
    """頂層 wrapper(對齊 propose §5.4)。

    `reruns`:該 usage_log 對應評審的所有 challenger 重跑;**無重跑列時為空 list `[]`**
    (對應 `200 + data.reruns=[]`,非 404,與「log 不存在」區隔)。
    """

    reruns: list[RerunResult]


class RerunOverviewItem(BaseModel):
    """AI 判決總覽頁(跨 log)單列:一筆 challenger 重跑 + 對比裁決 + 來源 log 連結資訊。

    對齊 `RerunResult` 的 Decimal → 字串慣例;額外帶 `usage_log_uid`(供前端連到
    usage-logs 明細頁)與 `original_model`(原模型,用於「原 → challenger」並列顯示)。
    """

    usage_log_uid: UUID
    original_model: str
    rerun_model: str
    status: str
    error_code: str | None
    cost_usd: str | None
    cost_delta_usd: str | None
    latency_ms: int | None
    compare_winner: str | None
    compare_score: str | None
    compare_judge_model: str | None
    triggered_at: datetime


class RerunOverviewPage(BaseModel):
    """AI 判決總覽分頁 wrapper(對齊 `schemas.common.Page` 形狀:items/total/page/size)。"""

    items: list[RerunOverviewItem]
    total: int
    page: int
    size: int
