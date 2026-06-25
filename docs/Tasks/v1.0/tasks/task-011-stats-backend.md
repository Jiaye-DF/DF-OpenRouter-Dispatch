---
id: task-011
title: 儀錶板彙總端點後端(overview / by-department / by-model / timeseries)
status: done
parallel: false
depends_on: [task-008]
affected_files:
  - backend/app/api/v1/stats.py
  - backend/app/services/stats/
  - backend/app/schemas/stats.py
  - backend/tests/api/test_stats.py
estimated_hours: 3
---

## 目標

依 propose § 6.1 實作 4 個彙總端點:`/stats/overview`(總請求 / tokens / 金額)、`/stats/by-department`、`/stats/by-model`、`/stats/timeseries`(`granularity=hour|day`);查詢以 `usage_logs`(task-008)聚合;`from` / `to` 時間範圍過濾。可見性:一般 `user` 僅彙總自身部門(service 層以 `actor.department_uid` 注入 WHERE),admin 不限。

## Acceptance

- [x] `uv run pytest tests/api/test_stats.py` 全綠
- [x] 4 端點皆回 `ApiResponse` 殼;`granularity=hour|day` 皆可用(斷言)
- [x] user 角色 `by-department` 僅含自部門列(跨部門被過濾,測試斷言)
- [x] 彙總走索引(`idx_usage_logs_dept_time` 等),`from`/`to` 區間過濾正確(斷言)

## 必讀檔(Just-in-time)

- [`03-backend/01-routing.md`](../../../Design-Base/03-backend/01-routing.md) · [`92-project-permission.md`](../../../Design-Base/03-backend/92-project-permission.md)
- [`04-databases/09-indexes-and-perf.md`](../../../Design-Base/04-databases/09-indexes-and-perf.md) · [`10-statistics-log.md`](../../../Design-Base/04-databases/10-statistics-log.md)
