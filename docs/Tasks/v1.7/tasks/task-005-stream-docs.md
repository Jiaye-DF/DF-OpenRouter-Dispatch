---
id: task-005
title: 更新串流端點對外文件與 50-openrouter § 7 規格
status: done
parallel: true
depends_on: []
affected_files:
  - docs/INTEGRATION.md
  - docs/Design-Base/90-third-party-service/50-openrouter.md
estimated_hours: 2
---

## 目標
更新對外 SDK 文件與 Design-Base 規格:`50-openrouter.md § 7` 由「預留」改為正式串流規格(補錯誤對照與記帳時機),`docs/INTEGRATION.md` 新增串流端點呼叫方式與 SSE 解析說明。

## Acceptance
- [x] `50-openrouter.md § 7` 由「預留」改為正式規格,含簡化 `{ id, content }` 格式、錯誤對照、記帳時機(`finally` 寫 usage_logs)。
- [x] `docs/INTEGRATION.md` 新增 `POST /api/v1/model/chat/stream` 的呼叫範例與 SSE 解析說明(`data: {...}` … `data: [DONE]`)。
- [x] 文件明確標示串流只回 `{ id, content }`,OpenRouter 內部欄位(provider / cost / usage)不外露。
- [x] 文件與實作端點契約一致(headers、body、回應型別)。

## 必讀檔(Just-in-time)
- [`00-overview/04-api-docs.md`](../../../Design-Base/00-overview/04-api-docs.md) · API 文件規範
- [`90-third-party-service/50-openrouter.md`](../../../Design-Base/90-third-party-service/50-openrouter.md) · § 7 串流規格本體
- [`90-third-party-service/00-overview.md`](../../../Design-Base/90-third-party-service/00-overview.md) · 第三方服務總覽
