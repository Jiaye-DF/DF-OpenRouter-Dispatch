---
id: task-002
title: 前端申請表單專案負責人改 Combobox 並自動帶入唯讀信箱
status: done
parallel: false
depends_on: [task-001]
affected_files:
  - frontend/src/types/api.ts
  - frontend/src/lib/api/endpoints.ts
  - frontend/src/app/(main)/api-key-requests/page.tsx
---

## 目標
申請表單「專案負責人」由純文字改為可搜尋 Combobox(資料源 owner-options),選取後自動帶出名稱與信箱、信箱欄位設唯讀,避免手打與 M365 不一致。

## Acceptance
- [x] `types/api.ts` 新增 `OwnerOption`(`username` + `email`)。
- [x] `lib/api/endpoints.ts` 新增 `userOwnerOptions: "/api/v1/users/owner-options"`。
- [x] `api-key-requests/page.tsx` 載入負責人清單(`owners` state + 一次性 effect)。
- [x] `ownerOptions` memo(value = `email`,label = `名稱(信箱)`)+ `onSelectOwner` 同時帶出 `owner_name` / `owner_email`。
- [x] 「專案負責人」改 `Combobox`(可搜尋姓名 / 信箱);「專案負責人信箱」改唯讀自動帶入。
- [x] 前端 `tsc --noEmit` 無錯。

## 必讀檔(Just-in-time)
- [`02-frontend/02-api-and-state.md`](../../../Design-Base/02-frontend/02-api-and-state.md) · 載入清單 state / effect 與 endpoints 集中管理
- [`02-frontend/05-components.md`](../../../Design-Base/02-frontend/05-components.md) · Combobox 可搜尋與唯讀欄位
- [`02-frontend/91-project-ui-ux.md`](../../../Design-Base/02-frontend/91-project-ui-ux.md) · 「名稱(信箱)」label 與唯讀帶入比照部門模式
- [`00-overview/04-api-docs.md`](../../../Design-Base/00-overview/04-api-docs.md) · 型別與端點對應
