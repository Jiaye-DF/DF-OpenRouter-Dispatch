-- V4: SDK API Key（argon2id hash 比對）。

CREATE TABLE sdk_api_keys (
    pid                  BIGSERIAL PRIMARY KEY,
    sdk_api_key_uid      UUID         NOT NULL UNIQUE,
    department_uid       UUID         NOT NULL REFERENCES departments(department_uid),
    name                 VARCHAR(128) NOT NULL,
    key_hash             VARCHAR(255) NOT NULL,
    key_prefix           VARCHAR(32)  NOT NULL,
    is_active            BOOLEAN      NOT NULL DEFAULT TRUE,
    is_deleted           BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_sdk_api_keys_dept
    ON sdk_api_keys (department_uid)
    WHERE is_deleted = FALSE;
CREATE INDEX idx_sdk_api_keys_prefix
    ON sdk_api_keys (key_prefix)
    WHERE is_deleted = FALSE;

CREATE TRIGGER trg_sdk_api_keys_updated_at
BEFORE UPDATE ON sdk_api_keys
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
