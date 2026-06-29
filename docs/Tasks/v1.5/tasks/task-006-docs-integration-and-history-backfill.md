---
id: task-006
title: INTEGRATION.md 同步 X-Project-Code + 補齊 v1.3/v1.4 歷史 propose
status: done
parallel: true
depends_on: [task-002]
affected_files:
  - docs/INTEGRATION.md
  - docs/Tasks/v1.3/propose-v1.3.0.md
  - docs/Tasks/v1.4/propose-v1.4.0.md
estimated_hours: 2
---

## 目標
更新對外整合文件加入 `X-Project-Code` header 與兩個新錯誤碼，並追溯補寫 v1.3 / v1.4 母本 propose（依 git log）。

## Acceptance
- [x] `docs/INTEGRATION.md` § 2 加 X-Project-Code 列；§ 4 範例加 header + 錯誤碼說明
- [x] `docs/INTEGRATION.md` § 7 curl/Python 範例加 header；§ 8 加 `project_code_required` / `project_invalid` 兩列
- [x] `docs/Tasks/v1.3/propose-v1.3.0.md` 依 git log 追溯撰寫 DF-SSO 整合
- [x] `docs/Tasks/v1.4/propose-v1.4.0.md` 依 git log 追溯撰寫維護修正集

## 必讀檔(Just-in-time)
- [`00-overview/04-api-docs.md`](../../../Design-Base/00-overview/04-api-docs.md) · [`90-third-party-service/50-openrouter.md`](../../../Design-Base/90-third-party-service/50-openrouter.md) · [`00-overview/00-overview.md`](../../../Design-Base/00-overview/00-overview.md) · [`00-overview/02-secrets.md`](../../../Design-Base/00-overview/02-secrets.md)
