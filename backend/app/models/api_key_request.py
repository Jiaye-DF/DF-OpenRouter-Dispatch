from uuid import UUID

from sqlalchemy import BigInteger, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ApiKeyRequest(Base, TimestampMixin):
    __tablename__ = "api_key_requests"

    pid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    request_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), unique=True, nullable=False
    )
    # 申請人(後端由 Actor 注入,前端不可指定)
    applicant_user_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    department_name: Mapped[str] = mapped_column(String(128), nullable=False)
    department_code: Mapped[str] = mapped_column(String(32), nullable=False)
    project_name: Mapped[str] = mapped_column(String(128), nullable=False)
    # 須為 GitHub / Replit 連結(驗證於 schema)
    project_url: Mapped[str] = mapped_column(String(512), nullable=False)
    owner_name: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_email: Mapped[str] = mapped_column(String(255), nullable=False)
    # 申請狀態,本版恆為 "pending"(審核流轉留待 v1.9.1)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="pending"
    )
