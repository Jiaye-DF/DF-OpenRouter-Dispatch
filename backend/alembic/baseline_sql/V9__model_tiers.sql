-- V9: 模型分級主檔 + seed 4 級(對齊 docs/Tasks/v1.1/propose-v1.1.0.md § 5.3)。
-- key 一旦建立不可改名(避免 models.tier_key 失聯);label / color / sort_order / 區間皆可編。
-- auto_match_*_price_per_mtok 單位為 USD per token(propose 表以 USD/M tok 顯示,seed 時除以 1_000_000)。

CREATE TABLE model_tiers (
    pid                            BIGSERIAL    PRIMARY KEY,
    tier_uid                       UUID         NOT NULL UNIQUE,

    key                            VARCHAR(32)  NOT NULL UNIQUE,
    label_zh                       VARCHAR(64)  NOT NULL,
    label_en                       VARCHAR(64),
    color                          VARCHAR(16),
    sort_order                     INT          NOT NULL DEFAULT 0,

    -- 同步時自動匹配的價格區間(USD per token);NULL = 不參與自動匹配
    auto_match_min_price_per_mtok  NUMERIC(20, 12),
    auto_match_max_price_per_mtok  NUMERIC(20, 12),

    is_active                      BOOLEAN      NOT NULL DEFAULT TRUE,
    is_deleted                     BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at                     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at                     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TRIGGER trg_model_tiers_updated_at
BEFORE UPDATE ON model_tiers
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- 預設 4 級 seed;單位 USD/token(propose § 5.3 區間以 USD/M tok 表示,此處除以 1_000_000)。
-- free      [0, 0]        → min=0,                max=0
-- cheap     (0, 1) USD/M  → min=0(開區間,service 以 > min 判斷或允許 = min 含於 free),max=0.000001
-- standard  [1, 5) USD/M  → min=0.000001,         max=0.000005
-- expensive [5, ∞)        → min=0.000005,         max=NULL
INSERT INTO model_tiers (tier_uid, key, label_zh, label_en, color, sort_order, auto_match_min_price_per_mtok, auto_match_max_price_per_mtok)
VALUES
    (gen_random_uuid(), 'free',      '免費', 'Free',      'gray',   10, 0,           0),
    (gen_random_uuid(), 'cheap',     '經濟', 'Cheap',     'green',  20, 0,           0.000001),
    (gen_random_uuid(), 'standard',  '標準', 'Standard',  'blue',   30, 0.000001,    0.000005),
    (gen_random_uuid(), 'expensive', '高階', 'Expensive', 'orange', 40, 0.000005,    NULL);
