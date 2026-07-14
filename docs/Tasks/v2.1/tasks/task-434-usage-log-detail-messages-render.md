---
id: task-434
title: 前端:用量記錄明細頁 messages 模式相容渲染(分角色;舊單輪形狀不變)
status: done
parallel: true
depends_on: [task-432]
affected_files:
  - frontend/src/app/(main)/usage-logs/[uid]/page.tsx
estimated_hours: 2
---

## 目標

用量記錄明細頁(`frontend/src/app/(main)/usage-logs/[uid]/page.tsx`)的 `request_content` 渲染區支援 messages 模式:依 role 分段顯示(system / user / assistant 各自標示),content parts 依型別呈現(text 文字、image 縮圖、file 檔名);舊單輪形狀(`{text, images, ...}`)渲染**完全不變**。

## 實作要點(對齊 propose §C.2 / §D.4)

- 以**形狀判別**分流:`request_content.messages` 存在(陣列)→ messages 渲染;否則走既有單輪渲染。不做資料遷移、不假設後端回傳版本。
- role 標示樣式對齊既有 ui 慣例(Badge / 區塊標題);content 為字串與 parts 陣列兩種形狀都要處理。
- file part 只有 `filename`(432 快照策略)→ 顯示檔名;image_url part 為 base64/URL → 沿用既有圖片縮圖顯示方式。
- 型別以頁面內區域型別(discriminated by shape)處理,**不動** `frontend/src/types/api.ts`(該檔由 task-437 持鎖;若實作中發現必須動,回報 orchestrator 重排,禁自行擴檔)。
- AI 分析區塊(admin-only)與其餘欄位渲染不動。

## Acceptance

- [ ] `npm run lint`(frontend/)與 `npx tsc --noEmit` 零錯誤零 warning
- [ ] 手測 case(dev 環境,配合 432/433 完成後的資料;先行可用 mock 資料驗證元件分支):
  - [ ] messages 模式紀錄:明細頁分角色渲染 system/user/assistant,text/image/file part 各自正確呈現
  - [ ] 舊單輪紀錄(v2.1.1 前產生):渲染與現況一致(視覺回歸)
  - [ ] `request_content` 為 null 的歷史紀錄:不噴錯、顯示現況佔位
- [ ] `git diff frontend/src/types/api.ts` 為空

## 必讀檔(Just-in-time)

- `docs/Design-Base/02-frontend/00-overview.md`(風格地板)
- `docs/Design-Base/02-frontend/05-components.md`(reuse 判準;渲染邏輯留頁內或抽共用)
- `docs/Design-Base/02-frontend/90-project-frontend.md` + `91-project-ui-ux.md`(本專案 UI 慣例)
- `docs/Tasks/v2.1/propose-v2.1.2.md` §C.2/§D.4
