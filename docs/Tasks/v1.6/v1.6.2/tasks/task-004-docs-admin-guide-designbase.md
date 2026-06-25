---
id: task-004
title: 文件:admin-guide 速查補述 + Design-Base 50 §6 補 output_text/used_tools
status: done
parallel: true
depends_on: []
affected_files:
  - src/app/(main)/admin-guide/page.tsx
  - docs/Design-Base/90-third-party-service/50-openrouter.md
estimated_hours: 1
---

## 目標
更新管理頁速查與 Design-Base OpenRouter 記帳章節,記載用量紀錄工具篩選、詳情頁與 `output_text` / `used_tools` 行為。

## Acceptance
- [x] `src/app/(main)/admin-guide/page.tsx`「管理頁速查」用量紀錄列補述工具篩選與詳情頁
- [x] `docs/Design-Base/90-third-party-service/50-openrouter.md` §6 Response 記帳補 `output_text`(完整回覆取代截斷)與 `used_tools`(由 tools 推導)說明
- [x] 確認 SDK 對外呼叫行為未變,INTEGRATION.md / user-guide 不需更新(標 N/A)

## 必讀檔(Just-in-time)
- [`90-third-party-service/00-overview.md`](../../../../Design-Base/90-third-party-service/00-overview.md) · [`90-third-party-service/50-openrouter.md`](../../../../Design-Base/90-third-party-service/50-openrouter.md)
- [`00-overview/00-overview.md`](../../../../Design-Base/00-overview/00-overview.md) · [`00-overview/04-api-docs.md`](../../../../Design-Base/00-overview/04-api-docs.md)
