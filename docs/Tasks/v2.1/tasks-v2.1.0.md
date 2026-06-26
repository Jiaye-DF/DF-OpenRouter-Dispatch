# Tasks v2.1.0 · 推薦模型「真實重跑 + 對比裁決」(champion / challenger,GAN 閉環)

> 狀態:未開始(已完成 0/10)
> 來源:[propose-v2.1.0.md](./propose-v2.1.0.md);母本鏈 [v2.0.0 地基](../v2.0/propose-v2.0.0.md) → [v2.0.1 判別管線](../v2.0/propose-v2.0.1.md) → [v2.0.3 評審結果顯示](../v2.0/propose-v2.0.3.md)
> 並行:5 / 序列:5 / 預估總時數:27 hr / 阻塞點:0(propose §10 已全數拍板,worker 可直接開工)

| # | 標題 | 狀態 | 並行 | 依賴 | 影響檔案 |
| --- | --- | --- | --- | --- | --- |
| 401 | env 兩顆開關 + Settings 欄位 | pending | ✓ | — | `backend/app/core/config.py`、`.env.example` |
| 402 | 新表 model + 父表游標欄 + migration | pending | ✓ | — | `backend/app/models/ai_model_eval_rerun.py`、`backend/app/models/ai_model_evaluation.py`、`backend/app/models/__init__.py`、`backend/alembic/versions/0026_ai_eval_reruns.py` |
| 403 | rerun repository + 父表重跑游標查詢 | pending | ✓ | 402 | `backend/app/repositories/ai_model_eval_rerun.py`、`backend/app/repositories/ai_model_evaluation.py`、`backend/tests/repositories/test_ai_model_eval_rerun.py` |
| 404 | AI discriminator 盲化對比 prompt + 解析 schema | pending | ✓ | — | `backend/app/services/ai_model_eval_rerun_prompt.py`、`backend/app/schemas/ai_model_eval.py`、`backend/tests/services/test_ai_model_eval_rerun_prompt.py` |
| 405 | rerun service(challenger 串行 → discriminator → 寫一筆) | pending | ✓ | 401, 403, 404 | `backend/app/services/ai_model_eval_rerun.py`、`backend/tests/services/test_ai_model_eval_rerun.py` |
| 406 | taskiq task + dispatcher(`dispatch_unrerun` / `rerun_evaluation_task`) | pending | ✓ | 403, 405 | `backend/app/tasks/ai_model_eval.py`、`backend/tests/tasks/test_ai_model_eval_rerun_dispatch.py` |
| 407 | 重跑結果 Response schema + 讀取 service | pending | ✓ | 403 | `backend/app/schemas/ai_model_eval_rerun_result.py`、`backend/app/services/ai_model_eval_rerun_result.py`、`backend/tests/services/test_ai_model_eval_rerun_result.py` |
| 408 | 查詢 API endpoint + router 註冊 | pending | ✗ | 407 | `backend/app/api/v1/ai_eval_reruns.py`、`backend/app/api/v1/__init__.py`、`backend/tests/api/test_ai_eval_reruns.py` |
| 409 | 前端型別 + 端點常數 + 裁決 label/util | pending | ✓ | 407 | `frontend/src/types/api.ts`、`frontend/src/lib/api/endpoints.ts`、`frontend/src/lib/ai-eval-labels.ts` |
| 410 | 摘要層「AI 判決結果」+ 詳細層 inline 對比(AI 分析卡) | pending | ✗ | 408, 409 | `frontend/src/app/(main)/usage-logs/[uid]/AiAnalysisSection.tsx`、`frontend/src/app/(main)/usage-logs/[uid]/AiRerunSection.tsx` |

## 並行批次

- **批次 1(可同時認領,零依賴)**:401、402、404(三者 `affected_files` 互不重疊)
- **批次 2**:403(待 402;repo 需 model)
- **批次 3**:405(待 401+403+404)、407(待 403)— 檔案不重疊,可並行
- **批次 4**:406(待 403+405)、408(待 407)、409(待 407)— 三者檔案不重疊,可並行
- **批次 5**:410(待 408+409)— 前端串接 + e2e 視覺驗證(折入本 task,見下)

> 跨 area 依賴鏈:**後端管線(401/402→403→404→405→406)→ 後端讀取 API(407→408)→ 前端串接(409→410)→ e2e**。
> e2e:本專案 Playwright 預設停用、查詢端點為 admin 認證(已由 408 pytest API 測涵蓋),視覺 e2e 折入 410 手動驗證,不另立 no-op task。

## 已決議(2026-06-26,user 拍板;propose §10「全數拍板,無待確認項」)

對齊 propose §10 決議表,worker 不必再問 user:

1. **不導入每日成本閘**(`AI_RERUN_DAILY_BUDGET_USD` 取消);控管靠總開關預設關 + 去重 + 維持原模型跳過。影響 401、405。
2. discriminator = **推薦該 challenger 的評審模型本人**(自我裁決,非固定單一裁判);去重取代表者。影響 404、405。
3. **不加**抽樣門檻 / 吻合度門檻(初版,先靠總開關控成本)。影響 406。
4. 去重:三裁判推薦同 challenger → 合併一筆,`ai_candidate_uid` 取代表者。影響 402、405。
5. PII 再送:**沿用 v2.0.1 不遮罩**現況(保留 mask hook)。影響 404、405。
6. 前端落點:**不依賴未建的 v2.0.4**;摘要 + 詳細(inline)都落在現有 `/usage-logs/[uid]` AI 分析卡;原 v2.0.4 slot 取消。影響 409、410。
7. discriminator **盲化**:不揭露兩側模型名,只比輸出 A/B(避免自我偏好偏差)。影響 404。
8. **不新增** batch / interval env;`dispatch_unrerun` 沿用 `dispatch_unevaluated` 排程與批量常數。影響 401、406。
9. 版號定案 **v2.1.0**(新表+新 endpoint=minor,規則強制);原 v2.0.4 細看專頁併入本版 §6。

## 拆解註記(orchestrator)

- **scope 守門**:全 10 task 皆映自 propose `In Scope` 七條目,無 orphan、無超出 scope 的偷渡功能。
- **檔案零重疊可並行**:10 個 task 的 `affected_files` 互不重疊,序列化純由 `depends_on` 驅動。共享檔(`models/__init__.py`、`api/v1/__init__.py`)各只由單一 task(402 / 408)觸碰,不互鎖。
- **discriminator schema 落點**:對比裁決解析模型 `DiscriminatorOutput` 與既有 `JudgeOutput` 同屬「判別模型回覆解析」語意,故併入 `backend/app/schemas/ai_model_eval.py`(task-404);唯讀對外展示 schema 另開 `ai_model_eval_rerun_result.py`(task-407),讀寫分檔對齊 v2.0.3。
- **taskiq 落點**:`dispatch_unrerun` / `rerun_evaluation_task` 加進既有 `backend/app/tasks/ai_model_eval.py`(沿用 beat 排程與批量常數,決議 #8);`scheduler.py` 已 import 該模組,新 schedule label 自動被 `LabelScheduleSource` 撈到,**無需動 scheduler.py**。
- **cost 算法**:challenger `cost_usd` 沿用 proxy 既有計費(取回應 `usage.cost`/`total_cost`,對齊 `services/proxy.py`);無原成本時 `cost_delta` 留 NULL(propose §9 風險)。
- **migration 編號**:現有最新 `0025`,本版新 migration 為 `0026_ai_eval_reruns`(新表 + 父表兩欄游標,單一 migration)。
- **e2e 折入 410**:理由見「並行批次」註。
</content>
</invoke>
