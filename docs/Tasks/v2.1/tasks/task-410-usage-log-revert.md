---
id: task-410
title: usage-log 明細頁回退 v2.0.3(移除內嵌重跑區塊 AiRerunSection)
status: done
parallel: true
depends_on: []
affected_files:
  - frontend/src/app/(main)/usage-logs/[uid]/page.tsx
  - frontend/src/app/(main)/usage-logs/[uid]/AiRerunSection.tsx
estimated_hours: 1
---

## 目標

把 usage-log 明細頁退回 v2.0.3 樣式:移除 v2.1.0 初版加在 AI 分析卡內的 `AiRerunSection`(重跑 / 判決 inline 區塊);重跑對比集中到 AI 判決總覽頁(task-411)。**保留** `AiAnalysisSection`(v2.0.3 評審結果區塊)不動。propose §6.3。

## 範圍與要點

- `frontend/src/app/(main)/usage-logs/[uid]/page.tsx`:
  - 移除 `AiRerunSection` 的 import 與 render(目前頁面只 render `AiAnalysisSection`,確認 `AiRerunSection` 若有引用一併清除;若該頁未實際引用則僅需刪檔 + 確認無殘留 import)。
  - `AiAnalysisSection`(`{uid && <AiAnalysisSection uid={uid} />}`)維持原樣。
- **刪除檔案** `frontend/src/app/(main)/usage-logs/[uid]/AiRerunSection.tsx`。
- 確認全 repo 無其他檔仍 import `AiRerunSection`。

## Acceptance

- [ ] `[ ! -f "frontend/src/app/(main)/usage-logs/[uid]/AiRerunSection.tsx" ]`(檔案已刪)
- [ ] `grep -rn "AiRerunSection" frontend/src` **零命中**(無殘留 import / 引用)
- [ ] `grep -n "AiAnalysisSection" "frontend/src/app/(main)/usage-logs/[uid]/page.tsx"` 命中(評審區塊保留)
- [ ] `npm run typecheck` 與 `npm run lint`(於 frontend/)零錯誤零 warning

## 必讀檔(Just-in-time)

- `docs/Design-Base/02-frontend/00-overview.md`
- `docs/Design-Base/02-frontend/05-components.md`
- `docs/Design-Base/02-frontend/90-project-frontend.md`
