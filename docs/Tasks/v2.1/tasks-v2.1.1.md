# Tasks v2.1.1 · Excel 專案×模型全維度 + 用量記錄下放部門(顯示所屬專案 + 專案篩選)

> 狀態:完成(已完成 4/4)
> 來源:[propose-v2.1.1.md](./propose-v2.1.1.md);母本鏈 [v1.5 依專案/使用者彙總](../v1.5) → 本版
> 並行:4 個 task 中最多 2 並行(批次 B)/ 序列鏈長 3 / 預估總時數:12 hr / 阻塞點:0(propose 已全數定案,僅「版號 v2.1.1 vs v2.2.0」待 user 拍板,不阻塞實作)

## 對齊的 Design-Base 章節

- 拆解:`01-propose/02-task-decomposition.md`、`03-multi-agent-flow.md`
- 後端:`03-backend/01-routing.md`(ApiResponse 外殼)、`02-auth.md`(UserDep / 鎖部門)、`92-project-permission.md § 4`(自身部門用量 ✅ User)、`§ 6`(權限收斂 Dependency,禁散落 if role)
- DB/查詢:`04-databases/05-precision.md`(成本 Numeric)、`09-indexes-and-perf.md`(彙總 GROUP BY 索引)、`02-soft-delete.md`
- 前端:`02-frontend/02-api-and-state.md`、`05-components.md`(Combobox 複用)、`04-datetime.md`(時序 UTC+8)、`92-project-permission.md § 7`(前端顯示規則)
- 第三方:`90-third-party-service/50-openrouter.md § 10`(usage_logs 欄位)
- API docs:`00-overview/04-api-docs.md`

## Definition of Done

- [ ] `GET /api/v1/stats/by-project-model` 於 `/api/docs` 可查;admin 全部 / 非-admin 鎖部門;無資料 `200+[]`
- [ ] `GET /api/v1/usage-logs`(列表)、`/{uid}`(明細)`AdminDep→UserDep`+鎖部門;response 帶專案欄;列表支援 `project_uid` 篩選
- [ ] 下載 Excel 含 7 sheet(總覽/部門/專案/專案×模型/依模型/使用者/時序);成本欄 USD 六位小數
- [ ] 用量記錄前端:列表「專案」欄 + 專案 Combobox 篩選;明細「專案」欄位;`RouteGuard` 放行 `/usage-logs` 給一般使用者
- [ ] 後端單元/整合測試覆蓋(彙總正確 / 鎖部門 / 跨部門 403 / 他部門明細 404 / JOIN 專案欄位)
- [ ] `mypy` / `ruff` / `npm run lint` / `tsc` 零錯誤零 warning
- [ ] 無新增 env、無 migration(本版不動 DB schema)

## 拆解總表

| # | 標題 | 狀態 | 並行 | 依賴 | 影響檔案 |
| --- | --- | --- | --- | --- | --- |
| 420 | 後端:`stats/by-project-model` 端點 + `ProjectModelStatItem` + repo `by_project_model` + 抽共用 `_resolve_filters` | done | ✓ | — | `backend/app/api/v1/stats.py`、`backend/app/api/v1/_scope_filters.py`(新)、`backend/app/schemas/stats.py`、`backend/app/repositories/usage_log.py`、`backend/tests/api/test_stats.py`、`backend/tests/repositories/test_usage_log_stats.py` |
| 421 | 後端:usage-logs 授權放寬 + 部門鎖 + `project_uid` 篩選 + JOIN projects 吐專案欄 + schema | done | ✗ | 420 | `backend/app/api/v1/usage_logs.py`、`backend/app/schemas/usage_log.py`、`backend/app/repositories/usage_log.py`、`backend/tests/api/test_usage_logs.py` |
| 422 | 前端:Excel 補 4 sheet + 儀表板下載串接 + types/endpoints | done | ✓ | 420 | `frontend/src/lib/export/excel.ts`、`frontend/src/app/(main)/dashboard/page.tsx`、`frontend/src/types/api.ts`、`frontend/src/lib/api/endpoints.ts` |
| 423 | 前端:用量記錄 專案欄 + 專案 Combobox 篩選 + 明細專案欄 + RouteGuard/Sidebar 放行 | done | ✗ | 421, 422 | `frontend/src/app/(main)/usage-logs/page.tsx`、`frontend/src/app/(main)/usage-logs/[uid]/page.tsx`、`frontend/src/components/layout/RouteGuard.tsx`、`frontend/src/components/layout/Sidebar.tsx`、`frontend/src/types/api.ts` |

## 執行流程(multi-agent)

- **批次 A(起點,零依賴)**:420(後端 stats;含抽出共用 `_resolve_filters`)。
- **批次 B(420 done 後,可並行)**:421(後端 usage-logs)∥ 422(前端 Excel)。兩者 `affected_files` 無重疊(後端 vs 前端)。
- **批次 C(尾端)**:423(前端用量記錄)— 依 421(後端專案欄/篩選/鎖部門)+ 422(`types/api.ts` 檔鎖)。

> 跨 area 三段鏈:**後端 API → 前端串接**。420→422(Excel 串接)、420→421→423(用量記錄後端→前端)。
> e2e:Playwright 預設停用;查詢端點為認證端點(420/421 pytest 涵蓋);前端視覺與角色可見性折入 422/423 手動驗證。

## 檔案重疊序列化說明

- `backend/app/repositories/usage_log.py`:420(加 `by_project_model` 彙總方法)與 421(改 `list`/`get_by_uid` JOIN projects + `project_uid` 篩選)同檔 → **421 序列於 420 後**(parallel:false)。
- `frontend/src/types/api.ts`:422(加 `StatsByProjectModel`)與 423(usage-log 型別補專案欄)同檔 → **423 序列於 422 後**(檔鎖;423 亦依 421 取後端契約)。
- `backend/app/api/v1/stats.py` 僅 420 動;`_scope_filters.py` 由 420 新建、421 import(構成 421→420 依賴之一)。

## 拆解註記(orchestrator)

- **scope 守門**:4 task 全映自 propose `In Scope`(功能一:後端端點 420 + Excel 422;功能二:後端 421 + 前端 423),無 orphan、無超出 scope。
- **_resolve_filters 抽共用**:propose §B.3「建議抽為共用工具」→ 落為 420 新建 `_scope_filters.py`、stats.py 改 import、421 沿用;避免 usage_logs.py 複製部門鎖邏輯(對齊 `92-project-permission.md § 6` 禁散落)。
- **LEFT vs INNER JOIN**:420 的 `by_project_model` 用 **INNER JOIN**(與既有 `by_project` 一致,NULL 專案不入彙總);421 的 usage-logs list/detail 用 **LEFT JOIN**(保留無專案歷史列,專案欄回 NULL)。
- **版號**:propose 檔首「版號判定註記」已標——嚴格屬 minor(v2.2.0);本批 task 檔案落於 `docs/Tasks/v2.1/`,若 user 改判 v2.2.0 由 user 決定搬移,不阻塞實作。
