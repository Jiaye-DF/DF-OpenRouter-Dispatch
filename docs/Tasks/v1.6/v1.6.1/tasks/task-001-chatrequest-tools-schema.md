---
id: task-001
title: ChatRequest 新增 tools 透傳欄位與 docstring
status: done
parallel: true
depends_on: []
affected_files:
  - backend/app/schemas/model.py
estimated_hours: 1
---

## 目標
於 `ChatRequest` 新增 `tools: list[dict[str, Any]] | None = None` 欄位,原樣透傳 OpenRouter server 端工具(如 web search),並補上類別 docstring 與欄位註解。

## Acceptance
- [x] `ChatRequest` 新增 `tools: list[dict[str, Any]] | None = None` 欄位,預設 None
- [x] `tools` 欄位有內聯註解,標明僅支援 server 端工具、function calling 未開放
- [x] `ChatRequest` 補上類別 docstring(繁中)
- [x] `python -m py_compile backend/app/schemas/model.py` 通過

## 必讀檔(Just-in-time)
- [`90-third-party-service/50-openrouter.md`](../../../../Design-Base/90-third-party-service/50-openrouter.md) · OpenRouter tools 透傳與 web search 規範
- [`03-backend/01-routing.md`](../../../../Design-Base/03-backend/01-routing.md) · schema 與請求模型規範
