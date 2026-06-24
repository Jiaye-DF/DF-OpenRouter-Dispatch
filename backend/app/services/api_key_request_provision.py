from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils import uuid7

from app.core.audit import write_audit
from app.core.security import hash_password
from app.core.snowflake import generate_id_str
from app.models.api_key_request import ApiKeyRequest
from app.models.project import Project
from app.models.user import User
from app.repositories.project import ProjectRepository
from app.repositories.sdk_api_key import SdkApiKeyRepository
from app.repositories.user import UserRepository
from app.services.sdk_key import create_sdk_key, reveal_sdk_key
from app.services.user_token import get_or_create_token

if TYPE_CHECKING:
    from app.services.api_key_request_router import RouteResult

logger = logging.getLogger(__name__)


@dataclass
class ProvisionResult:
    ok: bool
    error: str | None = None
    matched_department_uid: UUID | None = None
    created_project_uid: UUID | None = None
    created_user_uid: UUID | None = None
    created_sdk_key_uid: UUID | None = None
    provisioned_secrets: dict | None = None


async def provision(
    db: AsyncSession,
    req: ApiKeyRequest,
    route: RouteResult,
    *,
    actor,
) -> ProvisionResult:
    """確定性自動開通:依序建立 專案 → 使用者 → SDK Key → User Token。

    全程於傳入的 db session 內 flush(不 commit,commit 由端點負責);
    任一步失敗 → logger.exception 後回 ProvisionResult(ok=False),由端點以 savepoint rollback。
    """
    try:
        dept = route.matched_department
        # Department 模型僅有 department_uid(無 .uid);FK 欄位與既有 service 皆用此 UUID 值
        dept_uid = dept.department_uid
        matched_department_uid = dept_uid

        # 2) 專案:一律新建
        project = Project(
            project_uid=UUID(str(uuid7())),
            department_uid=dept_uid,
            code=generate_id_str(),
            name=req.project_name,
            description=None,
        )
        ProjectRepository(db).add(project)
        await db.flush()
        await write_audit(
            db,
            actor_user_uid=actor.user_uid,
            actor_role=actor.role,
            action="create_project",
            target_type="project",
            target_uid=project.project_uid,
        )

        # 3) 使用者:email 命中沿用,否則新建
        if route.matched_user is not None:
            user = route.matched_user
        else:
            user = User(
                user_uid=UUID(str(uuid7())),
                account=f"usr_{secrets.token_hex(12)}",
                username=req.owner_name,
                password_hash=hash_password(secrets.token_urlsafe(32)),
                role="user",
                department_uid=dept_uid,
                email=req.owner_email,
            )
            UserRepository(db).add(user)
            await db.flush()
            await write_audit(
                db,
                actor_user_uid=actor.user_uid,
                actor_role=actor.role,
                action="create_user",
                target_type="user",
                target_uid=user.user_uid,
            )

        # 4) SDK Key:部門有可用 Key 沿用,否則新建
        sdk_repo = SdkApiKeyRepository(db)
        sdk = await sdk_repo.get_active_by_department(dept_uid)
        if sdk is not None:
            plaintext = reveal_sdk_key(sdk)
        else:
            sdk, plaintext = await create_sdk_key(
                db,
                department_uid=dept_uid,
                name=f"{req.project_name} 申請金鑰",
            )
            await write_audit(
                db,
                actor_user_uid=actor.user_uid,
                actor_role=actor.role,
                action="create_sdk_key",
                target_type="sdk_api_key",
                target_uid=sdk.sdk_api_key_uid,
            )

        # 5) User Token:一人一把,固定不變;已存在則沿用同一把,不撤銷不重發
        #    (使同一使用者跨多專案/重複申請拿到的都是同一把,避免舊 token 被作廢)
        token, _issued_at = await get_or_create_token(db, user_uid=user.user_uid)

        # 6) 一次性憑證
        provisioned_secrets = {
            "sdk_key": plaintext,
            "user_token": token,
            "project_code": project.code,
        }

        return ProvisionResult(
            ok=True,
            matched_department_uid=matched_department_uid,
            created_project_uid=project.project_uid,
            created_user_uid=user.user_uid,
            created_sdk_key_uid=sdk.sdk_api_key_uid,
            provisioned_secrets=provisioned_secrets,
        )
    except Exception as exc:  # noqa: BLE001 - 開通任一步失敗皆降級人工
        logger.exception("自動開通失敗")
        return ProvisionResult(ok=False, error=str(exc)[:300])
