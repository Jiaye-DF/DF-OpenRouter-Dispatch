---
id: task-009
title: OpenRouter client(httpx wrapper + chat 呼叫 + 部門 active Key 選擇 / failover)
status: done
parallel: false
depends_on: [task-005]
affected_files:
  - backend/app/clients/openrouter/__init__.py
  - backend/app/clients/openrouter/client.py
  - backend/app/services/openrouter_key/selection.py
  - backend/tests/clients/test_openrouter_client.py
estimated_hours: 3
---

## 目標

依 propose § 3.4 / § 4 實作 OpenRouter 對外 client:`clients/openrouter/` 封裝 httpx chat/completions 呼叫與錯誤對應(429 `rate_limited` / 404 `model_not_found` / 401 失效);Key 選擇 helper 給定 `department_uid` 取 active Key 隨機挑一把、401 連續 failover 下一把(上限 = active key 數,封頂 5),全數失效回 502 `openrouter_unavailable`。`parallel:false`:相依 OR Key 模組(005)。

## Acceptance

- [x] `uv run pytest tests/clients/test_openrouter_client.py` 全綠(respx stub 上游)
- [x] 所有 active Key 皆 401 → 502 `openrouter_unavailable`,且嘗試次數 ≤ min(active, 5)(斷言)
- [x] 上游 429 → `rate_limited`、404 → `model_not_found` 的錯誤對應(斷言)
- [x] 對外呼叫一律經本 client:`grep -rn "httpx" backend/app/clients/openrouter` 為唯一建立 client 處

## 必讀檔(Just-in-time)

- [`90-third-party-service/00-overview.md`](../../../Design-Base/90-third-party-service/00-overview.md) · [`01-client-design.md`](../../../Design-Base/90-third-party-service/01-client-design.md)
- [`90-third-party-service/50-openrouter.md`](../../../Design-Base/90-third-party-service/50-openrouter.md)(§8 重試 / §9 錯誤對應)
- [`03-backend/06-clients.md`](../../../Design-Base/03-backend/06-clients.md)
