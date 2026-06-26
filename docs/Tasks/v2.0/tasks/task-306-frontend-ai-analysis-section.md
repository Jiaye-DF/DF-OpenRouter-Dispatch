---
id: task-306
title: AI 分析基礎摘要區塊 + usage-log 明細頁內嵌
status: pending
parallel: false
depends_on: [task-304, task-305]
affected_files:
  - frontend/src/app/(main)/usage-logs/[uid]/AiAnalysisSection.tsx
  - frontend/src/app/(main)/usage-logs/[uid]/page.tsx
estimated_hours: 2.5
---

## 目標

在 usage-logs 明細頁內嵌「AI 分析」**基礎摘要**區塊:一眼看完判決結果,涵蓋四種狀態(propose §6)。**本版只做基礎摘要卡,不做三評審逐筆明細**(逐筆細看 → v2.0.4 專頁)。前端串接 stage,含 e2e 視覺驗證(本專案 Playwright 預設停用,e2e 折入本 task 手動驗證)。

## 範圍

- `frontend/src/app/(main)/usage-logs/[uid]/AiAnalysisSection.tsx`(新檔):
  - props 收 `usageLogUid`;以 `apiClient` 打 `endpoints.aiEvaluationByUsageLog(uid)`(獨立 loading/error,不影響 log 本體)。
  - **狀態機**:未評審(`evaluation === null`)/ 評審中(`status==='pending'`)/ 失敗(`status==='error'`)/ 已評審(`status==='evaluated'`),各自對應提示或內容(propose §3 表)。
  - **基礎摘要卡**(已評審時):任務分析(`summary` + intent/complexity `Badge`,用 305 label map)、平均吻合度(`formatFitScore` + 進度條/色階 + min–max)、推薦共識(model+tier `Badge`、`is_split` 標「分歧」+ 票數)、自我偏好警示(`self_vote_count > 0` → 橘色 `Badge`)、完成度(`succeeded_count < judge_count` 標部分成功)。
  - **不渲染** `candidates`(三評審逐筆明細)—— 該資料 API 已回傳,留 v2.0.4 專頁消費;本版可預留「查看完整評審」位置但**不**實作連結。
  - 沿用既有 UI 元件(`Card` / `Badge` / `Skeleton` / `EmptyState`),RWD 對齊 `02-frontend/06-rwd.md`。
- `frontend/src/app/(main)/usage-logs/[uid]/page.tsx`(既有):在既有 metadata 區塊**下方**掛 `<AiAnalysisSection usageLogUid={uid} />`,保持用量詳情精簡。

## Acceptance

- [ ] `[ -f "frontend/src/app/(main)/usage-logs/[uid]/AiAnalysisSection.tsx" ]`
- [ ] 明細頁已掛載:`grep -q "AiAnalysisSection" "frontend/src/app/(main)/usage-logs/[uid]/page.tsx"`
- [ ] 元件處理 `evaluation === null`(未評審)分支:`grep -q "=== null\|evaluation == null\|!.*evaluation" "frontend/src/app/(main)/usage-logs/[uid]/AiAnalysisSection.tsx"`
- [ ] **不渲染逐筆候選**:`! grep -q "ai_recommend_reason" "frontend/src/app/(main)/usage-logs/[uid]/AiAnalysisSection.tsx"`(理由屬逐筆明細,本版不顯示)
- [ ] `cd frontend && npm run build` 成功(Next build 含型別檢查);`npm run lint` 無 warning
- [ ] 手動 e2e(dev 起):開一筆**已評審** log 明細 → 見基礎摘要卡(吻合度/推薦共識/偏差警示);開一筆**未評審** log → 見「尚未評審」提示;確認**無**三評審逐筆明細

## 必讀檔(Just-in-time)

- `AGENTS.md`
- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/02-frontend/00-overview.md`
- `docs/Design-Base/02-frontend/01-routing-and-error.md`
- `docs/Design-Base/02-frontend/02-api-and-state.md`
- `docs/Design-Base/02-frontend/04-datetime.md`
- `docs/Design-Base/02-frontend/05-components.md`
- `docs/Design-Base/02-frontend/06-rwd.md`
- `docs/Design-Base/02-frontend/90-project-frontend.md`
- `docs/Design-Base/02-frontend/91-project-ui-ux.md`
