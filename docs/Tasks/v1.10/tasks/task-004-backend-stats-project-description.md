---
id: task-004
title: 後端 stats by-project 帶出專案描述供 Excel 備註欄
status: done
parallel: true
depends_on: []
affected_files:
  - app/repositories/usage_log.py
  - app/schemas/stats.py
  - app/api/v1/stats.py
---

## 目標
儀表板內部 stats `by-project` 端點回傳資料補上專案描述,供 Excel 匯出「專案」sheet 新增「備註」欄使用。

## Acceptance
- [x] `repositories/usage_log.py` `by_project`:`SELECT` / `GROUP BY` 加入 `Project.description`,回傳 tuple 補一格。
- [x] `schemas/stats.py`:`ProjectStatItem` 加 `project_description: str | None`。
- [x] `api/v1/stats.py` `by-project`:mapping 帶入 `project_description=r[3]`(後續索引順移)。
- [x] 範圍為儀表板內部 stats 端點,非對外 SDK API;不動 INTEGRATION.md / 使用者文件,Swagger 自動帶出新欄位。
- [x] 後端 `py_compile` 通過(`usage_log.py` / `schemas/stats.py` / `api/v1/stats.py`)。

## 必讀檔(Just-in-time)
- [`04-databases/10-statistics-log.md`](../../../Design-Base/04-databases/10-statistics-log.md) · usage_log 統計聚合 GROUP BY
- [`03-backend/01-routing.md`](../../../Design-Base/03-backend/01-routing.md) · stats 端點 mapping
- [`00-overview/04-api-docs.md`](../../../Design-Base/00-overview/04-api-docs.md) · Schema 新欄位與 Swagger 同步
