---
id: task-003
title: proxy service 串流邏輯 run_chat_stream + _stream_openrouter + 記帳
status: done
parallel: false
depends_on: [task-002]
affected_files:
  - backend/app/services/proxy.py
estimated_hours: 4
---

## 目標
於 `services/proxy.py` 新增 `run_chat_stream()` + `_stream_openrouter()` async generator,沿用既有 Key failover / rate limiter,commit point 改為「收到第一個 chunk」之前;relay 階段簡化 SSE 為 `{ id, content }`,並於 finally 寫 usage_logs。

## Acceptance
- [x] `run_chat_stream()`:`videos` 非空→400;白名單檢查;`provider != "openrouter"`→400 `feature_not_supported`;`_rewrite_request` 後注入 `stream=True`、`stream_options={"include_usage":True}`,委派 `_stream_openrouter()`。
- [x] `_stream_openrouter()` 沿用 `pick_random_active` + `get_limiter`(`wait_timeout=0`)failover 迴圈;`first = await candidate.__anext__()` 試連:401/連線錯換下一把,404/403/429 拋對應 `AppError`(pre-stream);全撞速率→429 `rate_limited`,曾連線仍失敗→502 `openrouter_unavailable`。
- [x] commit 後每行經 `_simplify_sse_line` 只吐 `{ id, content }`(空行 / keep-alive 註解 / 無文字 chunk 不轉發),同步累積 `delta.content` / `usage` / `id`;OpenRouter error chunk 轉 `data:{"error":"upstream_error"}`,後端斷線補 `data:{"error":"openrouter_unavailable"}`+`data:[DONE]`,不靜默截斷。
- [x] `finally`:`aclose` 上游並合成 `resp` dict 呼叫 `schedule_usage_log`(串完 `status=success`;中斷 / 上游錯 `status=error` 記部分內容),`latency_ms` 以請求起算到串流結束計,背景 task + 獨立 session。

## 必讀檔(Just-in-time)
- [`03-backend/03-async-and-tx.md`](../../../Design-Base/03-backend/03-async-and-tx.md) · 非同步與交易
- [`03-backend/05-exceptions-and-logging.md`](../../../Design-Base/03-backend/05-exceptions-and-logging.md) · 例外與 Log
- [`04-databases/10-statistics-log.md`](../../../Design-Base/04-databases/10-statistics-log.md) · 用量紀錄
- [`90-third-party-service/50-openrouter.md`](../../../Design-Base/90-third-party-service/50-openrouter.md) · § 4 / § 8 / § 10
- [`90-third-party-service/02-rate-and-cost.md`](../../../Design-Base/90-third-party-service/02-rate-and-cost.md) · rate limiter 與成本
