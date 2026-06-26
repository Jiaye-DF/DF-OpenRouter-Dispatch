"""challenger 重跑結果讀取 API(task-408;對齊 docs/Tasks/v2.1/propose-v2.1.0.md §5.4)。

依 `usage_log_uid` 取該筆評審觸發的所有 challenger 真實重跑 + 對比裁決(GAN 閉環),
供 usage-logs 明細頁內嵌的「AI 分析」重跑對比區塊消費。

設計決議(對齊既有 v2.0.3 `ai_eval_results.py`):
- **admin-only**:對齊 usage-logs 明細頁權限,以 `AdminDep` 保護(非 admin → 403、
  未認證 → 401,皆由 `require_admin` / `require_user` 自然產生)。
- **新檔**:本端點獨立成 `ai_eval_reruns.py`,與既有 `ai_eval.py`(判別模型設定)/
  `ai_eval_results.py`(評審結果)共用 `/ai-eval` prefix / `ai-eval` tag,但職責分離。
- **無重跑 → 200 + reruns=[]**:當該 usage log 未觸發任何 challenger 重跑
  (service 回 `[]`)時,**回 200 並 `reruns=[]`**,**不 raise 404**(對齊 propose
  對外承諾;404 語意保留給「log 不存在」)。

職責邊界(對齊 propose §5.4 / `ai_eval_results.py`):**純讀**——不寫 audit、不開
transaction、不 commit。service(task-407)`build_rerun_results` 已是無副作用查詢,
本層僅組頂層 wrapper。
"""

from uuid import UUID

from fastapi import APIRouter

from app.core.deps import AdminDep, DbDep
from app.core.response import success_response
from app.schemas.ai_model_eval_rerun_result import RerunListResponse
from app.services.ai_model_eval_rerun_result import build_rerun_results

router = APIRouter(prefix="/ai-eval", tags=["ai-eval"])


@router.get(
    "/reruns/by-usage-log/{usage_log_uid}",
    summary="challenger 重跑結果(依用量紀錄,admin)",
)
async def get_reruns_by_usage_log(
    usage_log_uid: UUID,
    admin: AdminDep,
    db: DbDep,
):
    """取單筆 usage log 的所有 challenger 重跑 + 對比裁決(唯讀;對齊 propose §5.4)。

    - 權限:`AdminDep`(對齊 usage-logs 明細頁)。
    - 路徑參數 `usage_log_uid`:來源 usage_logs.usage_log_uid(明細頁手上只有此鍵)。
    - 回應:`ApiResponse` 外殼包 `RerunListResponse`(`{ reruns: RerunResult[] }`)。

    無重跑列時 service 回 `[]` → `reruns=[]`,**仍回 200**(非 404):明細頁的
    `usage_log_uid` 必然存在,空陣列表「尚未觸發重跑」而非「log 不存在」。
    """
    results = await build_rerun_results(usage_log_uid, db=db)
    payload = RerunListResponse(reruns=results).model_dump(mode="json")
    return success_response(data=payload, detail="success")
