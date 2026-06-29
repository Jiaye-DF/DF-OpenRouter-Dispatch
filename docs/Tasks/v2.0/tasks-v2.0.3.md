# Tasks v2.0.3 · 評審結果顯示(usage-log 明細頁內嵌「AI 分析」區塊)

> 狀態:已完成(6/6;批次1–4 全數完成,後端 35 測通過、前端 type-check/lint/build 全綠)
> 來源:[propose-v2.0.3.md](./propose-v2.0.3.md);母本 [v2.0.1 判別管線](./propose-v2.0.1.md)(評審管線已落地,結果僅存 DB)
> 並行:2 / 序列:4 / 預估總時數:13 hr

| # | 標題 | 狀態 | 並行 | 依賴 | 影響檔案 |
| --- | --- | --- | --- | --- | --- |
| 301 | 評審結果 Response schema | done | ✓ | — | `backend/app/schemas/ai_model_eval_result.py` |
| 302 | repository — 取候選並 join 判別模型(key/name) | done | ✓ | — | `backend/app/repositories/ai_model_evaluation.py`、`backend/tests/repositories/test_ai_model_evaluation.py` |
| 303 | 彙總 service(三評審 → 單一判決) | done | ✗ | 301, 302 | `backend/app/services/ai_model_eval_result.py`、`backend/tests/services/test_ai_model_eval_result.py` |
| 304 | 評審結果 API endpoint + router 註冊 | done | ✗ | 303 | `backend/app/api/v1/ai_eval_results.py`、`backend/app/api/v1/__init__.py`、`backend/tests/api/test_ai_eval_results.py` |
| 305 | 前端型別 + 端點常數 + 中文對照/格式 util | done | ✗ | 301 | `frontend/src/types/api.ts`、`frontend/src/lib/api/endpoints.ts`、`frontend/src/lib/ai-eval-labels.ts` |
| 306 | AI 分析基礎摘要區塊 + usage-log 明細頁內嵌 | done | ✗ | 304, 305 | `frontend/src/app/(main)/usage-logs/[uid]/AiAnalysisSection.tsx`、`frontend/src/app/(main)/usage-logs/[uid]/page.tsx` |

## 並行批次

- **批次 1(可同時認領)**:301、302(`affected_files` 互不重疊、無依賴)
- **批次 2**:303(待 301+302)、305(待 301)— 兩者檔案不重疊,可並行
- **批次 3**:304(待 303)
- **批次 4**:306(待 304+305)— 前端串接 + e2e 視覺驗證(折入本 task,見下)

> 跨 area 依賴鏈:**後端 API(301→302→303→304)→ 前端串接(305→306)→ e2e**。e2e 因本專案 Playwright 預設停用、且端點為 admin 認證(已由 304 pytest API 測涵蓋),視覺 e2e 折入 306 手動驗證,不另立 no-op task。

## 已決議(2026-06-26,user 拍板;propose §8 + §9 變更紀錄)

> propose §8 六項待確認已全數拍板,無待解阻塞點,worker 可直接開工:

1. **權限**:**admin-only**(未來才開放 User)。影響 304。
2. **細看專頁**:側欄「AI 分析」下獨立專頁細看三評審 → **順延 v2.0.4**(本版 Out of Scope)。
3. **API 落點**:**新檔 `ai_eval_results.py`**(與 judge-settings 的 `ai_eval.py` 區隔)。影響 304。
4. **intent/complexity 中文對照**:**前端 label map**(`ai-eval-labels.ts`)。影響 305。
5. **「分歧」閾值**:**無嚴格過半即分歧** → `is_split = (top_votes*2 <= succeeded) and succeeded>1`(2:1→不分歧、1:1:1→分歧)。影響 303。
6. **無評審回應**:**`200 + data.evaluation=null`**(非 404)。影響 303/304。

## 拆解註記(orchestrator)

- **範圍縮減(2026-06-26)**:usage 詳情頁只做**基礎摘要卡**,**移除可展開三評審逐筆明細**;逐筆細看改做獨立「AI 分析」專頁順延 v2.0.4。**僅 task-306 縮範圍(3.5→2.5 hr)**;後端 301–305 不變(API 仍回完整 `candidates` 供 v2.0.4 重用)。
- **版號 slot**:v2.0.3 = 評審結果顯示(基礎摘要);細看專頁 v2.0.4、真實重跑 v2.0.5、人類裁決 v2.0.6、儀表板 v2.0.7(見 propose 開頭)。
- **migration**:本版**無 migration**(純唯讀 API + 前端展示,不動 schema)。
- **檔案零重疊**:6 個 task 的 `affected_files` 互不重疊,序列化純由 `depends_on` 驅動(非同檔互鎖);批次 2 內 303/305 可真並行。
- **e2e 折入 306**:理由見「並行批次」註。
