---
id: task-003
title: 前端 types + 用量列表「工具」欄與篩選 + 單筆 Input/Output 詳情頁
status: done
parallel: false
depends_on: [task-002]
affected_files:
  - src/types/api.ts
  - src/app/(main)/usage-logs/page.tsx
  - src/app/(main)/usage-logs/[uid]/page.tsx
estimated_hours: 4
---

## 目標
前端型別補 `used_tools` 與詳情型別,用量列表加工具欄與篩選 chip 且可點進詳情,並新增詳情頁顯示 Input(text/tools/base64 圖前端轉檔)與 Output。

## Acceptance
- [x] `src/types/api.ts` `UsageLog` 加 `used_tools` / `openrouter_generation_id`;新增 `UsageLogDetail` / `UsageRequestContent` / `UsageResponseSummary`
- [x] `src/app/(main)/usage-logs/page.tsx` 加「工具」欄(Badge「工具」/「—」)、「是否用工具」篩選 chip(全部 / 有用工具 / 未用工具 → query `used_tools`)、每列可點 `router.push('/usage-logs/{uid}')` 且 hover cursor
- [x] `src/app/(main)/usage-logs/[uid]/page.tsx`(新):打 `usageLogById` 取單筆,呈現 Metadata + Input(text / tools JSON 美化 / images)+ Output 三區
- [x] Input base64 圖以 `URL.createObjectURL` blob 顯示 + 開新分頁/下載,卸載時 `revokeObjectURL`;一般 URL 直接顯示
- [x] Output 顯示 `output_text` ?? `first_text`,舊紀錄(僅 first_text)標註「僅前 500 字」;含返回用量紀錄按鈕
- [x] `npm run type-check` 通過

## 必讀檔(Just-in-time)
- [`02-frontend/00-overview.md`](../../../../Design-Base/02-frontend/00-overview.md) · [`02-frontend/01-routing-and-error.md`](../../../../Design-Base/02-frontend/01-routing-and-error.md) · [`02-frontend/02-api-and-state.md`](../../../../Design-Base/02-frontend/02-api-and-state.md) · [`02-frontend/05-components.md`](../../../../Design-Base/02-frontend/05-components.md)
- [`02-frontend/06-rwd.md`](../../../../Design-Base/02-frontend/06-rwd.md) · [`02-frontend/91-project-ui-ux.md`](../../../../Design-Base/02-frontend/91-project-ui-ux.md) · [`90-third-party-service/50-openrouter.md`](../../../../Design-Base/90-third-party-service/50-openrouter.md)
