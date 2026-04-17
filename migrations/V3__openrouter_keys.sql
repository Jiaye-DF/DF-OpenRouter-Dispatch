-- V3: OpenRouter Key（AES-256-GCM 加密存 DB）。

CREATE TABLE openrouter_keys (
    pid                  BIGSERIAL PRIMARY KEY,
    openrouter_key_uid   UUID         NOT NULL UNIQUE,
    department_uid       UUID         NOT NULL REFERENCES departments(department_uid),
    name                 VARCHAR(128) NOT NULL,
    key_ciphertext       BYTEA        NOT NULL,
    key_prefix           VARCHAR(16)  NOT NULL,
    key_last4            VARCHAR(8)   NOT NULL,
    is_active            BOOLEAN      NOT NULL DEFAULT TRUE,
    is_deleted           BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_openrouter_keys_dept
    ON openrouter_keys (department_uid)
    WHERE is_deleted = FALSE AND is_active = TRUE;

CREATE TRIGGER trg_openrouter_keys_updated_at
BEFORE UPDATE ON openrouter_keys
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
