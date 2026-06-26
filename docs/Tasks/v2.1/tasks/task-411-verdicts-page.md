---
id: task-411
title: AI 判決總覽頁重做(依用量紀錄分組 + 原 vs 推薦模型1/2/3 真實輸出並排 + 統計)
status: done
parallel: false
depends_on: [task-408, task-409]
affected_files:
  - frontend/src/app/(main)/ai-analysis/verdicts/page.tsx
estimated_hours: 4
---

## 目標

重做 admin 頁「AI 判決總覽」(`/ai-analysis/verdicts`,sidebar「AI 分析」已掛入口)為**詳細並排比較頁**:依用量紀錄分組,並排呈現「原模型 vs 推薦模型1/2/3 的真實輸出原文」+ 成本Δ + 裁決 + 頁頂裁決分布統計。**禁止**任何連回 `/usage-logs/*` 的連結。對齊 propose §6.1 / §6.2(視覺形式已定案)。

## 範圍與要點(視覺形式定案,propose §6.2)

- 資料:`apiClient.get<RerunOverviewPage>(API_ENDPOINTS.aiRerunsOverview, { query: { page, size } })`(task-408/409 產物);admin 角色守衛(非 admin 顯示權限不足,對齊既有頁)。
- **頁頂統計列**:`stats` 渲染為一排小指標卡——總筆數 / 建議維持 / 建議改用 / 平手 / 未裁決 / 失敗。
- **主體=分組 Card 列表**(每組=一筆 `RerunGroup`,可展開 / 收合):
  - 收合:`原模型 key → 推薦模型數` + 彙總裁決 Badge(如「2/3 建議維持」)+ 執行時間。
  - 展開=**並排欄位比較**:第一欄固定「原模型(原始)」,後接推薦模型欄(`recommendations`)。
    - 每欄頂:模型 key + tier(原模型欄標「原始」)。
    - 每欄主體:**真實輸出原文**——原模型用 `group.original_output_text`、推薦模型用 `recommendation.output_text`;以 `max-h` + 內部捲動呈現;為 null 時顯示「無原始輸出快照」/「無輸出」。
    - 推薦欄底:真實成本 + **成本Δ**(綠=更省 / 紅=更貴)+ 延遲 + **裁決 Badge**(`winnerLabel`/`winnerTone`)+ 信心(`formatConfidencePercent`)+ 理由。
  - 失敗 / 未裁決狀態 Badge 比照既有 label。
- **RWD**:桌機多欄 grid 並排;手機垂直堆疊(原模型置頂,推薦模型依序);觸控目標 ≥ 44px。
- **禁跳轉**:不得有 `router.push("/usage-logs...")` / `<Link href="/usage-logs...">` / `onClick` 導頁;明細全由本頁 API 一次帶足。
- label / util 一律取自 `lib/ai-eval-labels.ts`(task-409),禁本檔硬編中文裁決字串或硬編端點。
- 日期顯示對齊 `02-frontend/04-datetime.md`(禁 `toLocaleString` / `timeZone`)。

## Acceptance

- [ ] `npm run typecheck` 與 `npm run lint`(於 frontend/)零錯誤零 warning
- [ ] `npm run build`(於 frontend/)成功
- [ ] `grep -nE "usage-logs|usageLogById|router.push\(.?/usage" "frontend/src/app/(main)/ai-analysis/verdicts/page.tsx"` **零命中**(全頁無連回用量紀錄)
- [ ] `grep -nE "original_output_text|\.output_text" "frontend/src/app/(main)/ai-analysis/verdicts/page.tsx"` 皆命中(原模型 + 推薦模型真實輸出原文都有渲染)
- [ ] `grep -n "stats" "frontend/src/app/(main)/ai-analysis/verdicts/page.tsx"` 命中(頁頂統計列有渲染)
- [ ] 手動驗證(admin 登入):總覽頁依用量紀錄分組,展開可見原模型與推薦模型1/2/3 真實輸出並排、成本Δ、裁決、信心;手機寬度欄位垂直堆疊不破版

## 必讀檔(Just-in-time)

- `docs/Design-Base/02-frontend/00-overview.md`
- `docs/Design-Base/02-frontend/02-api-and-state.md`
- `docs/Design-Base/02-frontend/04-datetime.md`
- `docs/Design-Base/02-frontend/05-components.md`
- `docs/Design-Base/02-frontend/06-rwd.md`
- `docs/Design-Base/02-frontend/90-project-frontend.md`
- `docs/Design-Base/02-frontend/91-project-ui-ux.md`
