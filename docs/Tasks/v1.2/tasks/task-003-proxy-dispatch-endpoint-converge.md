---
id: task-003
title: proxy 依 provider 分流(OR failover / Internal Phase1-2)+ /api/v1/model/chat 收斂與 models/keys CRUD 擴充
status: done
parallel: false
depends_on: [task-002]
affected_files:
  - backend/app/services/proxy.py
  - backend/app/services/sync.py
  - backend/app/api/v1/model_chat.py
  - backend/app/api/v1/models.py
  - backend/app/api/v1/openrouter_keys.py
  - backend/app/schemas/model.py
  - backend/app/schemas/openrouter_key.py
  - backend/app/repositories/model.py
estimated_hours: 4
---

## 目標
`run_chat` 依 `model_row.provider` 分流(OpenRouter:`acquire(timeout=0)` failover;Internal:Phase1 failover→Phase2 wait),`model_openrouter.py` 收斂為 `model_chat.py`(canonical `/model/chat` + deprecated alias),`POST /models`(限 internal)與條件性 PATCH 擴充,sync 只動 openrouter。

## Acceptance
- [x] `proxy.run_chat` internal 走 `_run_chat_internal`:Phase1 全 Key `acquire(timeout=0)` failover、Phase2 全撞牆隨機選一把 `acquire(timeout=RATE_WAIT_TIMEOUT)`;超時→`AppError("internal_busy",429,data={retry_after_seconds})`、5xx→`internal_unavailable` 502、無 active key→`provider_misconfigured` 500;internal usage_log `openrouter_key_uid=None`、`cost_usd=0`
- [x] OpenRouter 路徑迴圈 `acquire(timeout=0)` 撞牆換下一把,全撞牆→`rate_limited` 429
- [x] `api/v1/model_chat.py` 提供 `POST /api/v1/model/chat`(canonical)與 `POST /api/v1/model/openrouter/chat`(`deprecated=True` alias forward 同 handler);response 走 `success_response()`/`failure_response()`
- [x] `POST /api/v1/models` 僅 admin、body `provider` 非 `internal`→`provider_not_allowed` 400;`PATCH /models/{uid}` 依 provider 動態驗證(internal 開放 name/description/context_length/tier_key/is_active;openrouter 僅 tier_key/is_active);`openrouter_keys` PATCH 接受 rpm_limit/min_request_interval_ms
- [x] `services/sync.py` upsert 加 `WHERE provider='openrouter'`,`provider='internal'` 列 `last_synced_at` 不變;`repositories/model.py` `find_by_openrouter_model_id`→`find_by_key`

## 必讀檔(Just-in-time)
- [`03-backend/01-routing.md`](../../../Design-Base/03-backend/01-routing.md) · [`03-backend/05-exceptions-and-logging.md`](../../../Design-Base/03-backend/05-exceptions-and-logging.md) · [`03-backend/03-async-and-tx.md`](../../../Design-Base/03-backend/03-async-and-tx.md) · [`03-backend/92-project-permission.md`](../../../Design-Base/03-backend/92-project-permission.md) · [`90-third-party-service/50-openrouter.md`](../../../Design-Base/90-third-party-service/50-openrouter.md) · [`00-overview/04-api-docs.md`](../../../Design-Base/00-overview/04-api-docs.md)
