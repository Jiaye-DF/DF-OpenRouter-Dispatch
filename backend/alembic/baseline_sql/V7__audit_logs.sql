-- V7: 管理端稽核 Log（對齊 80-permission.md § 9）。
-- Tasks-v1 未明列 Migration，但規範要求所有 admin 異動寫稽核，故以補充 Migration 提供。

CREATE TABLE audit_logs (
    pid                 BIGSERIAL PRIMARY KEY,
    audit_log_uid       UUID         NOT NULL UNIQUE,
    actor_user_uid      UUID         NOT NULL,
    actor_role          VARCHAR(16)  NOT NULL,
    action              VARCHAR(64)  NOT NULL,
    target_type         VARCHAR(64)  NOT NULL,
    target_uid          UUID,
    result              VARCHAR(16)  NOT NULL DEFAULT 'success',
    detail              TEXT,
    ip                  INET,
    extra               JSONB,
    is_active           BOOLEAN      NOT NULL DEFAULT TRUE,
    is_deleted          BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_audit_logs_actor_time  ON audit_logs (actor_user_uid, created_at DESC);
CREATE INDEX idx_audit_logs_target_time ON audit_logs (target_type, target_uid, created_at DESC);

CREATE TRIGGER trg_audit_logs_updated_at
BEFORE UPDATE ON audit_logs
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
