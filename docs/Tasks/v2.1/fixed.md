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

## §2 — `mypy` 因共用 `app/core/logging.py` 匯入 `seqlog` 無型別 stub 殘留 1 個錯誤(task-407 acceptance 第四條)

- **時間**:2026-06-26T00:00+08:00
- **commit / PR**:`<pending>`(task-407,orchestrator 統一提交)
- **影響檔案**:`backend/app/core/logging.py:63`(**非** task-407 範圍檔;為 service 必經的共用 logger)
- **問題**:task-407 acceptance 第四條 `mypy app/schemas/ai_model_eval_rerun_result.py app/services/ai_model_eval_rerun_result.py` 要求全綠。實跑回報 1 個錯誤:`app\core\logging.py:63: error: Skipping analyzing "seqlog": module is installed, but missing library stubs or py.typed marker [import-untyped]`。task-407 兩個自身檔(schema / service)本身**無任何** mypy 錯誤;錯誤完全來自 service `from app.core.logging import get_logger` 連帶把共用 `logging.py` 拉進分析。
- **根因**:`seqlog` 套件未提供 `py.typed` / 型別 stub,專案又無 mypy override(`[[tool.mypy.overrides]] ignore_missing_imports`)壓制。任何 import `app.core.logging` 的新檔跑 mypy 都會連坐同一錯;與 §1 同類(既有共用模組的型別債在新 task 驗收上連坐)。已交叉驗證:對既有 v2.0.3 `app/services/ai_model_eval_result.py` 單獨跑 mypy 也回報**完全相同**的 seqlog 錯誤 → 證實為倉庫既有環境債,非 task-407 引入。
- **修正**:task-407 範圍只動三檔,不擅改 `app/core/logging.py` 或 `pyproject.toml`(遵守「禁止碰其他檔案」)。以「自身兩檔 mypy 無錯 + 既有同類 service 觸發相同錯誤」佐證本 task 未引入新型別錯誤。
- **規範參照**:`03-backend/07-testing.md`(acceptance 全綠要求)
- **後續**:reflect 候選 — 於 `pyproject.toml` 加 mypy override `[[tool.mypy.overrides]] module="seqlog.*" ignore_missing_imports=true`(或裝 stub)以根除連坐;應開獨立清債 task 處理,避免每個新檔 acceptance 都受此既有債影響。

## §3 — `AiModelEvaluationRepository` 無「以 `ai_evaluation_uid` 取父評審」getter,task-405 service 須以 ORM `select` 直取父列

- **時間**:2026-06-26T14:30+08:00
- **commit / PR**:`<pending>`(task-405,orchestrator 統一提交)
- **影響檔案**:`backend/app/services/ai_model_eval_rerun.py`(task-405 範圍檔);牽涉 `backend/app/repositories/ai_model_evaluation.py`(**非** task-405 範圍,不可動)
- **問題**:task-405 `rerun_evaluation(ai_evaluation_uid, ...)` 入口須先取父評審拿 `usage_log_uid` / `ai_original_model` / `ai_task_summary`。`AiModelEvaluationRepository` 只提供 `find_by_usage_log_uid`(以 log uid 查)、`find_by_usage_log_uid_including_deleted`、`list_candidates*`、`mark_reran`、`fetch_unreran_evaluation_uids`,**無**任何「以 `ai_evaluation_uid` 取單一父列」的 getter。task-405 範圍鎖死兩檔(service + test),不可在 repository 補方法。`03-backend/00-overview.md` 又明訂「禁 service 直寫 raw SQL」。
- **根因**:task-403 補 v2.1 重跑游標(`fetch_unreran_evaluation_uids` / `mark_reran`)時,只加了「掃 uid 清單」與「以 uid 標旗標」兩個 by-uid 寫入口,**漏補**對應的「以 uid 讀單列」getter;而消費端 task-405 的入口參數恰為 `ai_evaluation_uid`,形成讀取缺口。任務切分時未把「service 需要的 repo 讀取面」與「service 範圍鎖檔」對齊。
- **修正**:於 service 內以 SQLAlchemy 2 ORM `select(AiModelEvaluation).where(ai_evaluation_uid==..., is_deleted==False)` 取單列(**非** raw SQL 字串拼接,無注入風險,對齊 `04-databases/04-sql-safety.md`);沿用 `proxy.py` 既有「service 內 ORM select」先例(`proxy.py:283` `_resolve_model` 同模式)。已於程式內註解標明此處為權宜並 cross-ref 本條。
- **規範參照**:`03-backend/00-overview.md § 分層`(「禁 service 直寫 raw SQL」——此處為 ORM select 非 raw,屬邊界折衷)/ `04-databases/04-sql-safety.md`(已遵守,無字串拼接)
- **後續**:reflect 候選 — (1) 為 `AiModelEvaluationRepository` 補 `find_by_uid(ai_evaluation_uid)`(對齊既有 `find_by_usage_log_uid` 命名),清債 task 完成後把 service 改回走 repository;(2) 任務切分時應把「消費 service 所需的 repository 讀取方法」一併納入上游 repo task 範圍,避免下游 service 被迫在範圍鎖檔下繞道。

## §4 — `mypy app/tasks/ai_model_eval.py` 因連帶分析 repository / seqlog 既有型別債殘留 10 個錯誤(task-406 acceptance 第四條)

- **時間**:2026-06-26T15:30+08:00
- **commit / PR**:`<pending>`(task-406,orchestrator 統一提交)
- **影響檔案**:`backend/app/repositories/usage_log.py`(6 錯)、`backend/app/repositories/model.py`(3 錯)、`backend/app/core/logging.py`(1 錯)——**皆非** task-406 範圍檔
- **問題**:task-406 acceptance 第四條 `mypy app/tasks/ai_model_eval.py` 要求全綠。實跑回報 10 個錯誤,**全數**落在範圍外檔:`usage_log.py` 的 `UsageLogRepository.list` 方法名與 mypy 型別解析衝突(`valid-type`,5 處)+ `Row[Any]` dict comprehension(`misc`)、`model.py` 的 SQLAlchemy 2.x `Result` 無 `rowcount`(`attr-defined`,3 處)、`logging.py` 的 `seqlog` 缺 stub(`import-untyped`)。mypy 結尾明示 `checked 1 source file`,本 task 自身檔 `app/tasks/ai_model_eval.py` **零錯誤**(以 `grep -c "ai_model_eval.py:"` 驗為 0)。
- **根因**:與 §1 / §2 / §3 同類——既有 repository / 共用模組的型別債在新 task 驗收上「連坐」。task-406 為呼叫 task-405 service 新增 `from app.services.ai_model_eval_rerun import rerun_evaluation`,該 service 透傳 `UsageLogRepository` / `ModelRepository` / `app.core.logging`,把既有債拉進 mypy 分析圖;同檔既有的 `evaluate_usage_log_task` / `dispatch_unevaluated` 本就 import 同一批 repository,屬倉庫既有環境債,非本 task 引入。
- **修正**:task-406 範圍只動兩檔(task + test),**不**擅改範圍外 repository / `logging.py` / `pyproject.toml`(遵守「禁止碰其他檔案」)。以「自身檔 mypy 零錯 + 錯誤檔皆為既有債(§1/§2/§3 已記同源)」佐證本 task 未引入新型別錯誤。
- **規範參照**:`03-backend/07-testing.md`(acceptance 全綠要求)/ `04-databases/04-sql-safety.md`(本 task 範圍內無 raw 拼接,worker 短路以 ORM `select` 直取,對齊 §3)
- **後續**:reflect 候選 — 此為跨 v2.1 task(§1/§3/§4)連續第 3 次出現「既有 repository 型別債(`list` 方法名 / `Result.rowcount`)+ `seqlog` 缺 stub 連坐」,已達同類條目升規門檻;建議(1)開獨立清債 task:`UsageLogRepository.list` 改名、`model.py` 改用 `Result.rowcount` 替代寫法、`pyproject.toml` 加 `[[tool.mypy.overrides]] module="seqlog.*" ignore_missing_imports=true`;(2)對「禁碰其他檔案」的 task 把 mypy acceptance 範圍收斂為「僅本 task 變更檔」或建立 mypy baseline。
