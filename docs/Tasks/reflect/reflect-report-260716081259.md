# Reflect Report — 260716081259

> 產出時間:2026-07-16 08:12:59 (UTC+8)
> 素材:全版本 `fixed.md`(v1.2 / v1.5 / v1.10 / v2.0 / v2.1);**v2.2.0 無 fixed.md**(本版零規範違反 / bug)
> 前次報告:[reflect-report-260707051743.md](./reflect-report-260707051743.md)(候選 1 / 候選 2 皆 ✅ user 2026-07-07)、[reflect-report-260626143642.md](./reflect-report-260626143642.md)(候選 1 / 候選 2 **未見決議標記**)
> 本 skill 只跑三段式 **B 段(反思)**;C 段升級由 user 批准後另開 task(對齊 `01-propose/07-rule-evolution.md`)。

---

## 摘要

- **新增自上次**:v2.1 fixed.md **§11 / §12**(2026-07-14,v2.1.2 收尾;§1~§10 前兩份報告已涵蓋)。v2.2.0 無 fixed.md。
- **本次候選:2 個**(強化 1 / 修正 1),另 **1 個「已決議候選執行追蹤」**與 **2 個觀察項**。
- **與前次關聯**:
  - 前次(260707)候選 1(禁方法名遮蔽 `list`)/ 候選 2(建 `utils/datetime.ts`)**皆 ✅ 採納並落地**;但候選 1 的**方案 B(8 repo 改名清債 task)未執行**,§12(2026-07-14)證明 mypy `list` 遮蔽債仍在 → 列入「執行追蹤」(非新候選)。
  - **前前次(260626)候選 1**(mypy acceptance 範圍 vs 鎖檔 + baseline 機制)**至今未見決議標記**,且 §12 再度明確提名同一規則 → 本報告以**候選 A** 承接強化,建議一併決議。

---

## 候選 A — mypy / lint acceptance 定義收斂為「本 task 變更檔零錯 + 全倉不高於 baseline」+ seqlog override

- **類型**:強化(承接前前次 260626 候選 1,root-cause 由 §12 第 5+ 次復發強化)
- **來源**:fixed.md `v2.1 §1`(`mypy app/repositories/` 整包 20 錯,皆範圍外既有檔)、`v2.1 §2`(`seqlog` 缺 stub 連坐)、`v2.1 §4`(`mypy app/tasks/ai_model_eval.py` 連坐 10 錯)、`v2.1 §7`(worker 明示「第 4 次」)、`v2.1 §12`(2026-07-14,worker 明示「§1/§2/§4/§7/§12 同源第 5+ 次,遠超升規門檻」,並以 `git stash` 比對 baseline 佐證零新增)
- **pattern**:符合判準①「同規則 ≥ 3 次違反」——`03-backend/07-testing.md`(acceptance 全綠要求)被 **5 條** fixed 條目(§1/§2/§4/§7/§12)引用為「無法整包全綠」的根因;跨 v2.1.0 → v2.1.2 兩個 patch。系統性根因:acceptance 把 mypy / lint 範圍訂為整個 package,但同 task 鎖「禁碰其他檔案」,使既有債(`*.list` 方法名遮蔽內建型別、SQLAlchemy 2.x `Result.rowcount`、`seqlog` 無 py.typed)在**每個新檔**驗收上連坐;專案又無 mypy baseline 也無 `seqlog.*` override。**注意**:前次候選 1(✅ 採納)處理的是「**命名規則**(禁新方法名 `list`)」——碼面根因之一;本候選承接的是**驗收定義面**(260626 候選 1 未決),兩者互補而非重複。
- **建議**(落腳 `docs/Design-Base/03-backend/07-testing.md § acceptance / 型別檢查段`,可併行):
  1. **驗收定義**:「對 `affected_files` 鎖檔的 task,mypy / ruff acceptance = **(a) 本 task 變更檔逐檔零錯 + (b) 全倉 `mypy app/` 錯誤數不高於變更前 baseline**(以 `git stash` 或 HEAD 比對);**禁**以『整包 package 全綠』作為鎖檔 task 的驗收條件(既有債不連坐)。」
  2. **baseline / override 基建**(C 段補洞 task,非規則本身):`pyproject.toml` 加 `[[tool.mypy.overrides]] module="seqlog.*" ignore_missing_imports=true` 根除 seqlog 連坐;與候選 1 的清債 task(§12)可併案。
- **影響**:既有 task 檔 acceptance 不回溯改寫(grandfather);規則只規範**該 commit 之後**新拆 task。需同步:`03-backend/07-testing.md`(驗收定義段)、`99-code-review/04-lint-checklist.md`(mypy/ruff gate 改「逐檔 + baseline」語意)、`/propose-to-tasks` 產 task 模板(鎖檔 task → 逐檔 + baseline acceptance,本輪 v2.2.0 拆解已實務採此法,規範化即補上明文)。不破壞 backward。
- **driver**:後端規則 owner(BE lead)/ ruff·mypy 設定 owner

---

## 候選 B — Design-Base 規範先行但基建未落地的系統性缺口(測試 DB;含「承認現況合規層級 or 開基建 task」二擇一)

- **類型**:修正(規範與基建脫節;§11 提供 amend-rule 新角度)
- **來源**:fixed.md `v2.1 §11`(2026-07-14,`03-backend/07-testing.md` 要求「真 DB 整合測試」但專案零測試 DB 基建,v2.1.2 新測試 94 案只能沿既有「repository 替身 + 真 service/驗證鏈」mock 慣例;worker 明示「與 §5/§8『utils/datetime.ts 規範有、基建無』同型」)、`v2.1 §5`(datetime util 規範有基建無,task-410)、`v2.1 §8`(同上復發,task-422)
- **pattern**:符合判準②「同類根因跨 ≥ 2 版本 + 找不到對應規則」——**meta 根因**=「Design-Base 規定某共用基建 / 測試層級存在,但基建 task 從未落地,後續 task 在鎖檔下沿舊慣例繞道」,跨 **v2.1.0(§5 datetime)→ v2.1.1(§8 datetime 復發)→ v2.1.2(§11 測試 DB)** 三條、兩個新領域。datetime 分支已由前次候選 2(✅)建 util 解決;**但測試 DB 分支(§11)為全新領域且無對應規則**,且 §11 提出前兩次未有的**第三條路**:不一定要蓋基建,也可**修訂規範以承認現況**。此角度前次候選 2(只談「建基建 / 納上游範圍」)未涵蓋。
- **建議**(二擇一,C 段拆 task 時定案):
  - **(甲 首選,低成本)** 修訂 `docs/Design-Base/03-backend/07-testing.md`:明文承認「**repository 層以 in-memory 替身 + 真實 service / 驗證鏈 / schema** 為合規測試層級」為現階段地板,並標註「高風險雙表鏈路(token 撤銷、usage_logs 快照)**建議**升級真 DB 整合(testcontainers-postgres),非強制」。消除規範與現況跨多版本的持續落差。
  - **(乙 徹底)** 開基建 task 建立測試 DB fixture(testcontainers-postgres 或 compose 測試庫),把高風險鏈路升為真 DB 整合測試,`07-testing.md` 維持真 DB 地板。
  - **配套規則**(無論甲乙):於 `docs/Design-Base/01-propose/07-rule-evolution.md § 升級規則` 補一條「**規範新增 / re-baseline 要求某基建或測試層級時,須同步(a)開基建落地 task 或(b)於規範明文標註『現況合規層級 + 目標層級』**,避免規範與基建脫節使後續 task 在鎖檔下被迫沿舊慣例(已跨 §5/§8/§11 三度出現)」。
- **影響**:甲案純改規範文字(承認現況),既有測試 grandfather、零 code 變更;乙案為新增測試基建(新增 dev 依賴 + fixture),不動產品碼。配套規則規範未來拆解 / 升規行為,不破壞 backward。需同步:`03-backend/07-testing.md`(測試層級明文)、`01-propose/07-rule-evolution.md`(規範/基建同步條)、`01-propose/02-task-decomposition.md`(與前次候選 2 的「基建納上游範圍」呼應,交叉引用)。
- **driver**:後端規則 owner / 測試基建 owner

---

## 已決議候選執行追蹤(非新候選,提醒 user)

- **前次候選 1(禁 `list` 方法名遮蔽,✅ 採納 2026-07-07)之「方案 B 清債 task」尚未執行**:決議時方案 A(命名規則 + grandfather `builtins.list`)已落 `03-backend/00-overview.md`,方案 B(8 repo 的 `list` 統一改名 + 消費端同步 + 移除 `builtins.list` 權宜)「另開清債 task、不阻塞」。但 `v2.1 §12`(2026-07-14)以 baseline 比對證實 mypy `list` 遮蔽債**仍在**(`proxy.py` / `users.py` 既有錯)。**建議**:本輪收尾把方案 B 清債 task 與候選 A 的 `seqlog` override 併案排入,終止「每個新檔 acceptance 都受既有債連坐 + 每版 fixed 重記一條」的循環(已 §1/§2/§4/§7/§12 五度重記)。

---

## 觀察項(單案,未達 pattern 門檻,列出供 user 知情)

> 依判準「單一 fixed.md 條目不算 pattern」,下列僅 1 次出現,**不**列為正式升規候選;下版再現同類根因即跨門檻正式提。

- **OBS-1 · 共用方法契約變更前須盤點全部消費端**(延續前次 OBS-1)— 來源 `v2.1 §9`(`get_by_uid` 被 3 個 AI 評審 service 直用,task-421 若改其回傳型別會連坐版本邊界,故另立 `get_by_uid_with_project`)。仍為單案(前次即列 OBS-1),v2.1.2 / v2.2.0 無同類再現 → **維持觀察,不升格**。若後續版本再現「改共用方法契約連坐非範圍檔」即與 §9 跨版本達門檻,升為正式候選(落腳 `01-propose/02-task-decomposition.md § 依賴`)。
- **OBS-2 · 部門範圍過濾顯式防守 `department_uid IS NULL`**(前次 OBS-2)— 來源 `v2.1 §10`(已修正,scan AD-001;fixed §10 自提名落腳 `92-project-permission.md § 4`)。前次建議「不經 pattern 門檻直接併入 C 段 task 補 §4 明文」。**待確認**:此 Design-Base §4 明文條款是否已隨前次候選採納一併落地;若尚未,建議本輪一併補上(單案但屬安全地板,成本極低)。

---

## 已巡視、未成候選之判準(證明掃過,寧空勿湊)

- **判準①(同規則 ≥ 3 次)**:命中 1(候選 A,`07-testing.md` 被 §1/§2/§4/§7/§12 引 5 次)。其餘規則(`04-sql-safety.md`、`00-overview § 分層`)各僅 1~2 次,未達。
- **判準②(同類根因跨 ≥ 2 版本 + 無對應規則)**:命中 1(候選 B,規範/基建脫節 §5/§8/§11 跨 v2.1.0→.2)。v2.2.0 無 fixed.md,未新增跨版本根因。
- **判準③(規範矛盾)**:本輪新增 §11/§12 無條目標「規範矛盾」;§11 為「規範 vs 基建落差」(候選 B 處理),非 Design-Base 規則互相衝突。
- **判準④(規則 ≥ 6 個月未違反 → 棄用)**:Design-Base 2026-06-25 re-baseline,所有規則上線 < 2 個月,無棄用門檻基礎。
- **v1.2 / v1.5 fixed.md**:「收尾修正 / enhancement」性質(舊格式,無 `規範參照`/`根因` 結構);v1.5 §04(SDK Key 放棄 AES 改明文)為 user 簽核業務取捨,非規範 pattern。不計入。
- **v2.2.0**:本版 scan 報告(260716075637)零 Critical/High、無 fixed.md,無反思素材。

---

## 決議方式(user 於 PR 逐條標記)

- ✅ 採納 → 開 task 走 C 段升級(改對應 Design-Base 檔 + 同步 checklist + 開清債 task)
- ❌ 拒絕 → 在本報告該候選下記「拒絕原因」(亦為學習素材)
- 🕐 暫緩 → 帶到下次 reflect 重評

---

## 本次結論

**2 個候選 + 1 個執行追蹤 + 2 個觀察項**:
1. **候選 A(強化)** — mypy/lint acceptance 定義收斂為「變更檔零錯 + 全倉不高於 baseline」+ seqlog override(§1/§2/§4/§7/§12 第 5 次,承接 260626 候選 1 未決)。
2. **候選 B(修正)** — 規範/基建脫節系統性缺口:測試 DB(§11)可選「甲=改規範承認現況層級」或「乙=開測試基建 task」+ 配套「規範新增須同步基建」規則(§5/§8/§11 跨版本)。
3. **執行追蹤** — 前次候選 1 已 ✅ 但方案 B 清債 task 未執行,§12 證明債仍在,建議與候選 A 併案排入。
4. **OBS-1 / OBS-2** — 單案觀察;OBS-2 建議確認 §4 明文是否已落地,未落則補。

等 user 於 PR 逐條決議(含前前次 260626 兩候選之最終裁決)。
