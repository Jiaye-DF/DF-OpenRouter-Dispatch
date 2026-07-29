---
id: task-528
title: 前端明細頁三形態渲染 + types
status: pending
parallel: true
depends_on: [task-527]
affected_files:
  - frontend/src/app/(main)/usage-logs/[uid]/page.tsx
  - frontend/src/types/api.ts
estimated_hours: 3
---

## 目標

用量明細頁的圖片 / 檔案渲染,要能同時吃下**三種形態**:presigned URL(新)、base64 data URI(遷移前的舊列)、`upload_failed` 標記(S3 失敗)。任一形態壞掉都不能讓整頁掛掉(propose §E)。

## 範圍(只做這些)

### 1. `types/api.ts`

- `UsageRequestContent` 相關型別擴充,讓 `images[]` 元素與 `image_url.url` 的語意涵蓋「URL 字串」。
- 新增 `upload_failed` 標記的型別(image part 與 file part 兩種形狀)。
- **禁 `any`**、props 用獨立 `interface`(`AGENTS.md § Code Style`)。

### 2. `ImageItem` 渲染分支

現行邏輯是「base64 → Blob/object URL 後渲染,避免巨大 data URI 塞進 DOM」(見該檔第 27 行註解)。新增分支:

- **值為 `http(s)://`** → 直接 `src={url}`,**不**走 Blob 轉換。
- **值為 data URI** → 保留既有 Blob 轉換路徑(遷移期舊列)。
- **`upload_failed` 標記** → 顯示「圖片 #N:上傳失敗,內容未留存」+ 可得的 metadata(大小 / 型別),**不**顯示破圖或整段空白。
- **presigned URL 過期**(`onError`)→ 顯示可重新載入的提示(例:「連結已逾時,請重新整理頁面」),**不**是空白破圖。

### 3. 標示文案

現行標示為 `(base64)` / `(URL)`。改為能反映儲存位置的文案(例 `(已存檔)` / `(外部連結)` / `(未留存)`),字級與樣式對齊 `02-frontend/91-project-ui-ux.md`。

### 4. 檔案(files)顯示

- `files` 快照自本版起含路徑 → 可點擊開啟(presigned URL);舊紀錄只有檔名 → 顯示檔名但**不可點**,並標示「本版之前未留存內容」。

## 不做

- **不**動 `user-guide` 頁(532 的事)。
- **不**做縮圖 / 圖片處理 / lightbox 等新 UI 功能(propose Out of Scope)。
- **不**改列表頁(列表本來就不含 `request_content`)。

## Acceptance

- [ ] `cd frontend && npm run lint && npm run type-check && npm run build` 全綠
- [ ] `grep -c "any" frontend/src/types/api.ts` 未因本次變更增加(**禁 `any`**)
- [ ] 手測 case(於明細頁逐一確認,截圖或逐條勾選):
  - [ ] 新紀錄(presigned URL)→ 圖片正常顯示,DevTools Network 顯示 `https://` 請求且**非** data URI
  - [ ] 舊紀錄(data URI)→ 圖片正常顯示(既有 Blob 路徑未壞)
  - [ ] `upload_failed` 紀錄 → 顯示「上傳失敗,內容未留存」+ metadata,無破圖
  - [ ] 手動竄改 URL 使其失效 → 顯示可重新載入提示,**不**是空白
  - [ ] messages 模式與單輪模式兩種形狀皆正常
  - [ ] 含 `files` 的新紀錄 → 檔名可點開;舊紀錄 → 檔名不可點且有說明
- [ ] 頁面在任一形態下**皆不 crash**(錯誤邊界未被觸發,對齊 `02-frontend/01-routing-and-error.md`)
- [ ] RWD:手機寬度下圖片與提示文字不溢出(對齊 `02-frontend/06-rwd.md`)

## 必讀檔(Just-in-time)

- `docs/Design-Base/02-frontend/00-overview.md`
- `docs/Design-Base/02-frontend/01-routing-and-error.md`
- `docs/Design-Base/02-frontend/02-api-and-state.md`
- `docs/Design-Base/02-frontend/05-components.md`
- `docs/Design-Base/02-frontend/06-rwd.md`
- `docs/Design-Base/02-frontend/90-project-frontend.md`
- `docs/Design-Base/02-frontend/91-project-ui-ux.md`
