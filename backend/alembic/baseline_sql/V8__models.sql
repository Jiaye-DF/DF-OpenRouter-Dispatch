-- V8: 模型主檔(對齊 docs/Tasks/v1.1/propose-v1.1.0.md § 5.1)。
-- OpenRouter 為事實來源,平台僅做選擇與註記;單一 is_active 同時表達「OR 仍提供 + 平台允許使用」。

CREATE TABLE models (
    pid                            BIGSERIAL    PRIMARY KEY,
    model_uid                      UUID         NOT NULL UNIQUE,

    -- OpenRouter 識別(僅 sync 寫入,admin 唯讀)
    openrouter_model_id            VARCHAR(128) NOT NULL UNIQUE,
    name                           VARCHAR(255) NOT NULL,
    description                    TEXT,

    -- 規格(僅 sync 寫入)
    context_length                 INT,
    max_completion_tokens          INT,
    modality                       VARCHAR(64),
    tokenizer                      VARCHAR(64),

    -- 計費(USD per token;僅 sync 寫入)
    price_prompt_per_token         NUMERIC(20, 12),
    price_completion_per_token     NUMERIC(20, 12),
    price_image_per_image          NUMERIC(20, 12),
    price_request_flat             NUMERIC(20, 12),

    -- 平台控管(可由 admin 編輯)
    is_moderated                   BOOLEAN      NOT NULL DEFAULT FALSE,
    tier_key                       VARCHAR(32),  -- 對應 model_tiers.key;NULL = 未分級;不加硬 FK,由 service 保證引用完整性

    -- 同步追蹤
    openrouter_created_at          TIMESTAMPTZ,
    last_synced_at                 TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    -- 必備欄位
    is_active                      BOOLEAN      NOT NULL DEFAULT TRUE,
    is_deleted                     BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at                     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at                     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_models_active   ON models (is_active)  WHERE is_deleted = FALSE;
CREATE INDEX idx_models_tier_key ON models (tier_key)   WHERE is_deleted = FALSE;

CREATE TRIGGER trg_models_updated_at
BEFORE UPDATE ON models
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
