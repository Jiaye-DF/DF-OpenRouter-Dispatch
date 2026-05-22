"""啟動 Seed：只確保初始 admin 存在；其他資料一律由 admin 在後台自行建立。

- **不**自動建立 SYSTEM 部門
- **不**自動匯入 DEFAULT_OPENROUTER_KEY
- 不覆蓋已存在的 admin（密碼、department_uid 等欄位不動）
"""

import asyncio
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, text
from uuid_utils import uuid7

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.core.security import hash_password
from app.models.user import User

logger = get_logger(__name__)

_DB_READY_MAX_RETRIES = 30
_DB_READY_SLEEP = 2.0


async def _wait_db_ready() -> None:
    for i in range(_DB_READY_MAX_RETRIES):
        try:
            async with SessionLocal() as s:
                await s.execute(text("SELECT 1 FROM users LIMIT 1"))
            return
        except Exception as exc:  # noqa: BLE001
            logger.info("DB 尚未就緒（第 %d 次）: %s", i + 1, exc)
            await asyncio.sleep(_DB_READY_SLEEP)
    raise RuntimeError("DB/Migration 遲遲未就緒；放棄 seed")


async def run_seed() -> None:
    await _wait_db_ready()
    settings = get_settings()
    async with SessionLocal() as session:
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
        admin_email = settings.INITIAL_ADMIN_EMAIL.strip() or None
        if admin is None:
            admin = User(
                user_uid=UUID(str(uuid7())),
                account=settings.INITIAL_ADMIN_ACCOUNT,
                username=settings.INITIAL_ADMIN_USERNAME,
                password_hash=hash_password(settings.INITIAL_ADMIN_PASSWORD),
                role="admin",
                department_uid=None,
                email=admin_email,
                password_changed_at=datetime.now(tz=UTC),
            )
            session.add(admin)
            await session.flush()
            logger.info("已建立初始 admin：%s", admin.account)
        elif admin_email and not admin.email:
            # 既有 admin 尚無 Email:回填以供 DF-SSO 以 Email 對應登入(僅補空,不覆寫)。
            admin.email = admin_email
            logger.info("已回填初始 admin Email：%s", admin.account)
        await session.commit()
