---
id: task-421
title: 後端 usage-logs 授權放寬 + 部門鎖 + project_uid 篩選 + JOIN projects 吐專案欄 + schema
status: pending
parallel: false
depends_on: [task-420]
affected_files:
  - backend/app/api/v1/usage_logs.py
  - backend/app/schemas/usage_log.py
  - backend/app/repositories/usage_log.py
  - backend/tests/api/test_usage_logs.py
estimated_hours: 3
---

## 目標

把用量記錄列表 + 明細由 admin-only 放寬為「非-admin 鎖自身部門」(用量即部門成本),並讓 response 帶「所屬專案」欄、列表支援 `project_uid` 篩選(對齊 propose §B.3、對外承諾)。**不動 DB schema**。

## 範圍與要點

- **授權**:`backend/app/api/v1/usage_logs.py` 列表 `list_usage_logs` 與明細 `get_usage_log` 兩處 `AdminDep` → `UserDep`;引用 task-420 抽出的 `from app.api.v1._scope_filters import resolve_filters`,以 `dept, project, user = resolve_filters(actor, department_uid, project_uid, user_uid)` 取代直接吃參數(非-admin 強制部門、跨部門 403)。**禁**在 router 寫 `if actor.role`(對齊 `92-project-permission.md § 6`)。
- **列表新增 `project_uid` 查詢參數**:endpoint 加 `project_uid: UUID | None = None`;`repositories/usage_log.py` 的 `list()` 補接 `project_uid`(現有 `_apply_filters` 已支援 `project_uid`,傳入即可)。
- **JOIN 專案吐欄**:`list()` 與 `get_by_uid()` **LEFT JOIN** `Project`(保留 `project_uid IS NULL` 的歷史列),select 補 `Project.code` / `Project.name`;回傳結構讓 schema 能取 `project_uid` / `project_code` / `project_name`(NULL 專案三欄皆 None)。
- **schema**:`backend/app/schemas/usage_log.py` 的 `UsageLogListItem` 新增 `project_uid: UUID | None`、`project_code: str | None`、`project_name: str | None`(`UsageLogDetail` 繼承自動帶)。若改 JOIN 後 row 非 ORM 物件,`model_validate` 來源需相應調整(維持 `from_attributes` 或改 dict 組裝,worker 擇一並於測試驗證)。
- **明細越權**:`get_usage_log` 非-admin 取他部門 log → `AppError("not_found", 404)`(不以存在與否側漏,對齊 propose §D.1);admin 不變。
- **稽核**:讀取放寬,不寫稽核 Log。

## Acceptance

- [ ] `uv run pytest backend/tests/api/test_usage_logs.py` 全綠
- [ ] 測試涵蓋:admin 列表/明細行為不變且回傳含專案三欄;非-admin 列表只回自身部門 log;非-admin 帶本部門 `project_uid` → 正確過濾;非-admin 顯式傳他部門 `department_uid` → 403;非-admin 取他部門明細 → 404;歷史 `project_uid IS NULL` 的 log 仍出現在列表且專案三欄為 null
- [ ] pytest 對 OpenAPI 斷言:`/api/v1/usage-logs` GET 具 `project_uid` query 參數;回應 schema 含 `project_code`
- [ ] `grep -n "AdminDep" backend/app/api/v1/usage_logs.py` **零命中**(已全改 UserDep)
- [ ] `grep -nE "if .*\.role|is_admin" backend/app/api/v1/usage_logs.py` **零命中**(權限收斂於 resolve_filters,非散落)
- [ ] `cd backend && uv run mypy app/ && uv run ruff check .` 零錯誤零 warning
- [ ] response 殼為 ApiResponse(`03-backend/01-routing.md`)

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/01-routing.md`
- `docs/Design-Base/03-backend/02-auth.md`
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/03-backend/92-project-permission.md`
- `docs/Design-Base/03-backend/90-project-backend.md`
- `docs/Design-Base/04-databases/02-soft-delete.md`
- `docs/Design-Base/04-databases/09-indexes-and-perf.md`
- `docs/Design-Base/00-overview/04-api-docs.md`
- `docs/Design-Base/90-third-party-service/50-openrouter.md`
