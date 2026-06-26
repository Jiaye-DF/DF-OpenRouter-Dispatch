---
id: task-409
title: 前端「分組」型別 + 端點常數收斂 + 裁決 label/util
status: done
parallel: true
depends_on: [task-407]
affected_files:
  - frontend/src/types/api.ts
  - frontend/src/lib/api/endpoints.ts
  - frontend/src/lib/ai-eval-labels.ts
estimated_hours: 2
---

## 目標

前端型別與端點對齊 task-407/408 改版:新增**依用量紀錄分組**型別(含輸出原文 + stats)、移除舊扁平型別與 by-usage-log 端點常數;裁決 label/util 補齊總覽頁所需。供 task-411 總覽頁消費。

## 範圍與要點

- `frontend/src/types/api.ts`:
  - 新增 `RerunRecommendation`(對應後端,含 `output_text: string | null`)、`RerunGroup`(含 `original_output_text: string | null`、`recommendations: RerunRecommendation[]`)、`RerunStats`、`RerunOverviewPage`(`items: RerunGroup[]` + `total/page/size` + `stats`)。
  - **移除** `RerunResult`、`RerunListResponse`、`RerunOverviewItem`(舊扁平、無輸出原文)。
  - 金額 / 信心維持 `string | null`(Decimal→string 慣例);註解去黑話(challenger→AI 推薦模型)。
- `frontend/src/lib/api/endpoints.ts`:
  - **移除** `aiRerunsByUsageLog`(端點已下線);保留 `aiRerunsOverview`(`/api/v1/ai-eval/reruns`)。
- `frontend/src/lib/ai-eval-labels.ts`:
  - 保留既有 `winnerLabel` / `winnerTone` / `formatConfidencePercent`;若總覽頁需要,集中新增「裁決分布」中文 label(維持單一來源,禁前端各頁硬編)。

## Acceptance

- [ ] `npm run typecheck`(於 frontend/)零錯誤
- [ ] `npm run lint`(於 frontend/)零錯誤零 warning
- [ ] `grep -nE "RerunResult|RerunListResponse|RerunOverviewItem" frontend/src/types/api.ts` **零命中**
- [ ] `grep -nE "interface (RerunGroup|RerunRecommendation|RerunStats|RerunOverviewPage)" frontend/src/types/api.ts` 四者皆命中
- [ ] `grep -n "aiRerunsByUsageLog" frontend/src/lib/api/endpoints.ts` **零命中**;`grep -n "aiRerunsOverview" frontend/src/lib/api/endpoints.ts` 命中
- [ ] `grep -nE "original_output_text|output_text" frontend/src/types/api.ts` 皆命中

## 必讀檔(Just-in-time)

- `docs/Design-Base/02-frontend/00-overview.md`
- `docs/Design-Base/02-frontend/02-api-and-state.md`
- `docs/Design-Base/02-frontend/04-datetime.md`
- `docs/Design-Base/02-frontend/05-components.md`
- `docs/Design-Base/02-frontend/90-project-frontend.md`
