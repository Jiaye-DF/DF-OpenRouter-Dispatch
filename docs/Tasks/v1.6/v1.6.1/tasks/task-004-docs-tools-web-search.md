---
id: task-004
title: 文件與使用說明頁補 tools 透傳說明
status: done
parallel: true
depends_on: []
affected_files:
  - docs/INTEGRATION.md
  - docs/Design-Base/90-third-party-service/50-openrouter.md
  - frontend/src/app/(main)/user-guide/page.tsx
estimated_hours: 2
---

## 目標
於使用者文件、Design-Base OpenRouter 規範與後台「使用者使用說明」頁補上 `tools` 透傳(web search)說明:欄位表新增 `tools` 列、新增 web search 範例與注意事項。

## Acceptance
- [x] `docs/INTEGRATION.md` §5 欄位表新增 `tools` 列,並新增 §5.2「啟用工具(web search)」JSON 範例與 3 點注意事項
- [x] `docs/Design-Base/90-third-party-service/50-openrouter.md` §5 與 §6 各補 tools 透傳說明
- [x] `frontend/src/app/(main)/user-guide/page.tsx` Request Body 欄位表新增 `tools` 列、新增 `TOOLS_EXAMPLE` 與 3 點說明
- [x] `npm run type-check` 通過

## 必讀檔(Just-in-time)
- [`90-third-party-service/50-openrouter.md`](../../../../Design-Base/90-third-party-service/50-openrouter.md) · OpenRouter tools 透傳與 web search 規範
- [`00-overview/04-api-docs.md`](../../../../Design-Base/00-overview/04-api-docs.md) · 對外 API 文件規範
- [`02-frontend/05-components.md`](../../../../Design-Base/02-frontend/05-components.md) · 使用說明頁元件與範例呈現規範
