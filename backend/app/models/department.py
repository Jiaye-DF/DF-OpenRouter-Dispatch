from uuid import UUID

from sqlalchemy import BigInteger, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Department(Base, TimestampMixin):
    __tablename__ = "departments"

    pid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    department_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), unique=True, nullable=False
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)  # 成本中心代碼
    org_code: Mapped[str | None] = mapped_column(String(32), nullable=True)  # 組織代碼
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
