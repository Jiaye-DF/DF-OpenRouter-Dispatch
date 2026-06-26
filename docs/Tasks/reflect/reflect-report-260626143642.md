# reflect-report-260626143642

> 三段式之 **B 段(反思期)**。本報告只產候選,不改 `docs/Design-Base/*`(C 段由 user 批准後另開 task,對齊 `01-propose/07-rule-evolution.md`)。
> 素材:全版本 `fixed.md`(v1.2 / v1.5 / v1.10 / v2.0 / v2.1)。歷史 reflect 報告:**無**(本次為首次 reflect)。
> 掃描日期:2026-06-26 14:36 (UTC+8)。

---

## 摘要

- **候選 2 個**:強化 1 / 新增 1 / 修正 0 / 棄用 0。
- 候選 1 達 pattern 判準 1(同規則 `03-backend/07-testing.md` ≥ 3 次違反),且 fixed.md v2.1 §4 worker 已自評「達升規門檻」。
- 候選 2 為**門檻邊界**(同類根因 2 條、同版本),低於「跨 ≥ 2 版本」嚴格門檻,但兩條 fixed 條目皆**主動提名**同一 reflect 候選 → 列出供 user 決議(可早採 ✅ 或暫緩 🕐 帶下次重評)。
- v1.2 / v1.5 fixed.md 為「收尾修正 / enhancement」性質(無 `規範參照` / `根因` 結構),不構成規則違反 pattern,僅作背景。

---

## 候選 1 — mypy acceptance 範圍與「禁碰其他檔案」鎖檔衝突,既有型別債在新 task 驗收連坐

- **類型**:強化
- **來源**:fixed.md `v2.1 §1`(`mypy app/repositories/` 整包 20 錯,皆範圍外既有檔)、`v2.1 §2`(`seqlog` 缺 stub 連坐 1 錯)、`v2.1 §4`(`mypy app/tasks/ai_model_eval.py` 連帶分析 repository/seqlog 10 錯,worker 明示「跨 §1/§3/§4 連續第 3 次,已達升規門檻」)
- **pattern**:同一規則 `03-backend/07-testing.md`(acceptance 全綠要求)被 **3 條** fixed 條目引用為「無法整包全綠」的根因 → 滿足判準 1(同規則 ≥ 3 次違反)。系統性根因有二:(a) acceptance 把 mypy 範圍訂為**整個 package**(`mypy app/<pkg>/`),但同 task 又鎖「禁碰其他檔案」,使既有債(`UsageLogRepository.list` 等方法名與 mypy 型別位置解析衝突、SQLAlchemy 2.x `Result.rowcount` `attr-defined`、`seqlog` 無 `py.typed`)在**每個新檔**驗收上連坐;(b) 專案無 mypy baseline 也無 `seqlog.*` override 壓制連坐。三條皆已佐證「本 task 自身檔 mypy 全綠」,即新碼未引入新債。
- **建議**:落腳 `docs/Design-Base/03-backend/07-testing.md`(acceptance / 型別檢查段)。具體規則文字(擇一或併行):
  1. **範圍收斂**:「對 `affected_files` 鎖檔(『禁碰其他檔案』)的 task,mypy / ruff acceptance **僅**針對該 task 變更檔(逐檔列出),不得訂為整個 package;整包檢查留給全域 `/scan-project` 收口或專責清債 task。」
  2. **baseline 機制**:「專案應建立 mypy baseline(或於 `pyproject.toml` 加 `[[tool.mypy.overrides]]` 壓制第三方無 stub 套件如 `seqlog.*`),使新 task 的型別 acceptance 只反映新碼,不受存量債連坐。」
  - 連帶(C 段補洞 task,非規則):`pyproject.toml` 加 `module="seqlog.*" ignore_missing_imports=true`;`UsageLogRepository.list` / 其他 `*.list` 方法改名(避免與 `list` 型別位置衝突);`model.py` 改用 `Result.rowcount` 的等價寫法。
- **影響**:
  - **既有 code 合規性**:既有 task 檔的 acceptance 不回溯改寫(grandfather);新規則只規範**該 commit 之後**新拆的 task。
  - **backward**:不破壞;純驗收範圍與工具設定收斂。
  - **需補檔 / 同步 checklist**:改 `03-backend/07-testing.md`(加範圍/baseline 條);若 `99-code-review/*` 有 mypy gate checklist 須同步「逐檔 vs 整包」語意;`/propose-to-tasks` 產 task 時套用「鎖檔 task → 逐檔 acceptance」模板。另開清債 task 處理 `pyproject.toml` override + 既有 repository 型別債。
- **driver**:後端規則 owner(BE lead);reviewer 由 user 指派。

---

## 候選 2 — 任務拆解未把「下游 task 所需的上游方法 / 共用基建」納入上游範圍,逼下游在鎖檔下繞道

- **類型**:新增
- **來源**:fixed.md `v2.1 §3`(`AiModelEvaluationRepository` 缺 `find_by_uid(ai_evaluation_uid)` getter;task-405 service 入口參數正是 `ai_evaluation_uid`,範圍鎖檔下只能以 ORM `select` 權宜直取父列)、`v2.1 §5`(`02-frontend/04-datetime.md` 規定的共用 `utils/datetime.ts` 從未被任何前版 task 落地;首個需日期顯示的前端 task-410 範圍鎖檔下只能就地實作 `formatDateTime`)
- **pattern**:**同類根因 2 條**——拆解時未把「下游 task 消費所需的上游產物(repository 讀取方法 / 共用 util 基建)」納入上游 task 的 `affected_files`,導致下游在「禁碰其他檔案」下被迫繞道(ORM select / 就地實作),產生待清債的權宜碼。**門檻說明**:目前 2 條皆 v2.1 同版本,**未達**判準 2 的「跨 ≥ 2 版本」嚴格門檻;但兩條 fixed 條目的「後續」欄**皆主動提名**此 reflect 候選,根因高度同質,先行列出供 user 決議。
- **建議**:落腳 `docs/Design-Base/01-propose/02-task-decomposition.md`(拆解完整性段)。具體規則文字:「拆解 task 時,orchestrator 須對每個 task 反查其**消費端依賴**:(a) service/任務 task 若以某識別碼為入口,對應 repository 的『以該識別碼讀取』方法須存在或納入上游 repo task 的 `affected_files`;(b) 凡涉及 Design-Base 強制的共用基建(如 `utils/datetime.ts` 的 `formatDateTime`),若該基建尚未落地,須**先**建立基建 task(或併入首個消費 task 的範圍),不得讓下游在鎖檔下就地重實作。」同步在 `03-multi-agent-flow.md § 衝突偵測` 註記「鎖檔不可截斷下游必需的上游讀取面」。
- **影響**:
  - **既有 code 合規性**:v2.1 §3 / §5 的權宜碼(service ORM select、`AiRerunSection.tsx` 就地 `formatDateTime`)grandfather 保留,待清債 task 收斂(補 repo `find_by_uid`、建 `utils/datetime.ts` 並把就地版 + 既有 `usage-logs/[uid]/page.tsx:195` `toLocaleString()` 一併改走共用)。
  - **backward**:不破壞;規範未來拆解行為。
  - **需補檔 / 同步 checklist**:改 `01-propose/02-task-decomposition.md`;`/propose-to-tasks` skill 加「消費端依賴反查」步驟;開 2 個清債 task(repo getter / 共用 datetime util)。
- **driver**:orchestrator / 規則 owner;reviewer 由 user 指派。

---

## 已巡視但未成候選的判準(寧空勿湊,證明跑過)

| 判準 | 結果 | 說明 |
| --- | --- | --- |
| 判準 1：同規則 ≥ 3 次違反 | 命中 1(候選 1) | `03-backend/07-testing.md` 被 v2.1 §1/§2/§4 引用 3 次 → 候選 1。其餘規則(`04-sql-safety.md`、`00-overview § 分層`)各僅 1 次,未達。 |
| 判準 2：同類根因跨 ≥ 2 版本且無對應規則 | 邊界 1(候選 2) | 「拆解漏納下游依賴」根因 2 條但**同版本(v2.1)**,嚴格未達跨版本門檻;因兩條主動提名故列出供決議。其餘根因(判別神棍 v2.0 §1、temperature v2.0 §2、FIFO 餓死 v2.0 §3)皆單條且已於該版修正,非跨版本 pattern。 |
| 判準 3：規範彼此矛盾(fixed 標「規範矛盾」) | 無 | 全版本 fixed.md 無任一條根因標記「規範矛盾」。v2.0 §1 的「盲化推翻」屬 **propose 層設計推翻**(propose-v2.0.1 §5),已於該版更新,非 Design-Base 規則互相衝突。 |
| 判準 4：規則 ≥ 6 個月未違反(棄用) | 無 | 專案 HE spec 於 2026-06-25 才 re-baseline,所有規則上線 < 6 個月,無棄用判斷基礎。 |
| 背景：v1.2 / v1.5 fixed.md | 不計入 | 屬「收尾修正 / enhancement」紀錄,無 `規範參照`/`根因` 結構(舊格式),非規則違反素材;v1.5 §04(SDK Key 放棄 AES 改明文)為 user 簽核之業務取捨,非規範 pattern。 |

---

## 收口

**2 個候選,等 user 在 PR 上逐條決議**:
- ✅ 採納 → 開 task 走 C 段升級(改對應 Design-Base 檔 + 同步 checklist + 開清債 task)
- ❌ 拒絕 → 在本報告該候選下記「拒絕原因」(亦為學習素材)
- 🕐 暫緩 → 帶到下次 reflect 重評(候選 2 若本次暫緩,下版若再現同類根因即跨版本達門檻)

> 建議優先序:**候選 1 優先**(已達判準 1 + worker 自評達門檻,且清債 task 影響 5 條 fixed §1–§4 的連坐);**候選 2** 視 user 對「拆解完整性是否值得入規」之取捨,或暫緩待下版確認跨版本再現。
