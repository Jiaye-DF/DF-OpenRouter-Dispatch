-- V1: 認證相關 Table（users、refresh_tokens）+ 共用 trigger。
-- Seed 初始 admin 由應用程式層 lifespan hook 完成（需 argon2id hash，由 Python 端負責）。

CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- users（V2 會 ALTER 補 department_uid、employee_id、email）
CREATE TABLE users (
    pid                    BIGSERIAL PRIMARY KEY,
    user_uid               UUID         NOT NULL UNIQUE,
    account                VARCHAR(64)  NOT NULL,
    username               VARCHAR(128) NOT NULL,
    password_hash          VARCHAR(255) NOT NULL,
    role                   VARCHAR(16)  NOT NULL,
    failed_login_count     INT          NOT NULL DEFAULT 0,
    locked_until           TIMESTAMPTZ,
    password_changed_at    TIMESTAMPTZ,
    is_active              BOOLEAN      NOT NULL DEFAULT TRUE,
    is_deleted             BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at             TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at             TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX uq_users_account ON users (lower(account)) WHERE is_deleted = FALSE;

CREATE TRIGGER trg_users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- refresh_tokens
CREATE TABLE refresh_tokens (
    pid                    BIGSERIAL PRIMARY KEY,
    refresh_token_uid      UUID         NOT NULL UNIQUE,
    user_uid               UUID         NOT NULL,
    family_uid             UUID         NOT NULL,
    token_hash             VARCHAR(255) NOT NULL,
    issued_at              TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    expires_at             TIMESTAMPTZ  NOT NULL,
    revoked_at             TIMESTAMPTZ,
    replaced_by_uid        UUID,
    user_agent             VARCHAR(512),
    ip                     INET,
    is_active              BOOLEAN      NOT NULL DEFAULT TRUE,
    is_deleted             BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at             TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at             TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_refresh_tokens_user_uid ON refresh_tokens (user_uid) WHERE is_deleted = FALSE;
CREATE INDEX idx_refresh_tokens_family   ON refresh_tokens (family_uid) WHERE is_deleted = FALSE;

CREATE TRIGGER trg_refresh_tokens_updated_at
BEFORE UPDATE ON refresh_tokens
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
