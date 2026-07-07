---
id: task-debt-001
title: 清債 — repository `list` 方法改名 `list_page`,根治 mypy `list` 遮蔽連坐
status: pending
parallel: false
depends_on: []
affected_files:
  - backend/app/repositories/api_key_request.py
  - backend/app/repositories/department.py
  - backend/app/repositories/internal_key.py
  - backend/app/repositories/openrouter_key.py
  - backend/app/repositories/project.py
  - backend/app/repositories/sdk_api_key.py
  - backend/app/repositories/usage_log.py
  - backend/app/repositories/user.py
  - (連帶)所有呼叫 `.list(` 的 api/service/tests 消費端
estimated_hours: 4
---

## 來源

reflect-report-260707051743 候選 1(✅ 採納,方案 B);fixed.md v2.1 §1 / §4 / §7(`list` 遮蔽內建型別致 mypy `valid-type` 假錯,第 4 次)。C 段規則已於 `03-backend/00-overview.md` 落地(方案 A);本 task 為方案 B 徹底清債。

## 目標

把 8 個 repository 的 `async def list(...)` 統一改名 `list_page(...)`,消除 class scope 對內建 `list` 的遮蔽,使全 class 回傳標註回歸裸 `list[...]`(移除 §7 的 `builtins.list[...]` 迴避),根治 mypy 連坐。

## 範圍與要點

- 逐 repo 改名 `list` → `list_page`;同步全部呼叫端(`grep -rn "\.list(" backend/app backend/tests`)。
- 改名後把該 class 內 `builtins.list[...]` 回歸 `list[...]`。
- **禁**改動查詢邏輯 / 回傳結構(純改名 + 標註回歸),行為零變化。

## Acceptance

- [ ] `grep -rnE "def list\(" backend/app/repositories/` **零命中**(全改名)
- [ ] `grep -rn "builtins.list" backend/app/repositories/` 零命中(標註已回歸)
- [ ] `cd backend && uv run mypy app/repositories/ app/api/` 相關 `valid-type` / `__iter__` 假錯**歸零**(對照 fixed.md §7 列的錯)
- [ ] `cd backend && uv run pytest` 全綠(行為未變)
- [ ] `cd backend && uv run ruff check .` 零新增錯

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`(命名 / 型別段,本 task 的規則來源)
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Tasks/v2.1/fixed.md`(§1 / §4 / §7)
