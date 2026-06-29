---
id: task-412
title: AI 判決總覽頁編號(pid)排序 + 搜尋(後端分組端點下推 + 前端工具列;用量紀錄頁移除 pid 搜尋)
status: done
parallel: false
depends_on: [task-408, task-411]
affected_files:
  - backend/app/api/v1/ai_eval_reruns.py
  - backend/app/repositories/ai_model_eval_rerun.py
  - backend/app/services/ai_model_eval_rerun_result.py
  - backend/tests/api/test_ai_eval_reruns.py
  - frontend/src/app/(main)/ai-analysis/verdicts/page.tsx
  - frontend/src/app/(main)/usage-logs/page.tsx
estimated_hours: 2
---

## 目標

承 fixed.md §6(pid 對 admin 外露為「顯示編號 #pid」)後續微調:把「依編號排序 + 編號精確搜尋」的操作落點由**用量紀錄頁**搬到**AI 判決總覽頁**(`/ai-analysis/verdicts`),讓 admin 在詳細比較頁就能直接依用量紀錄編號定位/排序。後端分組總覽端點把 pid 排序/搜尋**下推到查詢層**,total 與當頁一致;用量紀錄頁移除已搬走的 pid 搜尋欄位。**不動 DB**(pid 既有)。

## 範圍與要點

- **後端端點**(`api/v1/ai_eval_reruns.py`):`list_reruns_overview` 加兩個 query 參數——`order`(`^(asc|desc)$`,預設 `desc` 大→小)、`pid`(`int >= 1`,選填,精確比對)。docstring 同步改「排序依用量紀錄編號 pid」。
- **Repository**(`repositories/ai_model_eval_rerun.py`):
  - `list_grouped_by_usage_log` 加 `order` / `pid` 參數。分組鍵查詢改 **LEFT outer join `usage_logs`** 取 `pid`,依 `pid` 排序(`desc` 預設;孤兒組無對應 usage_log → `pid=NULL` 以 `nulls_last()` 排末),`pid` 給值時 `where(UsageLog.pid == pid)` 精確過濾。`group_by` 補 `UsageLog.pid`。
  - `count_distinct_usage_logs` 加 `pid` 參數,有 pid 時 join `usage_logs` 同源過濾,確保 `total` 與當頁清單一致。
- **Service**(`services/ai_model_eval_rerun_result.py`):`build_rerun_overview` 透傳 `order` / `pid` 到 repo 的 `list_grouped_by_usage_log` 與 `count_distinct_usage_logs`。
- **前端 — 判決總覽頁**(`ai-analysis/verdicts/page.tsx`):工具列加「搜尋編號」`Input`(type=number)+「編號 ▼大→小 / ▲小→大」排序切換 `Button`;`order` / `pidSearch` 進 query,改動時 `setPage(1)`;`load` 依賴補 `order` / `pidSearch`。
- **前端 — 用量紀錄頁**(`usage-logs/page.tsx`):移除 `filters.pid` 狀態、query 帶入與「編號」搜尋 Input(保留既有 `order` 排序)。

## Acceptance

- [x] 後端 `pytest tests/api/test_ai_eval_reruns.py` 通過(fake `build_rerun_overview` 簽章已對齊新增 `order="desc", pid=None`)
- [x] `order` 僅接受 `asc|desc`(Query pattern 守門)、`pid` 僅接受 `>=1`;非法值 422
- [x] 有 pid 搜尋時 `total` 與當頁分組清單一致(count 與 list 同源 join)
- [x] 孤兒組(無對應 usage_log)在無 pid 搜尋時仍保留、排末(`nulls_last`)
- [x] 前端 `npm run typecheck` / `npm run lint` / `npm run build` 零錯誤
- [x] 用量紀錄頁不再出現「搜尋編號」欄位;判決總覽頁工具列具編號搜尋 + 排序切換

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/04-databases/04-sql-safety.md`
- `docs/Design-Base/02-frontend/02-api-and-state.md`
- `docs/Design-Base/02-frontend/05-components.md`

## 註記

- 延續 fixed.md §6 的 pid 破例:pid 僅 admin-only 唯讀顯示/排序/搜尋,**非連結、不可導頁**(守判決總覽「禁連回用量紀錄」紅線,決議 #12)。
- 查詢層全走 SQLAlchemy 2 ORM `select` + `outerjoin`(無 raw SQL 拼接,對齊 `04-sql-safety.md`)。
