---
id: task-002
title: KeyRateLimiter 速率限制器 + Internal OpenAI-compatible client + client factory
status: done
parallel: true
depends_on: [task-001]
affected_files:
  - backend/app/services/rate_limit.py
  - backend/app/clients/internal/__init__.py
  - backend/app/clients/internal/client.py
  - backend/app/clients/factory.py
  - backend/app/core/config.py
  - .env.example
estimated_hours: 4
---

## 目標
實作 in-memory `KeyRateLimiter`(RPM 視窗 + 最小間隔疊加,asyncio.Lock)、OpenAI-compatible internal client(base_url/api_key 建構子注入、5xx/連線失敗包成 `InternalError`),以及依 provider 回 client 的 factory;收斂 `INTERNAL_LLM_*` 為 2 個 env。

## Acceptance
- [x] `services/rate_limit.py` 提供 `RateLimitExceeded(retry_after_seconds)`、`KeyRateLimiter.acquire(wait_timeout)`(清舊時間戳→`wait=max(min_interval, rpm_window)`→超 timeout 拋例外→鎖內預訂 slot→釋鎖後 sleep)、module-level `get(key, rpm_limit, min_interval_ms)` registry
- [x] `clients/internal/client.py` 提供 `chat_completion()`,base_url/api_key 由建構子注入,`httpx.HTTPError`/5xx 包成 `InternalError`;`factory.py` 提供 `internal_httpx()` 共用 httpx 單例與 `get_chat_client(provider)`
- [x] `core/config.py` 保留 `INTERNAL_LLM_REQUEST_TIMEOUT` / `INTERNAL_LLM_RATE_WAIT_TIMEOUT`,移除 base_url/api_key/RPM/min_interval 4 個 env
- [x] `.env.example` `# --- Internal LLM ---` 區塊僅含上述 2 key 並附說明註解
- [x] limiter 每次 acquire 即時讀傳入的 rpm/interval(不快取),設定變更下一次 acquire 生效

## 必讀檔(Just-in-time)
- [`90-third-party-service/01-client-design.md`](../../../Design-Base/90-third-party-service/01-client-design.md) · [`90-third-party-service/02-rate-and-cost.md`](../../../Design-Base/90-third-party-service/02-rate-and-cost.md) · [`03-backend/06-clients.md`](../../../Design-Base/03-backend/06-clients.md) · [`03-backend/03-async-and-tx.md`](../../../Design-Base/03-backend/03-async-and-tx.md) · [`03-backend/04-config.md`](../../../Design-Base/03-backend/04-config.md)
