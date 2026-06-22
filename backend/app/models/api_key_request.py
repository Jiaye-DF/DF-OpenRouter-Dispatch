from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
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
    # 申請狀態(v1.9.1 五種):
    #   manual_pending 待人工處理 / agent_done Agent 已處理 / done 已處理 /
    #   revoked 已撤銷 / cancelled 已取消
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="manual_pending"
    )
    # 取消資訊
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_source: Mapped[str | None] = mapped_column(String(8), nullable=True)
    # 人工處理 admin
    handled_by_user_uid: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    # AI 欄位驗證決策 {confidence, reason}
    agent_decision: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # AI / 開通失敗原因
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 開通結果
    created_project_uid: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    created_user_uid: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    created_sdk_key_uid: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    matched_department_uid: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    # 一次性憑證 {sdk_key, user_token, project_code},領取後清空
    provisioned_secrets: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # 進入終態時間
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # 開通完成 Email 通知(v1.9.2):寄送成功時間 / 失敗原因(不含憑證)
    notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notify_error: Mapped[str | None] = mapped_column(Text, nullable=True)
