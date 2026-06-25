# Workflow v2.0.0 · 模型適配評審【地基:資料表 + 判別模型設定】

> 狀態:已完成(3/3)

## 版本資訊

- 母本 propose:[propose-v2.0.0.md](../propose-v2.0.0.md)
- 範圍:鋪地基——建資料表(`ai_` 前綴)+ 判別模型設定 CRUD + 前端「AI 分析」side-bar。**本版不打任何 LLM/OpenRouter、不導入 taskiq/Redis、不跑評審**。
- 對齊的 Design-Base 章節:
  - DB:[`04-databases/00-overview.md`](../../../Design-Base/04-databases/00-overview.md)(必備欄位)、[`04-databases/01-identifiers.md`](../../../Design-Base/04-databases/01-identifiers.md)(pid/uid)、[`04-databases/08-alembic.md`](../../../Design-Base/04-databases/08-alembic.md)(migration round-trip)、[`04-databases/90-project-database.md`](../../../Design-Base/04-databases/90-project-database.md)(必備欄位/Snowflake)
  - 後端:[`03-backend/01-routing.md`](../../../Design-Base/03-backend/01-routing.md)(ApiResponse 外殼)、[`03-backend/02-auth.md`](../../../Design-Base/03-backend/02-auth.md)(admin 保護)、[`03-backend/92-project-permission.md § 9`](../../../Design-Base/03-backend/92-project-permission.md)(稽核 log)、[`00-overview/04-api-docs.md`](../../../Design-Base/00-overview/04-api-docs.md)(`/api/docs`)
  - 前端:[`02-frontend/01-routing-and-error.md`](../../../Design-Base/02-frontend/01-routing-and-error.md)、[`02-frontend/02-api-and-state.md`](../../../Design-Base/02-frontend/02-api-and-state.md)(RTK Query)、[`02-frontend/05-components.md`](../../../Design-Base/02-frontend/05-components.md)(Combobox reuse)、[`02-frontend/90-project-frontend.md`](../../../Design-Base/02-frontend/90-project-frontend.md)(Sidebar/Card)

## Definition of Done

- [x] 三張新表(`ai_eval_judge_settings` / `ai_model_evaluations` / `ai_model_eval_candidates`)建立,alembic upgrade/downgrade round-trip 通過(對真實 postgres 17 驗證:upgrade → 3 表 + 3 trigger;downgrade -1 全清回 `0018_user_tokens`;再 upgrade 回 head),皆含必備欄位
- [x] `GET` / `PUT /api/v1/ai-eval/judge-settings` 通過 pytest(`tests/api/test_ai_eval.py` 9 passed,含非 3 個 / 重複 / 不存在 / 停用四種 422 + 401/403)
- [x] Swagger 於 `/api/docs` 可查閱新增 `ai-eval` 端點(router 已掛載,兩端點路徑確認)
- [x] 前端「AI 分析 → 設定判別模型」頁可選恰 3 個 active 模型並儲存,重整後保留(進頁 GET 回填,儲存 PUT)
- [x] 既有頁面 / proxy 流程 / 既有 API 行為無迴歸(後端全套 40 passed;前端 lint/tsc/build 綠)
- [x] 無新增環境變數(本版判別模型走 DB 設定;taskiq/Redis 留 v2.0.1)

> 註:migration revision 為 `0019_ai_eval_foundation`(非任務卡初稿的 `0018`,因 `0018_user_tokens` 已存在)。

## 拆解總表

| # | 標題 | 狀態 | 並行 | 依賴 | 影響檔案 |
| --- | --- | --- | --- | --- | --- |
| 001 | 建評審地基三張表 + 模型 + migration(DB) | done | ✓ | — | `backend/app/models/ai_*.py`、`backend/app/models/__init__.py`、`backend/alembic/versions/0019_ai_eval_foundation.py` |
| 002 | 判別模型設定 CRUD API(後端) | done | ✗ | 001 | `backend/app/repositories/ai_eval_judge_setting.py`、`backend/app/schemas/ai_eval.py`、`backend/app/api/v1/ai_eval.py`、`backend/app/api/v1/__init__.py` |
| 003 | 「AI 分析」side-bar +「設定判別模型」頁(前端) | done | ✗ | 002 | `frontend/src/components/layout/Sidebar.tsx`、`frontend/src/app/(main)/ai-analysis/judge-settings/page.tsx`、`frontend/src/lib/api/endpoints.ts`、`frontend/src/types/api.ts`、`frontend/src/lib/api/error-map.ts` |

## 執行流程(multi-agent)

- **線性鏈(跨 area 三段)**:001 DB → 002 後端 API → 003 前端串接。`affected_files` 三段不重疊,但 002 依賴 001 的 model、003 依賴 002 的 API 契約,故 `depends_on` 序列化。
- **並行度**:本版為地基,實質序列;僅 task-001 可立即認領,002/003 待前置 done 解除 blocked。
- **收口**:三 task done 後 orchestrator 跑 `/scan-project` 全域檢測;P0/P1 → 補洞 task;全綠 → `/reflect-rules` → 開 PR。
- e2e(Playwright)本專案預設 disabled([`05-CI/06-e2e.md`](../../../Design-Base/05-CI/06-e2e.md)),本版以 pytest + 前端 build/lint + 手測 case 驗收,不開 e2e job。
