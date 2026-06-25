---
id: task-002
title: proxy 服務層透傳 tools 並補 docstring
status: done
parallel: true
depends_on: []
affected_files:
  - backend/app/services/proxy.py
estimated_hours: 3
---

## 目標
讓 `_rewrite_request` / `_build_request_log` / `run_chat` 接收並透傳 `tools`(有值才放進 payload 與 request log),OpenRouter 與 internal 兩條路徑共用同一 payload;`_extract_content` 維持回純文字;串接鏈路每個 function 補 Google-style docstring。

## Acceptance
- [x] `run_chat` 新增 `tools` 參數並往下傳給 `_rewrite_request` 與 `_build_request_log`
- [x] `_rewrite_request` 在 `tools` 有值時放進 `payload["tools"]`,無值不放
- [x] `_build_request_log` 在 `tools` 有值時寫進 request log,無值不寫
- [x] `_extract_content` 維持回傳純文字(`message.content`)不變
- [x] 串接鏈路上每個 function 補繁中 Google-style docstring(Args/Returns/Raises)
- [x] `python -m py_compile backend/app/services/proxy.py` 通過

## 必讀檔(Just-in-time)
- [`90-third-party-service/50-openrouter.md`](../../../../Design-Base/90-third-party-service/50-openrouter.md) · 請求改寫表格與 tools 透傳規範
- [`03-backend/03-async-and-tx.md`](../../../../Design-Base/03-backend/03-async-and-tx.md) · proxy 非同步呼叫與下游 client 規範
- [`03-backend/00-overview.md`](../../../../Design-Base/03-backend/00-overview.md) · 後端服務層結構
