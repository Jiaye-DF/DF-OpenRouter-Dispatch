"""AI 推薦模型「真實重跑 + 對比裁決」唯讀讀取 API(對齊 propose §5.4)。

**單一**分組總覽端點:跨用量紀錄取所有 AI 推薦模型真實重跑 + 對比裁決,**依用量紀錄分組**
回傳(每組 = 一筆原始呼叫 + 原模型真實輸出原文 + 其底下去重後的推薦模型),供前端
「AI 判決總覽」並排比較頁消費。

設計決議(對齊既有 v2.0.3 `ai_eval_results.py`):
- **admin-only**:以 `AdminDep` 保護(非 admin → 403、未認證 → 401)。
- **單一端點**:讀取全收斂到 `/reruns`(總覽);舊「依用量紀錄查單筆」端點已移除。
- **無資料 → 200 + items=[]**:不 raise 404(404 語意保留給「資源不存在」)。

職責邊界:**純讀**——不寫 audit、不開 transaction、不 commit。service(task-407)
`build_rerun_overview` 已是無副作用查詢,本層僅組外殼。
"""

from fastapi import APIRouter, Query

from app.core.deps import AdminDep, DbDep
from app.core.response import success_response
from app.services.ai_model_eval_rerun_result import build_rerun_overview

router = APIRouter(prefix="/ai-eval", tags=["ai-eval"])


@router.get(
    "/reruns",
    summary="AI 判決總覽(跨 log,依用量紀錄分組,分頁,admin)",
)
async def list_reruns_overview(
    admin: AdminDep,
    db: DbDep,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    pid: int | None = Query(default=None, ge=1),
):
    """跨 log 取 AI 推薦模型真實重跑 + 對比裁決,依用量紀錄分組回傳(唯讀,分頁)。

    - 權限:`AdminDep`(對齊既有 AI 分析端點)。
    - 排序:依用量紀錄編號 `pid` 排序(`order=desc` 大→小,預設;`asc` 小→大)。
    - 搜尋:`pid` 給值時精確比對該筆編號;`total` = 分組組數。
    - 回應:`ApiResponse` 外殼包 `RerunOverviewPage`(items/total/page/size/stats);
      每組帶原模型輸出原文 + 各推薦模型輸出原文 + 成本Δ + 裁決 + 裁決分布統計。
    """
    page_data = await build_rerun_overview(
        db=db, page=page, size=size, order=order, pid=pid
    )
    return success_response(
        data=page_data.model_dump(mode="json"), detail="success"
    )
