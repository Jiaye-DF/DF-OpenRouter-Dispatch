"""AI 推薦模型「真實重跑 + 對比裁決」唯讀讀取 schema(v2.1.0 重做;對齊 propose §5.4 / §6.1)。

本檔承載「AI 判決總覽」對外結構:**依用量紀錄(usage_log)分組**,每組帶原模型 +
各 AI 推薦模型的**真實輸出原文**,供查詢 API(task-408)與前端並排比較頁消費。

名詞(對齊 propose 名詞約定,移除黑話):
- **原模型** = 使用者實際呼叫、寫進 `usage_logs` 的模型。
- **AI 推薦模型** = 評審推薦、且 ≠ 原模型的模型(DB 欄位仍叫 `rerun_model`)。
- **對比裁決** = AI 比對「原模型輸出 vs 推薦模型輸出」何者較佳的結果(`compare_*`)。

職責邊界(對齊既有 `ai_model_eval_result.py`):
- 全為**唯讀** response 模型,不含任何 CRUD / 驗證邏輯。
- **Decimal → 字串傳輸**:所有金額(`cost_usd` / `original_cost_usd` / `cost_delta_usd`)
  與信心分數(`compare_score`)一律宣告為 `str | None`,避免 JS 浮點誤差(對齊
  `docs/Design-Base/04-databases/05-precision.md` + 既有慣例)。Decimal → str 轉換由
  service(`ai_model_eval_rerun_result.build_rerun_overview`)負責,此檔僅負責「型別宣告」。
- **輸出原文**:`original_output_text`(原模型,取自 `usage_logs.response_summary.output_text`)
  與 `RerunRecommendation.output_text`(推薦模型,取自 `ai_model_eval_reruns.response_summary.output_text`)
  皆 `str | None`(歷史 log 未存快照 / 失敗列 → None)。
- **無資料時**:`RerunOverviewPage.items` 為空 list `[]`(對齊 propose 對外承諾
  「無則 `200 + items=[]`」,非 None / 非 404)。
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class RerunRecommendation(BaseModel):
    """單一 AI 推薦模型的真實重跑 + 對比裁決(對應一筆 `ai_model_eval_reruns`;對齊 propose §5.4)。

    模型:
    - `rerun_model`:AI 推薦模型 key(實際重跑)。
    - `model_uid`:推薦模型 `models.model_uid`(軟引用;取不到為 `None`)。
    - `output_text`:推薦模型**真實輸出原文**(取自 `response_summary.output_text`;
      歷史未存 / 失敗列 → `None`)。

    真實用量 / 成本(推薦模型真實 API 結果;失敗列可能為 `None`):
    - `prompt_tokens` / `completion_tokens` / `total_tokens`:真實 token 數。
    - `cost_usd`:推薦模型真實成本(USD);**Decimal → 字串**(`str | None`)。
    - `cost_delta_usd`:成本差 推薦模型 − 原(客觀指標);**Decimal → 字串**。
    - `latency_ms`:推薦模型延遲(毫秒)。

    狀態:
    - `status`:重跑狀態(success / error)。
    - `error_code`:錯誤碼;無錯誤為 `None`。

    對比裁決(子開關停用時整組為 `None`):
    - `compare_winner`:裁決 original / challenger / tie。
    - `compare_score`:信心分數 0–1;**Decimal → 字串**(`str | None`)。
    - `compare_reason`:裁決理由。
    - `compare_judge_model`:擔任裁決的模型 key(推薦該模型的評審本人)。

    推薦來源:
    - `recommended_by`:這個推薦模型是「哪個評審模型推薦的」(評審模型 key)。
      讀取層由 candidate 反查 derive 得來(對該筆評審查候選清單,以本列的
      `ai_candidate_uid` 對映回推薦它的評審模型),**不是** `compare_judge_model`
      ——後者只有實際跑過裁決才有值(失敗 / 未裁決時為 None,不可靠)。
      查不到對應候選(候選已軟刪 / 無 `ai_candidate_uid`)→ `None`。

    `triggered_at`:重跑執行時間。
    """

    rerun_model: str
    model_uid: UUID | None
    output_text: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    cost_usd: str | None
    cost_delta_usd: str | None
    latency_ms: int | None
    status: str
    error_code: str | None
    compare_winner: str | None
    compare_score: str | None
    compare_reason: str | None
    compare_judge_model: str | None
    recommended_by: str | None
    triggered_at: datetime


class RerunUsageLogInfo(BaseModel):
    """對應那筆用量紀錄(usage_log)的基礎資訊(供前端 Dialog 顯示,非只給 uid)。

    全取自讀取層已反查的同一筆 `usage_logs` row(不另查 DB);供前端展示「這組重跑
    源自哪一次呼叫」的人類可讀 metadata。

    - `pid`:該筆用量紀錄的顯示編號(#pid);與用量紀錄頁同一編號,供 admin 互相對應。
    - `created_at`:該筆呼叫時間。
    - `model`:呼叫的模型 key。
    - `status`:呼叫狀態(success / error 等)。
    - `prompt_tokens` / `completion_tokens` / `total_tokens`:該筆呼叫的 token 數。
    - `cost_usd`:該筆呼叫成本(USD);**Decimal → 字串**(沿用金額字串慣例避免 JS 浮點誤差)。
    - `latency_ms`:該筆呼叫延遲(毫秒)。
    - `used_tools`:該筆呼叫是否帶 tools(如 web search)。
    - `error_code`:錯誤碼;無錯誤為 `None`。
    """

    pid: int
    created_at: datetime
    model: str
    status: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: str
    latency_ms: int
    used_tools: bool
    error_code: str | None


class RerunGroup(BaseModel):
    """一組 = 一筆用量紀錄(對齊 propose §5.4 / §6.1)。

    每組 = 一筆原始呼叫(原模型 + 原模型真實輸出原文 + 原成本)+ 其底下去重後的
    1–N 個 AI 推薦模型(`recommendations`)。

    - `usage_log_uid`:分組鍵(來源 usage_logs.usage_log_uid)。
    - `original_model`:原模型 key(denormalize,並排顯示)。
    - `original_output_text`:原模型**真實輸出原文**(取自 `usage_logs.response_summary.output_text`;
      歷史 log 未存快照 → `None`,前端顯示「無原始輸出快照」)。
    - `original_input_text`:該筆呼叫的「任務輸入」原文(取自 `usage_logs.request_content`,
      經 `request_snapshot.input_text_of` 正規化:單輪快照取 `text`、messages 直傳快照取
      **最後一則 user 訊息**的文字)。request_content 為 NULL / 無任何文字 → `None`。
    - `original_cost_usd`:原呼叫成本(USD);**Decimal → 字串**(`str | None`)。
    - `evaluated_at`:該組最新一筆推薦模型的重跑執行時間(供排序 / 顯示;無列 → `None`)。
    - `usage_log_info`:對應那筆用量紀錄的基礎資訊(供 Dialog 顯示;該筆 usage_log
      不存在 / 歷史已刪 → `None`)。
    - `recommendations`:去重後的 AI 推薦模型列(最新優先)。
    """

    usage_log_uid: UUID
    original_model: str
    original_output_text: str | None
    original_input_text: str | None
    original_cost_usd: str | None
    evaluated_at: datetime | None
    usage_log_info: RerunUsageLogInfo | None
    recommendations: list[RerunRecommendation]


class RerunStats(BaseModel):
    """跨 log 裁決分布(頁頂輕量彙總;對齊 propose §6.1)。

    計數定義(針對當頁分組內的所有推薦模型):
    - `total_recommendations`:推薦模型總筆數。
    - `keep_count`:`compare_winner='original'`(建議維持原模型)。
    - `swap_count`:`compare_winner='challenger'`(建議改用推薦模型)。
    - `tie_count`:`compare_winner='tie'`(平手)。
    - `unjudged_count`:`status='success'` 但 `compare_winner IS NULL`(已重跑·未裁決)。
    - `failed_count`:`status != 'success'`(重跑失敗)。
    """

    total_recommendations: int
    keep_count: int
    swap_count: int
    tie_count: int
    unjudged_count: int
    failed_count: int


class RerunOverviewPage(BaseModel):
    """AI 判決總覽分頁 wrapper(對齊 `schemas.common.Page` 形狀:items/total/page/size + stats)。

    - `items`:當頁 `RerunGroup[]`(依用量紀錄分組,最新優先)。
    - `total`:**分組後的總組數**(distinct usage_log,非重跑列數)。
    - `page` / `size`:分頁參數回放。
    - `stats`:當頁分組內推薦模型的裁決分布彙總。
    """

    items: list[RerunGroup]
    total: int
    page: int
    size: int
    stats: RerunStats
