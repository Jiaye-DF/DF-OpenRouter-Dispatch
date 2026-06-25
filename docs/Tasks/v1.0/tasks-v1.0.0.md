# Tasks v1.0.0

> 狀態:已完成(12/12)
>
> 母本 propose:[`propose-v1.0.0.md`](./propose-v1.0.0.md)(MVP 設計推導與決議過程)。
> 細節檔:[`tasks/task-NNN-*.md`](./tasks/);本檔為總清單,內容若與細節檔衝突,以細節檔為準。

## 拆解摘要

- 共 **12** 個 task;並行 **7**(001 / 002 / 003 / 004 / 005 / 006 / 008)、序列 **5**(007 / 009 / 010 / 011 / 012)。
- 跨 area 三段鏈:後端代理(007 雙因子 + 009 client)→ 代理端點(010)→ 前端串接(012)。
- 阻塞點:**010 SDK 代理端點**(收斂 007 + 009);**012 前端整合**(收斂 002 + 004/005/006 + 011)。

## 清單

| # | 標題 | 狀態 | 並行 | 依賴 | 影響檔案(摘) |
| --- | --- | --- | --- | --- | --- |
| [001](./tasks/task-001-backend-skeleton-core.md) | 後端骨架 + 核心模組(config / response / exceptions / crypto)+ compose | done | ✓ | — | `backend/app/core/*`、`docker-compose*.yml` |
| [002](./tasks/task-002-frontend-skeleton.md) | 前端骨架(Next.js + API client + auth store + 登入頁) | done | ✓ | — | `frontend/src/{lib/api,store,components/layout}/*` |
| [003](./tasks/task-003-auth-users-backend.md) | 登入系統後端(login / refresh / logout / me / 改密 + admin 建使用者,V1) | done | ✓ | 001 | `migrations/V1__*`、`api/v1/{auth,users}.py` |
| [004](./tasks/task-004-organization-backend.md) | 組織結構後端(departments / projects CRUD + V2) | done | ✓ | 001 | `migrations/V2__*`、`api/v1/{departments,projects}.py` |
| [005](./tasks/task-005-openrouter-keys-backend.md) | OpenRouter Key 管理後端(AES-256-GCM + CRUD + V3) | done | ✓ | 001 | `migrations/V3__*`、`api/v1/openrouter_keys.py` |
| [006](./tasks/task-006-sdk-keys-backend.md) | SDK Key 管理後端(argon2id + prefix 查詢 + V4) | done | ✓ | 001 | `migrations/V4__*`、`api/v1/sdk_keys.py` |
| [007](./tasks/task-007-user-tokens-sdk-auth.md) | User Token 簽發 / 撤銷 + SDK 雙因子驗證 Dependency(V5) | done | ✗ | 003, 006 | `migrations/V5__*`、`core/sdk_auth.py`、`api/v1/user_tokens.py` |
| [008](./tasks/task-008-usage-logs-backend.md) | 用量紀錄後端(usage_logs 背景寫入 + 查詢 + V6) | done | ✓ | 001 | `migrations/V6__*`、`api/v1/usage_logs.py` |
| [009](./tasks/task-009-openrouter-client.md) | OpenRouter client(httpx wrapper + Key 選擇 / failover) | done | ✗ | 005 | `backend/app/clients/openrouter/*` |
| [010](./tasks/task-010-proxy-endpoint-openrouter-client.md) | SDK 代理端點 + OpenRouter client 整合(改寫 / key 選擇 / failover) | done | ✗ | 007, 009 | `api/v1/model_openrouter.py`、`services/proxy/*` |
| [011](./tasks/task-011-stats-backend.md) | 儀錶板彙總端點後端(overview / by-department / by-model / timeseries) | done | ✗ | 008 | `api/v1/stats.py`、`services/stats/*` |
| [012](./tasks/task-012-frontend-admin-pages.md) | 前端管理頁 + 儀錶板(各列表頁 + dashboard 圖表) | done | ✗ | 002, 004, 005, 006, 011 | `frontend/src/app/(main)/*`、`components/feature/stats/*` |
