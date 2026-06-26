# fixed — v2.1.0 規範違反 / bug 根因累積

> 格式見 `docs/Design-Base/01-propose/04-fixed-format.md`。Agent 寫,user 不主動寫。

## §1 — `mypy app/repositories/` 因既有檔案殘留 20 個型別錯誤,task-403 acceptance 第三條無法整包全綠

- **時間**:2026-06-26T00:00+08:00
- **commit / PR**:`<pending>`(task-403,orchestrator 統一提交)
- **影響檔案**:`backend/app/repositories/user.py`、`sdk_api_key.py`、`openrouter_key.py`、`internal_key.py`、`api_key_request.py`、`usage_log.py`、`model.py`(**皆非** task-403 範圍檔)
- **問題**:task-403 acceptance 要求 `mypy app/repositories/`(整包)全綠。實跑回報 7 個既有檔共 20 個錯誤(例:`UserRepository.list` 方法名與 mypy 對 `list` 型別解析衝突 → `valid-type`;`Result.rowcount` `attr-defined`;`api_key_request` 的 `ColumnElement[bool]` vs `BinaryExpression[bool]` `arg-type`)。task-403 自身兩檔(`ai_model_eval_rerun.py`、`ai_model_evaluation.py`)單獨跑 mypy **全綠**(`Success: no issues found in 2 source files`)。
- **根因**:這些錯誤在 task-403 動工前即存在於工作樹(`git status` 證實該 7 檔皆未被 task-403 修改),屬倉庫既有型別債,非本 task 引入;acceptance 把檢查範圍訂成整個 `app/repositories/` 套件,使既有債務在新 task 的驗收上「連坐」。常見根因類型:repository 把方法命名為 `list`(與內建型別同名,mypy 在型別位置誤解析)、SQLAlchemy 2.x `Result` 不再有 `rowcount`、`where()` 條件型別標註過窄。
- **修正**:task-403 範圍只動三檔,**不**擅自修改範圍外 7 檔(遵守 task「禁止碰其他檔案」)。以「task-403 自身兩檔 mypy 全綠」佐證本 task 未引入新型別錯誤;整包殘留錯誤留待專責清債 task 處理。
- **規範參照**:`03-backend/07-testing.md`(acceptance 全綠要求)/ `04-databases/04-sql-safety.md`(本 task 範圍內已遵守,無 raw 拼接)
- **後續**:reflect 候選 — (1) 既有 repository 型別債應開獨立 task 清理(優先 `Result.rowcount` 與 `list` 方法命名);(2) 建議 acceptance 的 mypy 範圍對「禁碰其他檔案」的 task 應收斂為「僅本 task 變更檔」,避免既有債連坐,或先建立 mypy baseline。
