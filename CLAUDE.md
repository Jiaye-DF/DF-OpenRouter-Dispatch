# CLAUDE.md

Claude Code 特化薄層。**事實層以 [`AGENTS.md`](./AGENTS.md) 為準**(技術棧、Just-in-time Loading、Build/Test/Lint、Code Style、Git、Security、毀滅性操作禁止、規範優先序);本檔僅補 Claude 特性,**不重述** AGENTS.md。

> 本專案 2026-06-25 起採 **Harness-Engineering** spec。規範入口:[`docs/Design-Base/README.md`](./docs/Design-Base/README.md)(任務 → 必讀檔對照表)。

## 規範優先順序

```
docs/Design-Base/* > docs/Arch/* > AGENTS.md / CLAUDE.md > docs/Tasks/*
```

Design-Base 為**不可違反的地板**,版本 `docs/Tasks/*` 的 propose/tasks **不可**凌駕基礎規範;要改規則**先改 Design-Base**。`AGENTS.md` 與本檔同層、內容須一致。

## Just-in-time Loading(Claude 特性)

- 依任務性質載入 `docs/Design-Base/<area>/*.md`(依 `docs/Design-Base/README.md` 對照表 + `AGENTS.md § Just-in-time Loading`);**不必**全資料夾掃描,**不預載**歷史報告。
- 有 sub-agent / skill → `/scan-project`、`/propose-to-tasks`、`/reflect-rules` 可分派(`.claude/commands/*`)。
- 任務中規範被推翻 → 於 commit / task doc 註明,並提醒使用者**先更新 Design-Base** 再續(對齊 `01-propose/07-rule-evolution.md`)。

## 開發前必檢查(env)

1. `.env.example` 存在;`.env` 存在(無則提醒從 `.env.example` 複製)。
2. `.env.example` 所有鍵名已於 `.env` 填值;缺漏逐一列出後暫停。
3. 程式碼用到的環境變數皆已於 `.env.example` 定義;缺漏提醒同步。

> 詳細 env 分層 / 機密規範:`docs/Design-Base/00-overview/02-secrets.md`、`03-env-layers.md`、`00-overview/91-project-naming-env.md`。

## 自訂指令

| 指令 | 說明 |
| --- | --- |
| [`/commit-all`](.claude/commands/commit-all.md) | 一鍵提交並推送當前分支所有變更 |
| [`/merge-main`](.claude/commands/merge-main.md) | 合併當前分支至 `main` |
| [`/scan-project`](.claude/commands/scan-project.md) | 掃描專案結構並分析潛在問題 |
| [`/dev-up`](.claude/commands/dev-up.md) | 一鍵啟動本機開發環境 |
| [`/propose-to-tasks`](.claude/commands/propose-to-tasks.md) | 從 propose 拆出 multi-agent 可並行 tasks |
| [`/reflect-rules`](.claude/commands/reflect-rules.md) | 讀全版本 `fixed.md` 找 pattern → 候選升規 |
