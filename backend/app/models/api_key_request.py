from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import BigInteger, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ApiKeyRequest(Base, TimestampMixin):
    __tablename__ = "api_key_requests"

    __table_args__ = (
        sa.Index(
            "idx_api_key_requests_applicant",
            "applicant_user_uid",
            postgresql_where=sa.text("(is_deleted = false)"),
        ),
        sa.Index(
            "idx_api_key_requests_created_at",
            "created_at",
            postgresql_where=sa.text("(is_deleted = false)"),
        ),
        {"comment": "金鑰申請單"},
    )

    pid: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        comment="內部自增主鍵,禁對外暴露 | internal auto-increment PK",
    )
    request_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        unique=True,
        nullable=False,
        comment="對外 UUID 識別(UUIDv7) | external UID",
    )
    # 申請人(後端由 Actor 注入,前端不可指定)
    applicant_user_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        comment="申請人(軟引用 users.user_uid,後端由 Actor 注入) | applicant user",
    )
    department_name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="申請填寫的部門名稱 | requested department name",
    )
    department_code: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="申請填寫的部門代碼 | requested department code",
    )
    project_name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="申請的專案名稱 | requested project name",
    )
    # 須為 GitHub / Replit 連結(驗證於 schema)
    project_url: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        comment="專案連結(須為 GitHub / Replit,驗證於 schema) | project URL",
    )
    owner_name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="專案負責人姓名(PII) | owner name (PII)",
    )
    owner_email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="專案負責人 Email(PII) | owner email (PII)",
    )
    # 申請狀態(v1.9.1 五種):
    #   manual_pending 待人工處理 / agent_done Agent 已處理 / done 已處理 /
    #   revoked 已撤銷 / cancelled 已取消
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default="manual_pending",
        comment="申請狀態:manual_pending/agent_done/done/revoked/cancelled | request status",
    )
    # 取消資訊
    cancel_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="取消原因 | cancel reason",
    )
    cancel_source: Mapped[str | None] = mapped_column(
        String(8),
        nullable=True,
        comment="取消來源(user / admin 等) | cancel source",
    )
    # 撤銷資訊(本人 / admin 皆須填理由)
    revoke_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="撤銷原因 | revoke reason",
    )
    revoke_source: Mapped[str | None] = mapped_column(
        String(8),
        nullable=True,
        comment="撤銷來源(user / admin) | revoke source",
    )
    # 人工處理 admin
    handled_by_user_uid: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="人工處理的 admin(軟引用 users.user_uid) | handled-by admin",
    )
    # AI 欄位驗證決策 {confidence, reason}
    agent_decision: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="AI 欄位驗證決策 {confidence, reason} | AI field-validation decision",
    )
    # AI / 開通失敗原因
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="AI / 開通失敗原因 | AI or provisioning error message",
    )
    # 開通結果
    created_project_uid: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="開通建立的專案(軟引用 projects.project_uid) | created project",
    )
    created_user_uid: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="開通建立的使用者(軟引用 users.user_uid) | created user",
    )
    created_sdk_key_uid: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="開通建立的 SDK 金鑰(軟引用 sdk_api_keys.sdk_api_key_uid) | created SDK key",
    )
    matched_department_uid: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="比對到的既有部門(軟引用 departments.department_uid) | matched department",
    )
    # 一次性憑證 {sdk_key, user_token, project_code},領取後清空
    provisioned_secrets: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="一次性開通憑證 {sdk_key, user_token, project_code},領取後清空(機密) | one-time provisioned secrets (cleared after pickup)",
    )
    # 進入終態時間
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="進入終態時間(UTC+8) | processed at",
    )
    # 開通完成 Email 通知(v1.9.2):寄送成功時間 / 失敗原因(不含憑證)
    notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="開通完成 Email 通知寄送成功時間(UTC+8) | notified at",
    )
    notify_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="通知信寄送失敗原因(不含憑證) | notify error message",
    )
