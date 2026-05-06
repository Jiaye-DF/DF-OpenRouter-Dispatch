-- V11: usage_logs 加 model_uid FK(對齊 docs/Tasks/v1.1/propose-v1.1.0.md § 5.5)。
-- 寫入時同寫 model(字串)與 model_uid(若該模型存在於 models 表);既有歷史不回填,允許 NULL。

ALTER TABLE usage_logs
    ADD COLUMN model_uid UUID REFERENCES models(model_uid);

CREATE INDEX idx_usage_logs_model_uid_time
    ON usage_logs (model_uid, created_at DESC);
