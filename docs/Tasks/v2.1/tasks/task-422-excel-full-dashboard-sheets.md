---
id: task-422
title: 前端 Excel 補 4 sheet(總覽/專案×模型/依模型/時序)+ 儀表板下載串接 + types/endpoints
status: pending
parallel: true
depends_on: [task-420]
affected_files:
  - frontend/src/lib/export/excel.ts
  - frontend/src/app/(main)/dashboard/page.tsx
  - frontend/src/types/api.ts
  - frontend/src/lib/api/endpoints.ts
estimated_hours: 3
---

## 目標

讓下載的 Excel 成為儀表板的完整實體表格:在既有「部門/專案/使用者」三 sheet 外補「總覽 KPI / 專案×模型明細 / 依模型 / 時序」四 sheet,並於下載時補抓 `by-project-model`(對齊 propose §C.1 / §C.2)。

## 範圍與要點

- **型別/端點**:`types/api.ts` 新增 `StatsByProjectModel`(對應 task-420 `ProjectModelStatItem`:`project_uid/project_code/project_name/model/total_requests/total_tokens/total_cost_usd`);`lib/api/endpoints.ts` 新增 `statsByProjectModel: "/api/v1/stats/by-project-model"`。
- **excel.ts**:`DashboardExportInput` 擴充 `overview? / byModel? / byProjectModel? / timeseries?`;沿用既有 `buildSheet` / `USD_FORMAT` / 欄寬估算新增 sheet builder —
  - **總覽**:兩欄 `["指標","值"]`,列「總請求數 / 總 Tokens / 總成本 (USD)」;成本列套 USD 格式。
  - **專案×模型**:`["專案代碼","專案名稱","模型","請求數","Tokens","成本 (USD)"]`,`usdColumns:[5]`。
  - **依模型**:`["模型","請求數","Prompt Tokens","Completion Tokens","Tokens","成本 (USD)"]`,`usdColumns:[5]`。
  - **時序**:`["時間 (UTC+8)","請求數","Tokens","成本 (USD)"]`,時間用既有 `utils/datetime` 格式化,`usdColumns:[3]`。
  - sheet 追加順序:總覽 → 部門 → 專案 → 專案×模型 → 依模型 → 使用者 → 時序(既有三 sheet 欄位不動)。
- **dashboard/page.tsx**:`onDownloadExcel` 內 `await` 補抓 `API_ENDPOINTS.statsByProjectModel`(同畫面篩選參數,含台北日界 +08:00),連同畫面已持有的 `overview/byModel/timeseries` 一併傳入 `exportDashboardToExcel`;`!hasAnyData` disabled 邏輯不變;檔名維持 `dashboard_{from}_{to}.xlsx`。

## Acceptance

- [ ] `cd frontend && npm run lint && npx tsc --noEmit` 零錯誤零 warning
- [ ] `grep -n "statsByProjectModel" frontend/src/lib/api/endpoints.ts` 命中;`grep -n "StatsByProjectModel" frontend/src/types/api.ts` 命中
- [ ] `grep -nE "總覽|專案代碼.*模型|Prompt Tokens|時間 \(UTC\+8\)" frontend/src/lib/export/excel.ts` 命中四個新 sheet header
- [ ] 手測(記於 PR):下載 Excel 得 7 個 sheet;專案×模型 sheet 每專案各模型成本加總 == 專案 sheet 該專案總成本;成本欄顯示為 6 位小數 USD 格式
- [ ] `cd frontend && npm run build` 成功

## 必讀檔(Just-in-time)

- `docs/Design-Base/02-frontend/00-overview.md`
- `docs/Design-Base/02-frontend/02-api-and-state.md`
- `docs/Design-Base/02-frontend/04-datetime.md`
- `docs/Design-Base/02-frontend/05-components.md`
- `docs/Design-Base/02-frontend/90-project-frontend.md`
- `docs/Design-Base/00-overview/05-timezone.md`
