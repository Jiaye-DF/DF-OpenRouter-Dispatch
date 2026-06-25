---
id: task-002
title: OpenRouter Client 新增 list_models() / get_key_info()
status: done
parallel: true
depends_on: []
affected_files:
  - backend/app/clients/openrouter/client.py
estimated_hours: 2
---

## 目標
擴充 OpenRouter Client:`list_models()` 呼叫 `GET /models` 回傳 `data[]`(用任一把 active OR Key);`get_key_info(api_key)` 呼叫 `GET /auth/key` 回傳 `{label, usage, limit, is_free_tier}`。

## Acceptance
- [x] `grep -n "async def list_models" backend/app/clients/openrouter/client.py` 命中,簽名回傳 `list[dict]`
- [x] `grep -n "async def get_key_info" backend/app/clients/openrouter/client.py` 命中,接受 `api_key: str` 參數
- [x] `uv run pytest backend/tests/ -k "client" -q` 通過(含 list_models / get_key_info 的 mock 測試)
- [x] 上游非 2xx 時轉成統一例外(對齊 06-clients 重試/逾時/錯誤映射),不洩漏 Key 明文

## 必讀檔(Just-in-time)
- [`03-backend/06-clients.md`](../../../Design-Base/03-backend/06-clients.md) · [`03-backend/05-exceptions-and-logging.md`](../../../Design-Base/03-backend/05-exceptions-and-logging.md)
- [`90-third-party-service/00-overview.md`](../../../Design-Base/90-third-party-service/00-overview.md) · [`90-third-party-service/01-client-design.md`](../../../Design-Base/90-third-party-service/01-client-design.md) · [`90-third-party-service/50-openrouter.md`](../../../Design-Base/90-third-party-service/50-openrouter.md)
