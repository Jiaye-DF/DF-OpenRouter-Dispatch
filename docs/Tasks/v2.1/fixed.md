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

## §5 — `04-datetime.md` 規定的共用 `utils/datetime.ts`(`formatDateTime`)尚未建立,task-410 範圍鎖檔下只能於元件內就地實作

- **時間**:2026-06-26T16:30+08:00
- **commit / PR**:`<pending>`(task-410,orchestrator 統一提交)
- **影響檔案**:`frontend/src/lib/utils/datetime.ts`(**不存在**,應為共用日期 util 落點);`frontend/src/app/(main)/usage-logs/[uid]/AiRerunSection.tsx`(task-410 範圍檔,就地實作 `formatDateTime`);旁證既有違規 `frontend/src/app/(main)/usage-logs/[uid]/page.tsx:195`(用被禁的 `new Date(...).toLocaleString()`)
- **問題**:`02-frontend/04-datetime.md` 與 `05-components.md` 明訂日期格式化**必**走共用 `utils/datetime.ts` 的 `formatDateTime`,**禁**各頁自寫、**禁** `new Date(...).toLocaleString()`。但專案內 `frontend/src/lib/utils/` 僅有 `cn.ts` / `format.ts`,**無** `datetime.ts`(`grep formatDateTime` 全倉零命中)。task-410 需顯示 `RerunResult.triggered_at`,範圍鎖死兩檔(`AiRerunSection.tsx` + `AiAnalysisSection.tsx`),不可新建 `utils/datetime.ts`。
- **根因**:Design-Base 規定的共用日期 util 從未被任何前一版 task 落地建立(基建缺口);v2.1 任務切分時未把「建立 `utils/datetime.ts`」納入任一 task,使首個需要日期顯示的前端 task(410)在範圍鎖檔下無共用可用。另現網 `usage-logs/[uid]/page.tsx` 早已以被禁的 `toLocaleString()` 顯示時間,屬既有未稽出的違規。
- **修正**:於 `AiRerunSection.tsx` 內就地實作與 `04-datetime.md` 範例**逐字一致**的正規表示式版 `formatDateTime`(切 ISO 字串、**不**用 `new Date` / `toLocaleString` / `timeZone`),符合時區策略地板;已於程式註解標明此為權宜並 cross-ref 本條,待後續抽出共用 util。
- **規範參照**:`02-frontend/04-datetime.md`(共用入口 + 禁 `toLocaleString`)/ `02-frontend/05-components.md § 必抽`(日期格式化必走 `formatDateTime`)
- **後續**:reflect 候選 — (1) 開基建 task 建立 `frontend/src/lib/utils/datetime.ts` 匯出 `formatDateTime`,再把 `AiRerunSection.tsx` 就地版與 `usage-logs/[uid]/page.tsx:195` 的 `toLocaleString()` 一併改走共用;(2) 任務切分時,凡涉日期顯示的前端 task 應先確認共用 util 已存在,否則把建立 util 納入上游範圍。

## §6 — pid 對 admin 外露當「顯示編號(#pid)」,破「ID 隱藏 / pid 內部」慣例(user 拍板)

- **時間**:2026-06-26T18:30+08:00
- **commit / PR**:`<pending>`(v2.1 redo 增補,統一提交)
- **影響檔案**:`backend/app/schemas/usage_log.py`(`UsageLogListItem.pid`)、`backend/app/schemas/ai_model_eval_rerun_result.py`(`RerunUsageLogInfo.pid`)、`frontend/src/types/api.ts`、`frontend/src/app/(main)/usage-logs/page.tsx`(列表「編號」欄)、`frontend/src/app/(main)/usage-logs/[uid]/page.tsx`(明細「編號」)、`frontend/src/app/(main)/ai-analysis/verdicts/page.tsx`(收合列 + Dialog 基礎資訊)
- **問題**:user 要「用量紀錄」與「AI 判決總覽」兩頁能以同一編號互相對應。判決總覽明訂**禁連回用量紀錄**(決議 #12),且 user 反對顯示 `usage_log_uid`(UUID 串難讀)。需要一個跨兩頁穩定、唯一、人類可讀的對應號。
- **根因**:既有識別策略(`04-databases/01-identifiers.md`:pid 內部 / uid 對外;`02-frontend/00-overview.md`:ID 隱藏)沒有「admin 端人類可讀參考號」這一類;uid 對外但不可讀,pid 可讀但屬內部。無第三種號可用且不想開 migration 加流水號欄。
- **修正**:**刻意破例**——把既有 `pid`(穩定、唯一、遞增)對 **admin-only** 外露為「顯示編號 #pid」,兩頁共用。僅唯讀顯示,不作為連結 / 不可導頁(守判決總覽紅線);非 admin 端不暴露。schema 與型別均加註此為刻意破例並指向本條。**不動 DB**(pid 既有)。
- **規範參照**:`04-databases/01-identifiers.md`(pid 內部 / uid 對外)、`02-frontend/00-overview.md`(ID 隱藏)
- **後續**:reflect 候選 — 於 Design-Base `01-identifiers.md` / `02-frontend/00-overview.md` 補「admin 端可用 pid 作唯讀人類可讀參考號(非連結、非對外公開端點)」的明文例外,把本次破例升為正式規則;否則日後 review 易誤判為違規。

## §7 — `UsageLogRepository.list` 方法名遮蔽內建 `list`,新增 `by_project_model` 若沿用 `-> list[...]` 標註即觸 mypy `valid-type` + 連坐 stats 端點(task-420)

- **時間**:2026-07-07T00:00+08:00
- **commit / PR**:`<pending>`(task-420,orchestrator 統一提交)
- **影響檔案**:`backend/app/repositories/usage_log.py`(`UsageLogRepository.list` 方法名遮蔽內建 `list`;task-420 新增 `by_project_model`)、連坐 `backend/app/api/v1/stats.py`(6 個彙總端點 `for r in rows` 迭代)
- **問題**:task-420 acceptance 要求 `mypy app/` 零錯誤。`UsageLogRepository` 內有 `def list(...)` 方法,在 class scope 遮蔽內建 `list`,使同 class 內所有 `-> list[tuple[...]]` 回傳標註被 mypy 解析成「方法 `list` 當型別」→ `valid-type` 錯(既有 `by_department`/`by_model`/`by_project`/`by_user`/`timeseries` 5 法皆已中招,屬 §1/§2/§4 同源既有債);且回傳型別解析失敗會退化為 `list?`,連帶讓 `stats.py` 各端點 `for r in rows` 報 `has no attribute "__iter__"`。若新方法 `by_project_model` 直接沿用 `-> list[...]`,會**再新增 2 個**同類錯誤(repo 標註 + stats 端點迭代)。實測基線 HEAD = 47 錯,沿用寫法 = 49 錯。
- **根因**:同 §1/§2/§4——`UsageLogRepository.list` 方法名與內建 `list` 型別衝突的既有型別債從未清理;`from __future__ import annotations` 亦無法解(mypy 仍以 class scope 解析標註名)。task-420 範圍可動 `usage_log.py`,但清整個 class 的 `list` 遮蔽(改名 method / 全面改標註)超出本 task scope 且牽動 task-421 共用同檔。
- **修正**:task-420 新方法 `by_project_model` 的回傳標註改用 `builtins.list[tuple[...]]`(顯式繞過 class scope 的 `list` 遮蔽),使該方法 + 其消費端 `by_project_model_endpoint` **零新增 mypy 錯**;`mypy app/` 總數維持基線 47(未引入新錯)。既有 5 個 sibling 方法/端點的既有錯不在本 task scope,不擅改。已於 import `builtins` 沿用此意圖。
- **規範參照**:`03-backend/07-testing.md`(acceptance 全綠要求)/ `04-databases/04-sql-safety.md`(本 task 無 raw 拼接,純 ORM)
- **後續**:reflect 候選 — 此為跨 §1/§2/§4/§7 第 4 次記載「`UsageLogRepository.list` 方法名遮蔽內建 `list`」;已遠超同類升規門檻。建議開獨立清債 task:把 `list` 方法改名(如 `list_paged` / `paginate`),全 class 回傳標註即可回歸 `list[...]`、`stats.py` 連坐錯一併消,並移除本 task 的 `builtins.list` 權宜。task-421 亦動同檔,清債後兩者受惠。

## §8 — 共用 `utils/datetime.ts`(`formatDateTime`)仍未建立,task-422 時序 sheet 時間格式化只能於 `excel.ts` 就地實作(§5 同源復發)

- **時間**:2026-07-07T00:00+08:00
- **commit / PR**:`<pending>`(task-422,orchestrator 統一提交)
- **影響檔案**:`frontend/src/lib/utils/datetime.ts`(**仍不存在**,應為共用日期 util 落點);`frontend/src/lib/export/excel.ts`(task-422 範圍檔,就地實作 `formatBucketTaipei`)
- **問題**:task-422 / propose §C.1 明訂時序 sheet「時間 (UTC+8)」欄「時間以既有 `utils/datetime` 格式化(對齊 `02-frontend/04-datetime.md`)」。但 `frontend/src/lib/utils/` 至今仍僅 `cn.ts` / `format.ts`,**無** `datetime.ts`(`grep formatDateTime` 全倉零命中);§5(task-410)記載的基建缺口尚未被任何 task 補齊。task-422 範圍鎖死四檔(`excel.ts` / `dashboard/page.tsx` / `types/api.ts` / `endpoints.ts`),**不可**新建 `utils/datetime.ts`。
- **根因**:與 §5 完全同源——Design-Base `04-datetime.md` 規定的共用日期 util 從未落地;v2.1.1 任務切分再次未把「建立 `utils/datetime.ts`」納入任一 task,使需要時間顯示的 task-422 在範圍鎖檔下無共用可用。時序 bucket 為後端以 Asia/Taipei 切出的 naive wall-clock 字串,若丟 `new Date()` 會二次偏移(`04-datetime.md` 明禁)。
- **修正**:於 `excel.ts` 內就地實作與 `04-datetime.md` 範例**逐字一致**的正規表示式版 `formatBucketTaipei`(切 ISO 字串、**不**用 `new Date` / `toLocaleString` / `timeZone`),符合時區策略地板;已於程式註解標明此為權宜並 cross-ref `04-datetime.md`,待共用 util 落地後改走共用入口。
- **規範參照**:`02-frontend/04-datetime.md`(共用入口 + 禁 `toLocaleString` / `new Date`)/ `02-frontend/05-components.md § 必抽`(日期格式化必走 `formatDateTime`)
- **後續**:reflect 候選 — 此為跨 §5(task-410)/§8(task-422)第 2 次記載「共用 `utils/datetime.ts` 缺口迫使前端 task 就地實作日期格式化」。**強烈建議**立即開基建 task 建立 `frontend/src/lib/utils/datetime.ts` 匯出 `formatDateTime`,再把 §5 的 `AiRerunSection.tsx`、本次 `excel.ts` 的就地版、以及 `usage-logs/[uid]/page.tsx:195` 的 `toLocaleString()` 一併改走共用;並於任務切分時,凡涉日期顯示的前端 task 先確認共用 util 已存在,否則把建立 util 納入上游範圍。

## §9 — `UsageLogRepository.get_by_uid` 被 AI 評審管線共用,task-421 不可改其回傳型別,另立 `get_by_uid_with_project` 帶專案欄

- **時間**:2026-07-07T00:00+08:00
- **commit / PR**:`<pending>`(task-421,orchestrator 統一提交)
- **影響檔案**:`backend/app/repositories/usage_log.py`(task-421 範圍檔);牽涉 `backend/app/services/ai_model_eval.py`、`ai_model_eval_rerun.py`、`ai_model_eval_rerun_result.py`(**非** task-421 範圍,不可動;AI 評審管線)
- **問題**:task-421 規格要求「`list()` 與 `get_by_uid()` 改 LEFT JOIN projects、select 補 `Project.code` / `Project.name`」以吐專案欄。但 `get_by_uid(uid) -> UsageLog | None` 同時被 3 個 AI 評審 service 以 `usage_log: UsageLog | None = await usage_repo.get_by_uid(...)` 直用(屬性存取);若把其回傳改為 `tuple[UsageLog, str|None, str|None]` 會:(a) 觸這 3 檔新增 mypy `assignment` 錯 + 執行期屬性存取爆炸;(b) 連坐 AI 評審管線——而 propose-v2.1.1 開宗明義「本版**不**涉及 AI 評審管線」。`list()` 則僅 `usage_logs.py` 單一消費端,可安全改型別。
- **根因**:`get_by_uid` 是跨功能共用的單列讀取入口(用量明細 + AI 評審取源共用),task 規格未察其被 AI 評審鏈消費,逕要求改其回傳型別,與「不涉評審管線」的版本邊界相衝突。
- **修正**:`list()` 依規格改 LEFT JOIN 回傳 `builtins.list[tuple[UsageLog, str|None, str|None]]`(僅 `usage_logs.py` 消費,無連坐);`get_by_uid` **維持原型別不動**,另立 `get_by_uid_with_project(uid) -> tuple[UsageLog, str|None, str|None] | None`(LEFT JOIN 版)供明細端點 `get_usage_log` 使用。達成規格意圖(明細帶專案三欄、保留 NULL 專案列)且零連坐 AI 評審管線。已於新方法 docstring 標明並 cross-ref 本條。回傳標註沿用 §7 的 `builtins.list` 繞過 class scope `list` 遮蔽。`mypy app/` 對 3 個範圍檔零新增錯(基線 6 個既有 `usage_log.py` 錯僅行號位移)。
- **規範參照**:`03-backend/00-overview.md § 分層`(repository 封裝查詢)/ `03-backend/07-testing.md`(acceptance 全綠;既有債不連坐)
- **後續**:reflect 候選 — (1) 若日後要統一,清債 task 可把 `get_by_uid` 與 `get_by_uid_with_project` 收斂(或讓 AI 評審 service 改用 `[0]` 解包),但須與「評審管線不隨用量 task 動」的版本邊界一併評估;(2) 任務切分時,凡要求改「共用 repository 讀取方法」回傳型別者,應先盤點其全部消費端,避免跨功能連坐。
