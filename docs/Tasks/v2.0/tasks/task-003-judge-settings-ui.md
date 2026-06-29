---
id: task-003
title: 「AI 分析」side-bar +「設定判別模型」頁(前端串接)
status: done
parallel: false
depends_on: [task-002]
affected_files:
  - frontend/src/components/layout/Sidebar.tsx
  - frontend/src/app/(main)/ai-analysis/judge-settings/page.tsx
  - frontend/src/lib/api/endpoints.ts
  - frontend/src/types/api.ts
  - frontend/src/store/api.ts
estimated_hours: 3
---

## 目標

依 propose §6 新增 side-bar 分類「AI 分析」與其下「設定判別模型」頁,串接 task-002 的 API,讓 admin 從模型管理現有模型挑恰 3 個判別模型並儲存。

## 範圍

- **Side-bar**:`Sidebar.tsx` 新增分類「AI 分析」+ 子項「設定判別模型」(admin 可見),路由 `/ai-analysis/judge-settings`。
- **頁面**:3 個 Combobox 槽位,清單來源 = **模型管理的 active 模型**(沿用既有 models 查詢);限恰 3 個、不可重複;載入時以 `GET` 回填,儲存呼叫 `PUT`。
- **API 串接**:`endpoints.ts` 加路徑、`types/api.ts` 加型別、`store/api.ts` 加 RTK Query endpoints(`02-frontend/02-api-and-state.md`)。
- 沿用既有共用元件(Combobox / Card / toast),**不改既有頁面**。

## Acceptance

- [ ] side-bar 出現「AI 分析」分類與「設定判別模型」項;點擊進入 `/ai-analysis/judge-settings`
- [ ] 頁面 3 個 Combobox 清單為 active 模型(與模型管理同源),**限恰 3 個、不可重複**(UI 阻擋重複選取)
- [ ] 進頁以 `GET` 回填現有設定;儲存呼叫 `PUT`,成功顯示 toast;**重整後設定保留**
- [ ] 既有頁面 / 路由無迴歸(side-bar 其他項正常)
- [ ] `cd frontend && npm run lint` 零 warning(`99-code-review/04-lint-checklist.md`)
- [ ] `npx tsc --noEmit` 無型別錯誤
- [ ] `npm run build` 成功

## 必讀檔(Just-in-time)

- `AGENTS.md`
- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/02-frontend/00-overview.md`
- `docs/Design-Base/02-frontend/01-routing-and-error.md`
- `docs/Design-Base/02-frontend/02-api-and-state.md`
- `docs/Design-Base/02-frontend/03-env-and-auth.md`
- `docs/Design-Base/02-frontend/05-components.md`
- `docs/Design-Base/02-frontend/90-project-frontend.md`
- `docs/Design-Base/02-frontend/91-project-ui-ux.md`
