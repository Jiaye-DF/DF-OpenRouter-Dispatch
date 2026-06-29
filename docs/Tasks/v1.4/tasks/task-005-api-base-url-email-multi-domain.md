---
id: task-005
title: 填實際 API Base URL + 使用者建立 Email 多網域選擇
status: done
parallel: true
depends_on: []
affected_files:
  - docs/INTEGRATION.md
  - frontend/src/app/(main)/user-guide/page.tsx
  - frontend/src/app/(main)/users/page.tsx
estimated_hours: 2
---

## 目標
將文件與前端的 API Base URL 占位網址換成測試 / 正式環境實際值,並讓建立使用者時 Email 後綴可選 `@df-recycle.com` 或 `@df-recycle.com.tw`。

## Acceptance
- [x] `docs/INTEGRATION.md` 填入測試 / 正式環境實際網址,範例替換 `<正式站網址>` 占位符
- [x] `user-guide/page.tsx` 的 `TEST_API_BASE` / `PROD_API_BASE` 常數填入實際值
- [x] `user-guide/page.tsx` 補上「查詢可用模型清單」(GET `/api/v1/models`)區塊
- [x] `users/page.tsx` 建立使用者 Email 後綴改為下拉選單(`@df-recycle.com` / `@df-recycle.com.tw`)

## 必讀檔(Just-in-time)
- [`00-overview/04-api-docs.md`](../../../Design-Base/00-overview/04-api-docs.md) · [`00-overview/00-overview.md`](../../../Design-Base/00-overview/00-overview.md)
- [`02-frontend/05-components.md`](../../../Design-Base/02-frontend/05-components.md) · [`02-frontend/02-api-and-state.md`](../../../Design-Base/02-frontend/02-api-and-state.md)
