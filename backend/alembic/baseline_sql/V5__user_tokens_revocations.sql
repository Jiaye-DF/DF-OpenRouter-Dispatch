-- V5: User Token 撤銷記錄（驗證代理呼叫時比對）。

CREATE TABLE user_tokens_revocations (
    pid                              BIGSERIAL PRIMARY KEY,
    user_tokens_revocation_uid       UUID         NOT NULL UNIQUE,
    user_uid                         UUID         NOT NULL REFERENCES users(user_uid),
    revoked_issued_at                TIMESTAMPTZ  NOT NULL,
    revoked_at                       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    reason                           VARCHAR(255),
    is_active                        BOOLEAN      NOT NULL DEFAULT TRUE,
    is_deleted                       BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at                       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at                       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_user_tokens_revocations_user
    ON user_tokens_revocations (user_uid)
    WHERE is_deleted = FALSE;

CREATE TRIGGER trg_user_tokens_revocations_updated_at
BEFORE UPDATE ON user_tokens_revocations
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
