from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from uuid_utils import uuid7

from app.clients.openrouter.client import OpenRouterClient, get_openrouter_client
from app.core.audit import write_audit
from app.core.deps import ClientIpDep, DbDep, UserDep
from app.core.exceptions import AppError
from app.core.response import success_response
from app.models.api_key_request import ApiKeyRequest
from app.repositories.api_key_request import ApiKeyRequestRepository
from app.schemas.actor import Actor
from app.schemas.api_key_request import (
    ApiKeyRequestCreateRequest,
    ApiKeyRequestDetailResponse,
    ApiKeyRequestResponse,
    CancelRequest,
)
from app.schemas.common import Page
from app.services import api_key_request_agent as agent
from app.services import api_key_request_provision as provision
from app.services import api_key_request_router as router_svc
from app.services.email_graph import send_provision_email

router = APIRouter(prefix="/api-key-requests", tags=["api-key-requests"])

# AI 欄位驗證信心分數達此門檻才自動開通,否則降級人工(v1.9.x 由 95 調整為 90)。
AI_AUTO_PROVISION_THRESHOLD = 90


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _detail(row: ApiKeyRequest) -> dict:
    return ApiKeyRequestDetailResponse.model_validate(row).model_dump(mode="json")


async def _get_or_404(repo: ApiKeyRequestRepository, uid: UUID) -> ApiKeyRequest:
    row = await repo.get_by_uid(uid)
    if row is None:
        raise AppError("not_found", code=404)
    return row


async def _notify_owner(
    db: DbDep,
    row: ApiKeyRequest,
    actor: Actor,
    ip: str | None,
    *,
    action: str = "notify_api_key_request",
) -> None:
    """開通成功後 best-effort 寄信通知負責人,另起一次 commit 回寫 notified_at / notify_error。

    寄信失敗(含 M365 未設定)不影響已開通結果;憑證明文不入 log。
    """
    result = await send_provision_email(
        to_email=row.owner_email,
        owner_name=row.owner_name,
        project_name=row.project_name,
        secrets=row.provisioned_secrets or {},
    )
    if result.ok:
        row.notified_at = _now()
        row.notify_error = None
    else:
        row.notify_error = result.error
    await write_audit(
        db,
        actor_user_uid=actor.user_uid,
        actor_role=actor.role,
        action=action,
        target_type="api_key_request",
        target_uid=row.request_uid,
        result="success" if result.ok else "failure",
        ip=ip,
        # 僅記收件網域,不記完整 email / 憑證
        detail=row.owner_email.split("@")[-1],
    )
    await db.commit()


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


@router.post("", summary="送出 API Key 申請（同步 route→AI→provision）")
async def create_api_key_request(
    body: ApiKeyRequestCreateRequest,
    actor: UserDep,
    db: DbDep,
    ip: ClientIpDep,
    client: Annotated[OpenRouterClient, Depends(get_openrouter_client)],
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
        status="manual_pending",
    )
    repo.add(row)
    await db.flush()

    route = await router_svc.route(db, row)

    if route.decision == "system_cancel":
        row.status = "cancelled"
        row.cancel_source = "system"
        row.cancel_reason = route.reason
        row.processed_at = _now()
    elif route.decision == "manual":
        row.status = "manual_pending"
        # manual 無 agent_decision;將路由理由放入 error_message 供前端顯示。
        row.error_message = route.reason
        if route.matched_department is not None:
            row.matched_department_uid = route.matched_department.department_uid
    else:  # "ai"
        decision_ai = await agent.validate_fields(
            client, row, route.matched_department
        )
        row.agent_decision = {
            "confidence": decision_ai.confidence,
            "reason": decision_ai.reason,
            "error": decision_ai.error,
        }
        if decision_ai.error:
            row.error_message = decision_ai.error

        if decision_ai.confidence >= AI_AUTO_PROVISION_THRESHOLD:
            pr = None
            try:
                async with db.begin_nested():
                    pr = await provision.provision(db, row, route, actor=actor)
                    if not pr.ok:
                        # 觸發 savepoint rollback,撤回開通寫入
                        raise RuntimeError(pr.error or "provision_failed")
            except Exception:  # noqa: BLE001 - 開通失敗一律降級人工
                row.status = "manual_pending"
                row.error_message = (pr.error if pr is not None else None) or "自動開通失敗"
            else:
                row.status = "agent_done"
                row.matched_department_uid = pr.matched_department_uid
                row.created_project_uid = pr.created_project_uid
                row.created_user_uid = pr.created_user_uid
                row.created_sdk_key_uid = pr.created_sdk_key_uid
                row.provisioned_secrets = pr.provisioned_secrets
                row.processed_at = _now()
                await write_audit(
                    db,
                    actor_user_uid=actor.user_uid,
                    actor_role=actor.role,
                    action="auto_provision_api_key_request",
                    target_type="api_key_request",
                    target_uid=row.request_uid,
                    ip=ip,
                )
        else:
            row.status = "manual_pending"

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
    # 開通成功才寄信通知負責人(best-effort,獨立 commit,失敗不影響開通)
    if row.status == "agent_done":
        await _notify_owner(db, row, actor, ip)
    return success_response(data=_detail(row), detail="success")


@router.post("/{uid}/cancel", summary="取消申請（本人，限 manual_pending）")
async def cancel_api_key_request(
    uid: UUID,
    body: CancelRequest,
    actor: UserDep,
    db: DbDep,
    ip: ClientIpDep,
):
    repo = ApiKeyRequestRepository(db)
    row = await _get_or_404(repo, uid)
    if row.applicant_user_uid != actor.user_uid and not actor.is_admin:
        raise AppError("forbidden", code=403)
    if row.status != "manual_pending":
        raise AppError("invalid_status", code=409)

    row.status = "cancelled"
    row.cancel_source = "user"
    row.cancel_reason = body.reason
    row.processed_at = _now()
    await write_audit(
        db,
        actor_user_uid=actor.user_uid,
        actor_role=actor.role,
        action="cancel_api_key_request",
        target_type="api_key_request",
        target_uid=row.request_uid,
        ip=ip,
        detail=body.reason,
    )
    await db.commit()
    return success_response(data=_detail(row), detail="success")


@router.post("/{uid}/revoke", summary="撤銷申請（本人/admin，限 manual_pending）")
async def revoke_api_key_request(
    uid: UUID,
    actor: UserDep,
    db: DbDep,
    ip: ClientIpDep,
):
    repo = ApiKeyRequestRepository(db)
    row = await _get_or_404(repo, uid)
    if row.applicant_user_uid != actor.user_uid and not actor.is_admin:
        raise AppError("forbidden", code=403)
    # 已處理(agent_done / done)禁止撤銷;撤銷僅限 manual_pending。
    if row.status != "manual_pending":
        raise AppError("invalid_status", code=409)

    row.status = "revoked"
    row.processed_at = _now()
    await write_audit(
        db,
        actor_user_uid=actor.user_uid,
        actor_role=actor.role,
        action="revoke_api_key_request",
        target_type="api_key_request",
        target_uid=row.request_uid,
        ip=ip,
    )
    await db.commit()
    return success_response(data=_detail(row), detail="success")


@router.post("/{uid}/process", summary="人工處理開通（admin，確定性開通 → done）")
async def process_api_key_request(
    uid: UUID,
    actor: UserDep,
    db: DbDep,
    ip: ClientIpDep,
):
    if not actor.is_admin:
        raise AppError("forbidden", code=403)
    repo = ApiKeyRequestRepository(db)
    row = await _get_or_404(repo, uid)
    if row.status != "manual_pending":
        raise AppError("invalid_status", code=409)

    route = await router_svc.route(db, row)
    if route.matched_department is None:
        # 新部門 / 硬規則命中:無既有部門可沿用開通,須先於後台建立部門與 Key。
        raise AppError("manual_provision_requires_department", code=409)

    pr = None
    try:
        async with db.begin_nested():
            pr = await provision.provision(db, row, route, actor=actor)
            if not pr.ok:
                raise RuntimeError(pr.error or "provision_failed")
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        raise AppError(
            (pr.error if pr is not None else None) or "provision_failed", code=409
        ) from exc

    row.status = "done"
    row.handled_by_user_uid = actor.user_uid
    row.matched_department_uid = pr.matched_department_uid
    row.created_project_uid = pr.created_project_uid
    row.created_user_uid = pr.created_user_uid
    row.created_sdk_key_uid = pr.created_sdk_key_uid
    row.provisioned_secrets = pr.provisioned_secrets
    row.processed_at = _now()
    await write_audit(
        db,
        actor_user_uid=actor.user_uid,
        actor_role=actor.role,
        action="process_api_key_request",
        target_type="api_key_request",
        target_uid=row.request_uid,
        ip=ip,
    )
    await db.commit()
    # 人工開通成功後寄信通知負責人(best-effort,獨立 commit)
    await _notify_owner(db, row, actor, ip)
    return success_response(data=_detail(row), detail="success")


@router.post("/{uid}/resend-notify", summary="重送開通通知 Email（admin）")
async def resend_notify_api_key_request(
    uid: UUID,
    actor: UserDep,
    db: DbDep,
    ip: ClientIpDep,
):
    if not actor.is_admin:
        raise AppError("forbidden", code=403)
    repo = ApiKeyRequestRepository(db)
    row = await _get_or_404(repo, uid)
    # 僅開通終態可重送
    if row.status not in ("agent_done", "done"):
        raise AppError("invalid_status", code=409)
    # 憑證已被本人領取清空 → 無可寄內容
    if not row.provisioned_secrets:
        raise AppError("secrets_already_claimed", code=409)

    await _notify_owner(db, row, actor, ip, action="resend_notify_api_key_request")
    return success_response(data=_detail(row), detail="success")


@router.get("/{uid}", summary="申請詳情（本人/admin，本人僅自己）")
async def get_api_key_request(
    uid: UUID,
    actor: UserDep,
    db: DbDep,
):
    repo = ApiKeyRequestRepository(db)
    row = await _get_or_404(repo, uid)
    if row.applicant_user_uid != actor.user_uid and not actor.is_admin:
        raise AppError("forbidden", code=403)
    return success_response(data=_detail(row), detail="success")


@router.post("/{uid}/claim-secrets", summary="領取一次性憑證（本人，領取後清空）")
async def claim_api_key_request_secrets(
    uid: UUID,
    actor: UserDep,
    db: DbDep,
    ip: ClientIpDep,
):
    repo = ApiKeyRequestRepository(db)
    row = await _get_or_404(repo, uid)
    if row.applicant_user_uid != actor.user_uid:
        raise AppError("forbidden", code=403)

    secrets = row.provisioned_secrets
    row.provisioned_secrets = None
    await write_audit(
        db,
        actor_user_uid=actor.user_uid,
        actor_role=actor.role,
        action="claim_secrets_api_key_request",
        target_type="api_key_request",
        target_uid=row.request_uid,
        ip=ip,
    )
    await db.commit()
    detail = "success" if secrets else "已無可領取的憑證(可能已領取)"
    return success_response(data={"provisioned_secrets": secrets}, detail=detail)
