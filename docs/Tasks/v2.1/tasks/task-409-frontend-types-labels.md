---
id: task-409
title: 前端型別 + 端點常數 + 裁決 label/util
status: pending
parallel: true
depends_on: [task-407]
affected_files:
  - frontend/src/types/api.ts
  - frontend/src/lib/api/endpoints.ts
  - frontend/src/lib/ai-eval-labels.ts
estimated_hours: 2
---

## 目標

對映後端重跑結果 schema(task-407)的前端型別、端點常數,與裁決 Badge / 信心分數的中文 label 與格式 util,集中以利 reuse(propose §6.2、決議 #6)。

## 範圍(propose §6,對齊 v2.0.3 task-305 慣例)

- `types/api.ts`:新增 `RerunResult` / `RerunListResponse`,逐欄對應 task-407 schema(金額 / 分數欄為 `string | null`,對齊既有 `EvalCandidate` 的 `ai_fit_score: string | null`)。
- `lib/api/endpoints.ts`:在 `aiEvaluationByUsageLog` 後加 `aiRerunsByUsageLog: (uid: string) => `/api/v1/ai-eval/reruns/by-usage-log/${uid}``。
- `lib/ai-eval-labels.ts`(集中既有 AI 分析 label,**reuse 不另開檔**):
  - `WINNER_LABELS`:`compare_winner`(original / challenger / tie)→ 中文 Badge label(維持原模型 / 建議改用 / 平手)+ `winnerLabel(v)` fallback 不爆。
  - `formatConfidencePercent(score: string | null)`:信心分數 0–1 → 百分比字串(對齊既有 `formatFitPercent`;null/解析失敗 → `"—"`)。
  - 可選 `winnerTone(v)`:供 410 決定 Badge 顏色。

## 實作要點

- 全檔純函式、TS strict、無副作用(對齊 `ai-eval-labels.ts` 現況)。
- 枚舉與後端同步(後端傳原始字串,中文對照前端維護);fallback 回原值不爆。

## Acceptance

- [ ] `cd frontend && npm run type-check`(或 `tsc --noEmit`)全綠
- [ ] `cd frontend && npm run lint` 全綠(零 warning)
- [ ] `grep -q "aiRerunsByUsageLog" frontend/src/lib/api/endpoints.ts && grep -q "RerunResult" frontend/src/types/api.ts && grep -q "winnerLabel" frontend/src/lib/ai-eval-labels.ts`(三檔皆落地)

## 必讀檔(Just-in-time)

- `docs/Design-Base/02-frontend/00-overview.md`
- `docs/Design-Base/02-frontend/02-api-and-state.md`
- `docs/Design-Base/02-frontend/05-components.md`
- `docs/Design-Base/02-frontend/90-project-frontend.md`
</content>
