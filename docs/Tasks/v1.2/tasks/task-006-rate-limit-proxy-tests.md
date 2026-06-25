---
id: task-006
title: 測試 — KeyRateLimiter 單元 + proxy 分流/failover/internal 整合 + Swagger deprecated 驗證
status: done
parallel: false
depends_on: [task-003, task-004]
affected_files:
  - backend/tests/services/test_rate_limit.py
  - backend/tests/api/test_model_chat.py
  - backend/tests/api/test_internal_keys.py
estimated_hours: 4
---

## 目標
覆蓋 v1.2 關鍵情境:`KeyRateLimiter` 視窗/間隔/超時/滑動單元測試,proxy OR failover 與 internal Phase1-2 整合測試,internal-keys CRUD 不外洩明文,Swagger 兩條 chat path 可見(舊標 deprecated)。

## Acceptance
- [x] `test_rate_limit.py`:連 N+1 次(N=rpm_limit)第 N+1 需等視窗釋出、`min_request_interval_ms=200` 連兩次間隔≥200ms、等待>`wait_timeout`→`RateLimitExceeded` 帶正確 `retry_after_seconds`、60s 視窗舊時間戳被清除
- [x] proxy 整合:OR `rpm_limit=2` 連 3 次第 3 次自動切下一把、全 Key 撞牆→429 `rate_limited`;internal RPM=2 連 3 次第 3 次延遲成功、等待>`RATE_WAIT_TIMEOUT`→429 `internal_busy`+`retry_after_seconds`、server 5xx→502 `internal_unavailable`、無 active internal_keys 但有 internal model→500 `provider_misconfigured`
- [x] OpenRouter 模型回歸(v1.1 行為不變)、sync 不動 `provider='internal'` 列(`last_synced_at` 不變)、`POST /models` provider=openrouter→400 `provider_not_allowed`
- [x] internal-keys CRUD response 不含明文 `api_key`;Swagger `/api/docs` 兩條 chat path 皆可見且 `/model/openrouter/chat` 標 deprecated

## 必讀檔(Just-in-time)
- [`03-backend/07-testing.md`](../../../Design-Base/03-backend/07-testing.md) · [`03-backend/05-exceptions-and-logging.md`](../../../Design-Base/03-backend/05-exceptions-and-logging.md) · [`90-third-party-service/02-rate-and-cost.md`](../../../Design-Base/90-third-party-service/02-rate-and-cost.md) · [`90-third-party-service/50-openrouter.md`](../../../Design-Base/90-third-party-service/50-openrouter.md) · [`00-overview/04-api-docs.md`](../../../Design-Base/00-overview/04-api-docs.md)
