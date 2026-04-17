-- V6: 用量紀錄。

CREATE TABLE usage_logs (
    pid                       BIGSERIAL PRIMARY KEY,
    usage_log_uid             UUID          NOT NULL UNIQUE,
    user_uid                  UUID          REFERENCES users(user_uid),
    department_uid            UUID          REFERENCES departments(department_uid),
    openrouter_key_uid        UUID          REFERENCES openrouter_keys(openrouter_key_uid),
    model                     VARCHAR(128)  NOT NULL,
    prompt_tokens             INT           NOT NULL DEFAULT 0,
    completion_tokens         INT           NOT NULL DEFAULT 0,
    total_tokens              INT           NOT NULL DEFAULT 0,
    cost_usd                  NUMERIC(12,6) NOT NULL DEFAULT 0,
    latency_ms                INT           NOT NULL DEFAULT 0,
    status                    VARCHAR(16)   NOT NULL,
    error_code                VARCHAR(64),
    request_content           JSONB,
    response_summary          JSONB,
    openrouter_generation_id  VARCHAR(64),
    is_active                 BOOLEAN       NOT NULL DEFAULT TRUE,
    is_deleted                BOOLEAN       NOT NULL DEFAULT FALSE,
    created_at                TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at                TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_usage_logs_dept_time  ON usage_logs (department_uid, created_at DESC);
CREATE INDEX idx_usage_logs_user_time  ON usage_logs (user_uid, created_at DESC);
CREATE INDEX idx_usage_logs_model_time ON usage_logs (model, created_at DESC);

CREATE TRIGGER trg_usage_logs_updated_at
BEFORE UPDATE ON usage_logs
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
