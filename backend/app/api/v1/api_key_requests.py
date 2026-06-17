from uuid import UUID

from fastapi import APIRouter, Query
from uuid_utils import uuid7

from app.core.audit import write_audit
from app.core.deps import ClientIpDep, DbDep, UserDep
from app.core.response import success_response
from app.models.api_key_request import ApiKeyRequest
from app.repositories.api_key_request import ApiKeyRequestRepository
from app.schemas.api_key_request import (
    ApiKeyRequestCreateRequest,
    ApiKeyRequestResponse,
)
from app.schemas.common import Page

router = APIRouter(prefix="/api-key-requests", tags=["api-key-requests"])


@router.get("", summary="API Key 申請列表（admin 全部 / member 僅本人）")
async def list_api_key_requests(
    actor: UserDep,
    db: DbDep,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
):
    repo = ApiKeyRequestRepository(db)
    # 範圍由後端強制決定:admin 看全部,member 只看自己(忽略任何前端參數)。
    only = None if actor.is_admin else actor.user_uid
    items, total = await repo.list(page=page, size=size, applicant_user_uid=only)
    data = Page[ApiKeyRequestResponse](
        items=[ApiKeyRequestResponse.model_validate(x) for x in items],
        total=total,
        page=page,
        size=size,
    )
    return success_response(data=data.model_dump(mode="json"), detail="success")


@router.post("", summary="送出 API Key 申請（登入即可）")
async def create_api_key_request(
    body: ApiKeyRequestCreateRequest,
    actor: UserDep,
    db: DbDep,
    ip: ClientIpDep,
):
    repo = ApiKeyRequestRepository(db)
    row = ApiKeyRequest(
        request_uid=UUID(str(uuid7())),
        applicant_user_uid=actor.user_uid,
        department_name=body.department_name,
        department_code=body.department_code,
        project_name=body.project_name,
        project_url=body.project_url,
        owner_name=body.owner_name,
        owner_email=body.owner_email,
        status="pending",
    )
    repo.add(row)
    await db.flush()
    await write_audit(
        db,
        actor_user_uid=actor.user_uid,
        actor_role=actor.role,
        action="create_api_key_request",
        target_type="api_key_request",
        target_uid=row.request_uid,
        ip=ip,
    )
    await db.commit()
    return success_response(
        data=ApiKeyRequestResponse.model_validate(row).model_dump(mode="json"),
        detail="success",
    )
