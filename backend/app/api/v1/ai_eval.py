"""判別模型設定 API(對齊 docs/Tasks/v2.0/task-002-judge-settings-api.md、propose §5)。

- GET /api/v1/ai-eval/judge-settings(admin):回目前 3 個判別模型槽位。
- PUT /api/v1/ai-eval/judge-settings(admin):整批覆寫 3 個槽位。

驗證(非 3 個 / 重複 / 不存在 / 已停用或軟刪除)一律於 endpoint 內以
AppError(code=422) 回應,確保前端拿到 422(本專案 RequestValidationError → 400,
故不依賴 Pydantic validator 的自然 422)。
"""

from uuid import UUID

from fastapi import APIRouter
from uuid_utils import uuid7

from app.core.audit import write_audit
from app.core.deps import AdminDep, ClientIpDep, DbDep
from app.core.exceptions import AppError
from app.core.response import success_response
from app.models.ai_eval_judge_setting import AiEvalJudgeSetting
from app.repositories.ai_eval_judge_setting import AiEvalJudgeSettingRepository
from app.schemas.ai_eval import JudgeSettingRead, JudgeSettingsPutRequest

router = APIRouter(prefix="/ai-eval", tags=["ai-eval"])

JUDGE_SLOT_COUNT = 3


async def _read_current(repo: AiEvalJudgeSettingRepository) -> list[dict]:
    """組目前判別模型設定的對外 payload(含模型顯示資訊)。"""
    settings = await repo.list_active()
    if not settings:
        return []
    model_uids = [s.model_uid for s in settings]
    models = await repo.list_active_models_by_uids(model_uids)
    model_by_uid = {m.model_uid: m for m in models}
    data: list[dict] = []
    for s in settings:
        m = model_by_uid.get(s.model_uid)
        data.append(
            JudgeSettingRead(
                ai_judge_slot=s.ai_judge_slot,
                model_uid=s.model_uid,
                model_key=m.model_key if m else "",
                name=m.name if m else "",
            ).model_dump(mode="json")
        )
    return data


@router.get("/judge-settings", summary="判別模型設定(admin)")
async def get_judge_settings(admin: AdminDep, db: DbDep):
    repo = AiEvalJudgeSettingRepository(db)
    data = await _read_current(repo)
    return success_response(data=data, detail="success")


@router.put("/judge-settings", summary="整批設定判別模型(admin)")
async def put_judge_settings(
    body: JudgeSettingsPutRequest,
    admin: AdminDep,
    db: DbDep,
    ip: ClientIpDep,
):
    model_uids = body.model_uids

    # 1) 長度恰 3
    if len(model_uids) != JUDGE_SLOT_COUNT:
        raise AppError("judge_models_must_be_three", code=422)

    # 2) 不可重複
    if len(set(model_uids)) != JUDGE_SLOT_COUNT:
        raise AppError("judge_models_duplicated", code=422)

    repo = AiEvalJudgeSettingRepository(db)

    # 3) 每個 model_uid 須存在且 active / 未軟刪除
    active_models = await repo.list_active_models_by_uids(model_uids)
    active_uids = {m.model_uid for m in active_models}
    missing = [str(u) for u in model_uids if u not in active_uids]
    if missing:
        raise AppError("judge_model_not_active", code=422, data={"model_uids": missing})

    # 4) 先軟刪舊有效設定釋放 slot unique,flush 後再寫新 3 筆
    await repo.soft_delete_active()

    for slot, model_uid in enumerate(model_uids, start=1):
        repo.add(
            AiEvalJudgeSetting(
                ai_judge_setting_uid=UUID(str(uuid7())),
                model_uid=model_uid,
                ai_judge_slot=slot,
            )
        )
    await db.flush()

    await write_audit(
        db,
        actor_user_uid=admin.user_uid,
        actor_role=admin.role,
        action="update_ai_judge_settings",
        target_type="ai_eval_judge_setting",
        target_uid=None,
        ip=ip,
        extra={"model_uids": [str(u) for u in model_uids]},
    )
    await db.commit()

    data = await _read_current(repo)
    return success_response(data=data, detail="success")
