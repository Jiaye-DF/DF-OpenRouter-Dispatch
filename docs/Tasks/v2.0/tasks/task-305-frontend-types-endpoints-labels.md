---
id: task-305
title: 前端型別 + 端點常數 + 中文對照/格式 util
status: pending
parallel: false
depends_on: [task-301]
affected_files:
  - frontend/src/types/api.ts
  - frontend/src/lib/api/endpoints.ts
  - frontend/src/lib/ai-eval-labels.ts
estimated_hours: 1.5
---

## 目標

前端資料層:鏡像後端評審結果 schema 的型別、新增端點常數、提供 intent/complexity 中文對照與 fit_score 格式 util,供 306 元件取用(propose §6.3)。

## 範圍

- `frontend/src/types/api.ts`(既有):新增 `EvaluationResult` / `EvaluationSummary` / `RecommendConsensus` / `EvalCandidate` / `TaskAnalysis` 介面,對齊 task-301 schema;**Decimal 欄位(`*_fit_score`)為 `string | null`**;外層取用型別 `EvaluationResultEnvelope { evaluation: EvaluationResult | null }`。
- `frontend/src/lib/api/endpoints.ts`(既有):新增 `aiEvaluationByUsageLog: (uid: string) => \`/api/v1/ai-eval/evaluations/by-usage-log/${uid}\``。
- `frontend/src/lib/ai-eval-labels.ts`(新檔):
  - `INTENT_LABELS` / `COMPLEXITY_LABELS`:枚舉值 → 中文(枚舉以後端 `schemas/ai_model_eval.py` 的 `TaskIntent` / `TaskComplexity` 為準);查無對應回原值(fallback)。
  - `formatFitScore(score: string | null): string`:Decimal 字串 → 百分比顯示(null → `—`)。

## Acceptance

- [ ] `[ -f frontend/src/lib/ai-eval-labels.ts ]`
- [ ] 端點常數已加:`grep -q "aiEvaluationByUsageLog" frontend/src/lib/api/endpoints.ts`
- [ ] 型別已加:`grep -q "EvaluationResult" frontend/src/types/api.ts && grep -q "EvalCandidate" frontend/src/types/api.ts`
- [ ] label/util 已加:`grep -q "INTENT_LABELS" frontend/src/lib/ai-eval-labels.ts && grep -q "formatFitScore" frontend/src/lib/ai-eval-labels.ts`
- [ ] `cd frontend && npx tsc --noEmit` green;`npm run lint` 無 warning

## 必讀檔(Just-in-time)

- `AGENTS.md`
- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/02-frontend/00-overview.md`
- `docs/Design-Base/02-frontend/02-api-and-state.md`
- `docs/Design-Base/02-frontend/05-components.md`
- `docs/Design-Base/02-frontend/90-project-frontend.md`
