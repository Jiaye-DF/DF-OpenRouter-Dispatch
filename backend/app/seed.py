import asyncio
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, text
from uuid_utils import uuid7

from app.core.config import get_settings
from app.core.crypto import encrypt_bytes
from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.core.security import hash_password
from app.models.department import Department
from app.models.openrouter_key import OpenRouterKey
from app.models.user import User

logger = get_logger(__name__)

_SYSTEM_DEPT_CODE = "SYSTEM"
_DB_READY_MAX_RETRIES = 30
_DB_READY_SLEEP = 2.0


async def _wait_db_ready() -> None:
    """Flyway 可能仍在跑 migration，等 users 表出現後再 seed。"""
    for i in range(_DB_READY_MAX_RETRIES):
        try:
            async with SessionLocal() as s:
                await s.execute(text("SELECT 1 FROM users LIMIT 1"))
            return
        except Exception as exc:  # noqa: BLE001
            logger.info("DB 尚未就緒（第 %d 次）: %s", i + 1, exc)
            await asyncio.sleep(_DB_READY_SLEEP)
    raise RuntimeError("DB/Flyway 遲遲未就緒；放棄 seed")


async def run_seed() -> None:
    await _wait_db_ready()
    settings = get_settings()
    async with SessionLocal() as session:
        # --- 1. SYSTEM 部門 ---
        dept = (
            await session.execute(
                select(Department)
                .where(Department.code == _SYSTEM_DEPT_CODE, Department.is_deleted.is_(False))
                .limit(1)
            )
        ).scalar_one_or_none()
        if dept is None:
            dept = Department(
                department_uid=UUID(str(uuid7())),
                code=_SYSTEM_DEPT_CODE,
                name="系統管理部",
                description="平台內建部門；初始 admin 掛於此。",
            )
            session.add(dept)
            await session.flush()
            logger.info("已建立 SYSTEM 部門：%s", dept.department_uid)

        # --- 2. 初始 admin ---
        admin = (
            await session.execute(
                select(User)
                .where(
                    User.account == settings.INITIAL_ADMIN_ACCOUNT,
                    User.is_deleted.is_(False),
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if admin is None:
            admin = User(
                user_uid=UUID(str(uuid7())),
                account=settings.INITIAL_ADMIN_ACCOUNT,
                username=settings.INITIAL_ADMIN_USERNAME,
                password_hash=hash_password(settings.INITIAL_ADMIN_PASSWORD),
                role="admin",
                department_uid=dept.department_uid,
                password_changed_at=datetime.now(tz=UTC),
            )
            session.add(admin)
            await session.flush()
            logger.info("已建立初始 admin：%s", admin.account)
        elif admin.department_uid is None:
            admin.department_uid = dept.department_uid
            await session.flush()

        # --- 3. 選配：預設 OpenRouter Key ---
        if settings.DEFAULT_OPENROUTER_KEY.strip():
            existing = (
                await session.execute(
                    select(OpenRouterKey)
                    .where(
                        OpenRouterKey.department_uid == dept.department_uid,
                        OpenRouterKey.is_deleted.is_(False),
                    )
                    .limit(1)
                )
            ).scalar_one_or_none()
            if existing is None:
                raw = settings.DEFAULT_OPENROUTER_KEY.strip()
                try:
                    ciphertext = encrypt_bytes(raw.encode("utf-8"))
                except Exception:
                    logger.exception("DEFAULT_OPENROUTER_KEY 加密失敗；跳過")
                else:
                    row = OpenRouterKey(
                        openrouter_key_uid=UUID(str(uuid7())),
                        department_uid=dept.department_uid,
                        name="預設 Key（來自 .env）",
                        key_ciphertext=ciphertext,
                        key_prefix=raw[:4],
                        key_last4=raw[-4:],
                    )
                    session.add(row)
                    await session.flush()
                    logger.info("已 Seed 預設 OpenRouter Key 至 SYSTEM 部門")

        await session.commit()
