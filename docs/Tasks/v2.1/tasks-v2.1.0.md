# Tasks v2.1.0 · AI 推薦模型「真實重跑 + 對比裁決」

> 狀態:全數完成(401–406 初版 + 407–411 為 2026-06-26 redo,皆 done;待 /scan-project 收口)
> 來源:[propose-v2.1.0.md](./propose-v2.1.0.md);母本鏈 [v2.0.0 地基](../v2.0/propose-v2.0.0.md) → [v2.0.1 判別管線](../v2.0/propose-v2.0.1.md) → [v2.0.3 評審結果顯示](../v2.0/propose-v2.0.3.md)
> 並行:redo 批 5 個 task 中 3 可並行 / 序列 2 / 預估 redo 總時數:12 hr / 阻塞點:0(propose 已全數拍板,視覺形式 §6.2 已定案)

## 重做說明(2026-06-26)

初版 v2.1.0(下表 401–410)實作後,user 評估**前端展示過於陽春、術語難懂**,且詳細比較應集中於專屬 admin 頁。經調整 propose-v2.1.0(移除黑話、前端改獨立「AI 判決總覽」頁、依用量紀錄分組並排真實輸出、禁連回用量紀錄、usage-log 明細頁回退 v2.0.3):

- **不動**:401–406(env + 新表 + migration + repository + 對比裁決 prompt + rerun service + dispatcher)。**DB 一行不改**(真實輸出原文已存於 `response_summary.output_text`)。
- **重做**:407(讀取 schema/service 改分組 + 吐輸出原文)、408(API 收斂單一分組端點 + 移除 by-usage-log)、409(前端分組型別 + 端點收斂)。
- **新拆**:410 改為「usage-log 明細頁回退(移除 AiRerunSection)」、411「AI 判決總覽頁重做」。

## 任務清單

| # | 標題 | 狀態 | 並行 | 依賴 | 影響檔案 |
| --- | --- | --- | --- | --- | --- |
| 401 | env 兩顆開關 + Settings 欄位 | done | ✓ | — | `backend/app/core/config.py`、`.env.example` |
| 402 | 新表 model + 父表游標欄 + migration | done | ✓ | — | `backend/app/models/ai_model_eval_rerun.py`、`backend/app/models/ai_model_evaluation.py`、`backend/app/models/__init__.py`、`backend/alembic/versions/0026_ai_eval_reruns.py` |
| 403 | rerun repository + 父表重跑游標查詢 | done | ✓ | 402 | `backend/app/repositories/ai_model_eval_rerun.py`、`backend/app/repositories/ai_model_evaluation.py`、`backend/tests/repositories/test_ai_model_eval_rerun.py` |
| 404 | AI 對比裁決盲化 prompt + 解析 schema | done | ✓ | — | `backend/app/services/ai_model_eval_rerun_prompt.py`、`backend/app/schemas/ai_model_eval.py`、`backend/tests/services/test_ai_model_eval_rerun_prompt.py` |
| 405 | rerun service(推薦模型串行 → 對比裁決 → 寫一筆) | done | ✓ | 401, 403, 404 | `backend/app/services/ai_model_eval_rerun.py`、`backend/tests/services/test_ai_model_eval_rerun.py` |
| 406 | taskiq task + dispatcher(`dispatch_unrerun` / `rerun_evaluation_task`) | done | ✓ | 403, 405 | `backend/app/tasks/ai_model_eval.py`、`backend/tests/tasks/test_ai_model_eval_rerun_dispatch.py` |
| 407 | 重跑結果「依用量紀錄分組」讀取 schema + service(+ 分組分頁 repo 查詢) | done | ✓ | — | `backend/app/schemas/ai_model_eval_rerun_result.py`、`backend/app/services/ai_model_eval_rerun_result.py`、`backend/app/repositories/ai_model_eval_rerun.py`、`backend/tests/services/test_ai_model_eval_rerun_result.py`、`backend/tests/repositories/test_ai_model_eval_rerun.py` |
| 408 | 查詢 API 收斂為單一分組總覽端點 + 移除 by-usage-log | done | ✗ | 407 | `backend/app/api/v1/ai_eval_reruns.py`、`backend/tests/api/test_ai_eval_reruns.py` |
| 409 | 前端「分組」型別 + 端點常數收斂 + 裁決 label/util | done | ✓ | 407 | `frontend/src/types/api.ts`、`frontend/src/lib/api/endpoints.ts`、`frontend/src/lib/ai-eval-labels.ts` |
| 410 | usage-log 明細頁回退 v2.0.3(移除 AiRerunSection) | done | ✓ | — | `frontend/src/app/(main)/usage-logs/[uid]/page.tsx`、`frontend/src/app/(main)/usage-logs/[uid]/AiRerunSection.tsx`(刪) |
| 411 | AI 判決總覽頁重做(分組 + 原 vs 推薦1/2/3 真實輸出並排 + 統計) | done | ✗ | 408, 409 | `frontend/src/app/(main)/ai-analysis/verdicts/page.tsx` |

## 並行批次(redo)

- **批次 A(可同時認領,零依賴)**:407(後端讀取層)、410(前端回退,獨立)。
- **批次 B**:408(待 407)、409(待 407)— 後端 API 與前端型別檔不重疊,可並行。
- **批次 C**:411(待 408+409)— 前端總覽頁串接 + 視覺驗證。

> 跨 area 依賴鏈:**後端讀取(407)→ 後端 API(408)/ 前端型別(409)→ 前端總覽頁(411)**;410 與全鏈獨立可隨時做。
> e2e:Playwright 預設停用,查詢端點為 admin 認證(408 pytest 涵蓋);總覽頁視覺驗證折入 411 手動驗證。

## 檔案零重疊驗證(redo 批)

- 407(backend schema/service/repo/tests)、408(backend api + api test)、409(frontend types/endpoints/labels)、410(frontend usage-logs page + AiRerunSection)、411(frontend verdicts page)——`affected_files` **互不重疊**,序列化純由 `depends_on` 驅動。
- 407 與 403 共用 `repositories/ai_model_eval_rerun.py` 與 `tests/repositories/test_ai_model_eval_rerun.py`:403 已 done(非活躍),407 加分組分頁查詢方法不互鎖。

## 已決議(2026-06-26,user 拍板;對齊 propose §「設計取捨 / 已決議」#1–#14)

worker 不必再問 user,重點摘錄影響 redo 批者:

- **移除黑話**(#9):challenger→AI 推薦模型、discriminator/GAN→對比裁決、champion→原模型。影響 407/408/409 docstring 與註解。
- **前端落點改獨立 admin 頁**(#10):`/ai-analysis/verdicts`「AI 判決總覽」即詳細頁;移除 usage-log 明細卡內 `AiRerunSection`,該頁回退 v2.0.3。影響 410/411。
- **總覽頁依用量紀錄分組**(#11):並排原模型 vs 推薦模型1/2/3 **真實輸出原文**。影響 407/409/411。
- **禁連回用量紀錄**(#12):總覽頁不得有跳轉 `/usage-logs/*` 連結。影響 411。
- **DB 不動**(#13):輸出原文已存 `response_summary.output_text`,只改 schema 對外吐欄 + API + 前端。影響 407。
- **API 收斂**(#14):移除 by-usage-log 端點與舊扁平 schema,讀取全走分組總覽端點(帶輸出原文 + stats)。影響 407/408/409。
- **視覺形式定案**(propose §6.2,user 授權 agent 決策):頁頂統計列 + 分組可展開 Card + 並排欄位(原模型欄 + 推薦模型欄)+ RWD 堆疊。影響 411。

## 拆解註記(orchestrator)

- **scope 守門**:redo 批 5 task 皆映自 propose `In Scope`(唯讀查詢 API / 前端展示 / usage-log 回退),無 orphan、無超出 scope 偷渡。
- **407 取原模型輸出**:`original_output_text` 取自 `usage_logs.response_summary.output_text`,read service 以既有 usage_log repository 純讀補上(rerun 列僅 denormalize `original_model`/`original_cost_usd`,未存原輸出原文)。
- **407 分組分頁**:以 distinct `usage_log_uid`(最新 `triggered_at` 優先)為分頁單位,`total`=分組組數;同 usage_log 的多推薦模型併同組。
- **411 視覺**:形式已於 propose §6.2 定案,worker 直接實作,不需再問 user。
- **舊 task 檔**:初版 407(rerun-result-schema-service)、410(frontend-verdict-ui)slug 檔已刪除,以新 slug 取代,保持「一號一檔」。
