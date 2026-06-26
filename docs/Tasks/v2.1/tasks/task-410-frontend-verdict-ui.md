---
id: task-410
title: 摘要層「AI 判決結果」+ 詳細層 inline 對比(AI 分析卡)
status: done
parallel: false
depends_on: [task-408, task-409]
affected_files:
  - frontend/src/app/(main)/usage-logs/[uid]/AiAnalysisSection.tsx
  - frontend/src/app/(main)/usage-logs/[uid]/AiRerunSection.tsx
estimated_hours: 3.5
---

## 目標

在現有 `/usage-logs/[uid]` 的「AI 分析卡」加**摘要層**「AI 判決結果」欄位與**詳細層** inline 展開的「真實重跑對比」(決議 #6:不依賴未建的 v2.0.4,都落在現有卡內),並串接 task-408 查詢 API(propose §6.1 / §6.2)。

## 範圍(propose §6.1 / §6.2)

- 新元件 `AiRerunSection.tsx`(對齊 `AiAnalysisSection.tsx` 自有 loading / error / 狀態機,以 `apiClient` + `API_ENDPOINTS.aiRerunsByUsageLog` 獨立 fetch;重跑缺漏不影響評審本體)。
- **摘要層**(§6.1):AI 分析卡內加「AI 判決結果」欄位,每 usage_log 一筆——緊湊顯示 `原始(原模型) → 模型1 / 模型2 / 模型3 …`(去重後 challenger)+ 每 challenger 裁決 Badge(建議改用 / 維持 / 平手,用 task-409 `winnerLabel`)+ 信心分數(`formatConfidencePercent`);可給彙總結論(如「2/3 建議維持」)。**點開** → 同卡 inline 展開詳細層。
- **詳細層**(§6.2):逐 challenger 列——模型 + tier、真實成本與**成本Δ**(綠=更省 / 紅=更貴)、延遲、裁決 Badge + 信心分數 + 理由、challenger 輸出(可展開)。
- **狀態**:未重跑 / 重跑中 / 重跑失敗 / 已重跑 / **已重跑·未裁決**(子開關關,`compare_*` NULL)。
- 在 `AiAnalysisSection.tsx` 內掛入 `<AiRerunSection>`(propose 指定落點同卡)。

## 實作要點

- 型別 / 端點 / label 一律取自 task-409(`@/types/api`、`@/lib/api/endpoints`、`@/lib/ai-eval-labels`),**禁**重複定義或硬編端點字串。
- 成本Δ 顏色沿用既有 `FIT_BAR_CLASS` 的 emerald/destructive 色階慣例;日期 / 時間用 `utils/datetime`(對齊 `04-datetime.md`)。
- RWD / 觸控目標對齊 `06-rwd.md`;識別碼隱藏(不暴露 UID,對齊 `00-overview.md §32`)。

## Acceptance

- [ ] `cd frontend && npm run type-check` 全綠
- [ ] `cd frontend && npm run lint` 全綠(零 warning)
- [ ] `cd frontend && npm run build` 成功
- [ ] 手動驗證(e2e 折入本 task):admin 進 `/usage-logs/[uid]`,AI 分析卡顯示「AI 判決結果」摘要;點開 inline 展開逐 challenger 成本Δ / 裁決 Badge / 信心分數 / 理由;子開關關閉的列顯示「已重跑·未裁決」;無重跑顯示空狀態(對應 408 `reruns:[]`)

## 必讀檔(Just-in-time)

- `docs/Design-Base/02-frontend/00-overview.md`
- `docs/Design-Base/02-frontend/01-routing-and-error.md`
- `docs/Design-Base/02-frontend/02-api-and-state.md`
- `docs/Design-Base/02-frontend/04-datetime.md`
- `docs/Design-Base/02-frontend/05-components.md`
- `docs/Design-Base/02-frontend/06-rwd.md`
- `docs/Design-Base/02-frontend/90-project-frontend.md`
- `docs/Design-Base/02-frontend/91-project-ui-ux.md`
</content>
