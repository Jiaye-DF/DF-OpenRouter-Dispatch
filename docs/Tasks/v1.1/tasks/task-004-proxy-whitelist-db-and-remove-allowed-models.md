---
id: task-004
title: Proxy 白名單改 DB 驅動 + usage_log 寫 model_uid + 移除 ALLOWED_MODELS
status: done
parallel: false
depends_on: [task-001, task-003]
affected_files:
  - backend/app/services/proxy.py
  - backend/app/core/config.py
  - .env.example
estimated_hours: 3
---

## 目標
`_check_model_whitelist` 改查 `models WHERE openrouter_model_id=? AND is_active=TRUE AND is_deleted=FALSE`,不通過回 403 `model_forbidden`,通過回 `Model` instance 供 `schedule_usage_log` 取 `model_uid`(字串 `model` 與 `model_uid` 雙寫);`ALLOWED_MODELS` 從 `config.py`(含 `allowed_models_list` property)與 `.env.example` 完全移除。

## Acceptance
- [x] `uv run pytest backend/tests/test_proxy_whitelist_db.py -q` 通過:不存在 / `is_active=FALSE` / 軟刪除 三情境均回 403 `model_forbidden`
- [x] `grep -rn "ALLOWED_MODELS\|allowed_models_list" backend/app .env.example` 無命中(完全移除)
- [x] `schedule_usage_log` 簽名含 `model_uid: UUID | None`,放行請求寫入的 usage_log 同時有 `model` 字串與 `model_uid`
- [x] 白名單拒絕時仍寫一筆 `status=error error_code=model_forbidden` 的 usage_log

## 必讀檔(Just-in-time)
- [`03-backend/01-routing.md`](../../../Design-Base/03-backend/01-routing.md) · [`03-backend/04-config.md`](../../../Design-Base/03-backend/04-config.md) · [`03-backend/05-exceptions-and-logging.md`](../../../Design-Base/03-backend/05-exceptions-and-logging.md) · [`03-backend/07-testing.md`](../../../Design-Base/03-backend/07-testing.md)
- [`00-overview/02-secrets.md`](../../../Design-Base/00-overview/02-secrets.md) · [`00-overview/03-env-layers.md`](../../../Design-Base/00-overview/03-env-layers.md) · [`00-overview/91-project-naming-env.md`](../../../Design-Base/00-overview/91-project-naming-env.md)
- [`90-third-party-service/50-openrouter.md`](../../../Design-Base/90-third-party-service/50-openrouter.md) · [`03-backend/92-project-permission.md`](../../../Design-Base/03-backend/92-project-permission.md)
