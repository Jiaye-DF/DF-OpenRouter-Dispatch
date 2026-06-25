---
id: task-001
title: 新增 OPENROUTER_STREAM_TIMEOUT 設定與 env 同步
status: done
parallel: true
depends_on: []
affected_files:
  - backend/app/core/config.py
  - .env.example
estimated_hours: 1
---

## 目標
新增串流專用連線逾時設定 `OPENROUTER_STREAM_TIMEOUT`(預設 300 秒),避免串流被既有 `OPENROUTER_API_TIMEOUT`(60s)提早中斷,並同步 `.env.example`。

## Acceptance
- [x] `core/config.py` 新增 `OPENROUTER_STREAM_TIMEOUT: int = 300` 設定欄位。
- [x] `.env.example` 於 `# --- OpenRouter ---` 區段新增同名 key 與預設值 300。
- [x] 程式用到的環境變數皆已於 `.env.example` 定義,無缺漏。
- [x] 既有 `OPENROUTER_API_TIMEOUT` 行為不受影響(非串流端點維持原逾時)。

## 必讀檔(Just-in-time)
- [`03-backend/00-overview.md`](../../../Design-Base/03-backend/00-overview.md) · 後端規範總覽
- [`90-third-party-service/50-openrouter.md`](../../../Design-Base/90-third-party-service/50-openrouter.md) · § 11 設定與健康檢查
