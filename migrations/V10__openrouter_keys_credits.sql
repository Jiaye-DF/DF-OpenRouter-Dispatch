-- V10: openrouter_keys 加 4 欄追蹤 OpenRouter 帳號餘額(對齊 docs/Tasks/v1.1/propose-v1.1.0.md § 5.4)。
-- 對每把 active OR Key 呼叫 GET /auth/key,best-effort 回填;個別失敗不整批 rollback。

ALTER TABLE openrouter_keys
    ADD COLUMN credits_used_usd       NUMERIC(12, 6),
    ADD COLUMN credits_limit_usd      NUMERIC(12, 6),  -- NULL = 無上限
    ADD COLUMN credits_is_free_tier   BOOLEAN,
    ADD COLUMN credits_synced_at      TIMESTAMPTZ;
