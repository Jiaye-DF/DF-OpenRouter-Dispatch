---
id: task-001
title: 新增 ChatFile / ChatRequest.files schema
status: done
parallel: true
depends_on: []
affected_files:
  - backend/app/schemas/model.py
estimated_hours: 1
---

## 目標
於 `schemas/model.py` 新增 `ChatFile` 模型與 `ChatRequest.files` 可選欄位,作為檔案上傳(PDF 等)多模態輸入的型別契約。

## Acceptance
- [x] 新增 `ChatFile`,含 `filename`(`min_length=1, max_length=255`)與 `file_data`(`min_length=1`),兩者必填。
- [x] `ChatRequest` 新增 `files: list[ChatFile] | None = None`,語意對齊既有 `images`。
- [x] `ChatFile` 缺 `filename` 或 `file_data`(含空字串)時 Pydantic 回 422。
- [x] 不帶 `files` 的既有請求行為不變(預設 `None`,向後相容)。
- [x] Swagger `/api/docs` 自動反映 `files` 欄位(由 Pydantic schema 產生)。

## 必讀檔(Just-in-time)
- [`03-backend/00-overview.md`](../../../Design-Base/03-backend/00-overview.md) · [`03-backend/01-routing.md`](../../../Design-Base/03-backend/01-routing.md) · [`00-overview/04-api-docs.md`](../../../Design-Base/00-overview/04-api-docs.md) · [`90-third-party-service/50-openrouter.md`](../../../Design-Base/90-third-party-service/50-openrouter.md)
