---
id: task-006
title: e2e 整合測試 + Design-Base 文件同步(刪 ALLOWED_MODELS / 加錯誤碼)
status: done
parallel: false
depends_on: [task-004, task-005]
affected_files:
  - backend/tests/test_models_sync.py
  - backend/tests/test_model_tiers_crud.py
  - backend/tests/test_proxy_whitelist_db.py
estimated_hours: 3
---

## 目標
補齊端到端整合測試(同步全鏈路 + throttle + 餘額部分失敗 + 白名單三情境 + tier CRUD),並同步更新 Design-Base 文件:`50-openrouter.md` 白名單描述改 DB 查詢、加 `sync_in_progress`/`sync_throttled`/`tier_in_use` 錯誤碼、移除 `ALLOWED_MODELS` 段;`92-project-permission.md` 加「模型/模型分級/OpenRouter 餘額」資源行並刪 `ALLOWED_MODELS` 行;UI/UX 文件 Sidebar 加兩項。

## Acceptance
- [x] `uv run pytest backend/tests/test_models_sync.py backend/tests/test_model_tiers_crud.py backend/tests/test_proxy_whitelist_db.py -q` 全綠,涵蓋同步全新/更新/下架/rollback、10min throttle、餘額部分失敗 best-effort、白名單三情境、tier 唯一性/tier_in_use/自動匹配優先級
- [x] `grep -rn "ALLOWED_MODELS" docs/Design-Base/` 無命中(各文件 ALLOWED_MODELS 段已刪)
- [x] `grep -rn "sync_in_progress\|sync_throttled\|tier_in_use" docs/Design-Base/90-third-party-service/50-openrouter.md` 三碼皆命中
- [x] `grep -n "模型分級\|OpenRouter 餘額" docs/Design-Base/03-backend/92-project-permission.md` 命中新資源行

## 必讀檔(Just-in-time)
- [`03-backend/07-testing.md`](../../../Design-Base/03-backend/07-testing.md) · [`05-CI/00-overview.md`](../../../Design-Base/05-CI/00-overview.md) · [`05-CI/02-backend-jobs.md`](../../../Design-Base/05-CI/02-backend-jobs.md) · [`05-CI/06-e2e.md`](../../../Design-Base/05-CI/06-e2e.md)
- [`90-third-party-service/50-openrouter.md`](../../../Design-Base/90-third-party-service/50-openrouter.md) · [`90-third-party-service/00-overview.md`](../../../Design-Base/90-third-party-service/00-overview.md)
- [`03-backend/92-project-permission.md`](../../../Design-Base/03-backend/92-project-permission.md) · [`02-frontend/91-project-ui-ux.md`](../../../Design-Base/02-frontend/91-project-ui-ux.md)
