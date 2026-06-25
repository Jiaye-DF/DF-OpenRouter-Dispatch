---
id: task-002
title: OpenRouterClient 新增 stream_chat_completion 串流方法
status: done
parallel: true
depends_on: []
affected_files:
  - backend/app/clients/openrouter/client.py
estimated_hours: 3
---

## 目標
於 `OpenRouterClient` 新增 async generator `stream_chat_completion()`,以 `httpx.AsyncClient.stream()` 開連線,先檢查 HTTP 狀態碼(供 failover 判斷),200 才逐行 yield SSE 內容。

## Acceptance
- [x] 以 `self._client.stream("POST", f"{base}/chat/completions", json=payload, headers=headers, timeout=httpx.Timeout(OPENROUTER_STREAM_TIMEOUT))` 開連線。
- [x] yield 第一行**之前**先判斷 `resp.status_code`:401→`OpenRouterAuthError`、403→`Forbidden`、404→`ModelNotFound`、429→`RateLimit`、≥400→`OpenRouterError`(以 `await resp.aread()` 取錯誤 body)。
- [x] status 200 才 `async for line in resp.aiter_lines(): yield line`,為 async generator。
- [x] 解密後 OpenRouter Key 不出現於回傳內容,只可進後端 Log 前後 4 字元。

## 必讀檔(Just-in-time)
- [`03-backend/06-clients.md`](../../../Design-Base/03-backend/06-clients.md) · 外部 client 設計
- [`90-third-party-service/01-client-design.md`](../../../Design-Base/90-third-party-service/01-client-design.md) · client 設計準則
- [`90-third-party-service/50-openrouter.md`](../../../Design-Base/90-third-party-service/50-openrouter.md) · § 7 串流 / § 9 錯誤對應
