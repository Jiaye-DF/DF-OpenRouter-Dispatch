from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils import uuid7

from app.clients.openrouter.client import OpenRouterClient, get_openrouter_client
from app.core.audit import write_audit
from app.core.config import get_settings
from app.core.deps import ClientIpDep, DbDep, UserDep
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.core.response import success_response
from app.models.api_key_request import ApiKeyRequest
from app.repositories.api_key_request import ApiKeyRequestRepository
from app.repositories.user import UserRepository
from app.schemas.actor import Actor
from app.schemas.api_key_request import (
    ApiKeyRequestCreateRequest,
    ApiKeyRequestDetailResponse,
    ApiKeyRequestResponse,
    CancelRequest,
    RevokeRequest,
)
from app.schemas.common import Page
from app.services import api_key_request_agent as agent
from app.services import api_key_request_provision as provision
from app.services import api_key_request_router as router_svc
from app.services.email_graph import send_admin_notify_email, send_provision_email

logger = get_logger(__name__)

router = APIRouter(prefix="/api-key-requests", tags=["api-key-requests"])

# AI 欄位驗證信心分數達此門檻才自動開通,否則降級人工(v1.9.x 由 95 調整為 90)。
AI_AUTO_PROVISION_THRESHOLD = 90


def _now() -> datetime:
    return datetime.now(tz=UTC)


async def _lock_dedup_key(db: AsyncSession, *, department_code: str, project_name: str, owner_email: str) -> None:
    """交易級 advisory lock,序列化「同部門+同專案+同負責人」併發送單。

    避免兩個並發請求都在 route() 看到「無既有資料」而各自開通,重複建立
    Project / User / SDK Key 並繞過 system_cancel 去重。鎖隨交易 commit 自動釋放;
    後到者會等先到者 commit 後再 route(),屆時即可正確走沿用/去重路徑。
    """
    key = f"{department_code.strip().lower()}|{project_name.strip().lower()}|{owner_email.strip().lower()}"
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:k)::bigint)"), {"k": key}
    )


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


async def notify_admin_on_verdict(
    db: DbDep,
    row: ApiKeyRequest,
    actor: Actor,
    ip: str | None,
) -> None:
    """申請單進入終態後 best-effort 加寄一封判決通知信給系統管理員(propose §D.4/§D.5/§D.6)。

    與 `_notify_owner` 平行、獨立 try/except:總開關關閉直接 return;查無管理員 /
    管理員無 email 只落 info log 後 return(不寄、不報錯)。寄送成敗**僅落結構化 log**,
    **不**寫 DB 欄位(D.6);任何例外都吞掉只落 log,**不**回滾申請單狀態、**不**影響申請人通知。
    """
    settings = get_settings()
    if not settings.APIREQ_ADMIN_NOTIFY_ENABLED:
        return
    try:
        admin = await UserRepository(db).get_by_account(settings.INITIAL_ADMIN_ACCOUNT)
        if admin is None or not admin.email:
            logger.info(
                "管理員通知略過:帳號 %s 不存在或無 email request_uid=%s",
                settings.INITIAL_ADMIN_ACCOUNT,
                row.request_uid,
            )
            return
        decision = row.agent_decision if isinstance(row.agent_decision, dict) else {}
        reason = decision.get("reason")
        result = await send_admin_notify_email(
            to_email=admin.email,
            applicant_name=row.owner_name,
            department=row.department_name,
            project_name=row.project_name,
            status=row.status,
            reason=reason,
            request_uid=str(row.request_uid),
        )
        if result.ok:
            logger.info(
                "管理員通知已寄出 status=%s request_uid=%s domain=%s",
                row.status,
                row.request_uid,
                admin.email.split("@")[-1],
            )
        else:
            logger.info(
                "管理員通知未寄出 status=%s request_uid=%s error=%s",
                row.status,
                row.request_uid,
                result.error,
            )
    except Exception:  # noqa: BLE001 - best-effort:任何例外都不得影響主流程 / 申請人通知
        logger.exception("管理員通知失敗 request_uid=%s", row.request_uid)


@router.get("", summary="API Key 申請列表（admin 全部 / member 僅本人）")
async def list_api_key_requests(
    actor: UserDep,
    db: DbDep,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    status: str | None = Query(default=None, description="申請狀態精確篩選"),
    q: str | None = Query(default=None, description="關鍵字:專案/負責人/Email/部門"),
    department_code: str | None = Query(default=None, description="部門代號精確篩選"),
    from_time: datetime | None = Query(default=None, alias="from", description="建立時間起"),
    to_time: datetime | None = Query(default=None, alias="to", description="建立時間迄"),
):
    repo = ApiKeyRequestRepository(db)
    # 範圍由後端強制決定:admin 看全部,member 只看自己(忽略任何前端參數)。
    only = None if actor.is_admin else actor.user_uid
    items, total = await repo.list(
        page=page,
        size=size,
        applicant_user_uid=only,
        status=status,
        q=q,
        department_code=department_code,
        from_time=from_time,
        to_time=to_time,
    )
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
    # 先取去重鎖,序列化同 (部門+專案+負責人) 的併發送單,再進 route→provision。
    await _lock_dedup_key(
        db,
        department_code=body.department_code,
        project_name=body.project_name,
        owner_email=body.owner_email,
    )
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
    # 所有終態(cancelled / manual_pending / agent_done)加寄管理員通知(best-effort,互不連坐)
    await notify_admin_on_verdict(db, row, actor, ip)
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
    # 終態 cancelled 加寄管理員通知(best-effort,與申請人通知同層互不連坐)
    await notify_admin_on_verdict(db, row, actor, ip)
    return success_response(data=_detail(row), detail="success")


@router.post("/{uid}/revoke", summary="撤銷申請（本人/admin，須填理由，限 manual_pending）")
async def revoke_api_key_request(
    uid: UUID,
    body: RevokeRequest,
    actor: UserDep,
    db: DbDep,
    ip: ClientIpDep,
):
    repo = ApiKeyRequestRepository(db)
    row = await _get_or_404(repo, uid)
    is_owner = row.applicant_user_uid == actor.user_uid
    if not is_owner and not actor.is_admin:
        raise AppError("forbidden", code=403)
    # 已處理(agent_done / done)禁止撤銷;撤銷僅限 manual_pending。
    if row.status != "manual_pending":
        raise AppError("invalid_status", code=409)

    row.status = "revoked"
    # 撤銷本人單 → user;admin 撤銷他人單 → admin。
    row.revoke_source = "user" if is_owner else "admin"
    row.revoke_reason = body.reason
    row.processed_at = _now()
    await write_audit(
        db,
        actor_user_uid=actor.user_uid,
        actor_role=actor.role,
        action="revoke_api_key_request",
        target_type="api_key_request",
        target_uid=row.request_uid,
        ip=ip,
        detail=body.reason,
    )
    await db.commit()
    # 終態 revoked 加寄管理員通知(best-effort,與申請人通知同層互不連坐)
    await notify_admin_on_verdict(db, row, actor, ip)
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

    # 與 create 一致:序列化同 (部門+專案+負責人) 的併發開通,避免重複建立。
    await _lock_dedup_key(
        db,
        department_code=row.department_code,
        project_name=row.project_name,
        owner_email=row.owner_email,
    )
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
        # 原始例外可能含 SQL 約束 / 表名 / 他人 email,只進 log,不回前端。
        logger.exception(
            "人工開通失敗 request_uid=%s detail=%s",
            row.request_uid,
            (pr.error if pr is not None else None),
        )
        raise AppError("provision_failed", code=409) from exc

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
    # 終態 done 加寄管理員通知(best-effort,與申請人通知同層互不連坐)
    await notify_admin_on_verdict(db, row, actor, ip)
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
