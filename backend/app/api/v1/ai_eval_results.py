"""評審結果讀取 API(task-304;對齊 docs/Tasks/v2.0/propose-v2.0.3.md §4.1–4.3)。

依 `usage_log_uid` 取該筆 usage log 的三評審收斂結果(父表任務分析 + 本版彙總 +
三子候選),供 usage-logs 明細頁內嵌的「AI 分析」基礎摘要區塊消費。

設計決議(propose §4.2 / §6):
- **決議 #1 admin-only**:對齊 usage-logs 明細頁權限,以 `AdminDep` 保護(非 admin →
  403、未認證 → 401,皆由 `require_admin` / `require_user` 自然產生)。
- **決議 #3 新檔**:本端點獨立成 `ai_eval_results.py`,與既有 `ai_eval.py`
  (判別模型設定)共用 `/ai-eval` prefix / `ai-eval` tag,但職責分離(此檔唯讀結果)。
- **決議 #6 無評審 → 200 + evaluation=null**:當 usage log 已知存在但尚未評審
  (service 回 `None`)時,**回 200 並 `evaluation=null`**,**不 raise 404**。
  理由:404 語意是「log 不存在」;明細頁手上的 `usage_log_uid` 必然存在,只是還沒評審,
  以 `evaluation=null` 表「尚無評審」可與「log 不存在」清楚區隔,前端據此顯示空狀態。

職責邊界(對齊 propose §4.3):**純讀**——不寫 audit、不開 transaction、不 commit。
service(task-303)`build_evaluation_result` 已是無副作用查詢,本層僅組頂層 wrapper。
"""

from uuid import UUID

from fastapi import APIRouter

from app.core.deps import AdminDep, DbDep
from app.core.response import success_response
from app.schemas.ai_model_eval_result import EvaluationResultResponse
from app.services.ai_model_eval_result import build_evaluation_result

router = APIRouter(prefix="/ai-eval", tags=["ai-eval"])


@router.get(
    "/evaluations/by-usage-log/{usage_log_uid}",
    summary="評審結果(依用量紀錄,admin)",
)
async def get_evaluation_by_usage_log(
    usage_log_uid: UUID,
    admin: AdminDep,
    db: DbDep,
):
    """取單筆 usage log 的評審結果(唯讀;對齊 propose §4.1)。

    - 權限:`AdminDep`(決議 #1,對齊 usage-logs 明細頁)。
    - 路徑參數 `usage_log_uid`:來源 usage_logs.usage_log_uid(1:1 直查)。
    - 回應:`ApiResponse` 外殼包 `EvaluationResultResponse`
      (`{ evaluation: EvaluationResult | None }`)。

    無評審列時 service 回 `None` → `evaluation=null`,**仍回 200**(決議 #6,非 404):
    明細頁的 `usage_log_uid` 必然存在,`null` 表「尚未評審」而非「log 不存在」。
    """
    result = await build_evaluation_result(usage_log_uid, db=db)
    payload = EvaluationResultResponse(evaluation=result).model_dump(mode="json")
    return success_response(data=payload, detail="success")
