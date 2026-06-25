---
id: task-002
title: proxy 組裝 file content part 與用量紀錄只存檔名
status: done
parallel: false
depends_on: [task-001]
affected_files:
  - backend/app/services/proxy.py
estimated_hours: 3
---

## 目標
擴充 `proxy.py` 的 `_rewrite_request()` 與 `_build_request_log()`,將 `files` 組裝為 OpenRouter `file` content part 透傳,並在用量紀錄中**僅保留檔名、不留存檔案內容**(法務取捨)。

## Acceptance
- [x] `_rewrite_request()` 簽名加 `files: list[dict[str, str]] | None = None`,於 images 之後對每個 file append `{"type":"file","file":{"filename":..., "file_data":...}}` 至 user 訊息 content。
- [x] text / images / files 皆空時仍補空白 text block,維持「messages 不為空」保證。
- [x] `_build_request_log()` 簽名加 `files`,僅寫入 `log["files"] = [f["filename"] for f in files]`,**不**寫入 `file_data`;有值才出現(與 `tools` 一致)。
- [x] `run_chat()` / `run_chat_stream()` 簽名加 `files`,分別透傳給 `_rewrite_request(...)` 與 `_build_request_log(...)`;白名單 / failover / 記帳流程不變。
- [x] `file_data` 支援 base64 data URL 與遠端 URL,皆原樣帶入送 OpenRouter 的 payload。

## 必讀檔(Just-in-time)
- [`90-third-party-service/50-openrouter.md`](../../../Design-Base/90-third-party-service/50-openrouter.md) · [`90-third-party-service/01-client-design.md`](../../../Design-Base/90-third-party-service/01-client-design.md) · [`03-backend/06-clients.md`](../../../Design-Base/03-backend/06-clients.md) · [`04-databases/10-statistics-log.md`](../../../Design-Base/04-databases/10-statistics-log.md) · [`04-databases/03-passwords-and-pii.md`](../../../Design-Base/04-databases/03-passwords-and-pii.md)
