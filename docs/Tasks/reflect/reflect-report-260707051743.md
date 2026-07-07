# Reflect Report — 260707051743

> 產出時間:2026-07-07 05:17:43 (UTC+8)
> 素材:全版本 `fixed.md`(v1.2 / v1.5 / v1.10 / v2.0 / v2.1)
> 前次報告:[reflect-report-260626143642.md](./reflect-report-260626143642.md)(候選 1 / 候選 2,**尚未見 user 決議標記**)
> 本 skill 只跑三段式 **B 段(反思)**;C 段升級由 user 批准後另開 task(對齊 `01-propose/07-rule-evolution.md`)。

---

## 摘要

- **新增自上次**:v2.1 fixed.md §6~§10(§1~§5 已於前次報告涵蓋)。
- **本次候選:2 個**(強化 1 / 強化 1),另 **2 個觀察項**(單案未達 pattern 門檻,誠實列出)。
- **與前次關聯**:前次候選 1(mypy 既有債連坐)、候選 2(上游共用基建未納範圍)**皆因 v2.1 新條目再度復發並強化**;本報告不重複其原文,改以「已強化」交叉引用並補**新的、更可執行的根因規則**。前次兩候選仍待 user 決議,建議一併裁決。

---

## 候選 1 — 禁 repository / 類別方法名遮蔽 Python 內建型別(`list` / `dict` / `id` …)

> **決議:✅ 採納(user 2026-07-07)** — 走**方案 A**(命名規則 + grandfather),已於 C 段落地:`03-backend/00-overview.md § 命名 / § 型別` 增訂「新增方法禁名 `list`(用 `list_page`);grandfather scope 回傳標註用 `builtins.list[...]`」+ 檔頭變更紀錄。方案 B(8 repo 全改名)另開清債 task,不阻塞。

- **類型**:強化(新增可執行規則,root-cause 前次候選 1 的部分來源)
- **來源**:fixed.md `v2.1 §7`(`UsageLogRepository.list` 遮蔽內建 `list`,使全 class `-> list[...]` 標註觸 mypy `valid-type` 假錯,並連坐 `stats.py` 端點 `for r in rows` 的 `__iter__` 錯;worker 明示「跨 §1/§2/§4/§7 **第 4 次**」)、`v2.1 §1`(`mypy app/repositories/` 整包 20 錯)、`v2.1 §4`(`mypy app/tasks/ai_model_eval.py` 連坐 10 錯)
- **pattern**:符合判準①「同根因 ≥ 3 次」。§7 明確指認**根因**=方法名 `list` 遮蔽內建型別;現況盤點證實此為**全域系統性慣例**——`api_key_request` / `department` / `internal_key` / `openrouter_key` / `project` / `sdk_api_key` / `usage_log` / `user` **8 個 repository 全部**定義 `async def list(...)`(`grep "def list(" backend/app/repositories/`)。前次候選 1 談的是「acceptance 範圍 vs 鎖檔」的**流程面**,本候選補的是**碼面根因**:方法名遮蔽使任何 `list[...]` 回傳標註在該 class scope 失效,是 §1/§4/§7 mypy 債的直接來源之一。
- **建議**(二擇一,C 段拆 task 時定案):
  - **(A 首選,低破壞)** 於 `03-backend/00-overview.md § 命名` 增訂:「repository / service 的**分頁查詢方法禁命名 `list`**(遮蔽內建型別),一律用 `list_page` / `list_paged`;既有回傳型別標註**禁**在遮蔽 scope 用裸 `list[...]`,須 `builtins.list[...]`」。並於 `05-CI/02-backend-jobs.md` / ruff 設定啟用 `flake8-builtins`(ruff rule `A003` — class attribute shadowing builtin)對**新碼**強制。
  - **(B 徹底)** 開清債 task 把 8 repo 的 `list` 統一改名(如 `list_page`)+ 同步所有消費端,之後全 class 回歸 `list[...]` 標註,根治 mypy 連坐。
- **影響**:既有 8 repo 的 `list` 為**存量慣例**→ 必 grandfather:規則只規範**該 commit 之後**新增方法(對齊 `07-rule-evolution.md § 升級規則`);ruff `A003` 若對存量開啟會一次噴 8+ 處,故須**先開清債 task 或設 per-file-ignore**再開規則,否則 CI 紅。需同步:`03-backend/00-overview.md`(命名段)、`05-CI/02-backend-jobs.md`(ruff 設定)、`99-code-review/04-lint-checklist.md`(抽查項)。
- **driver**:後端 lead / ruff 設定 owner

---

## 候選 2 — 共用 `frontend/src/lib/utils/datetime.ts`(`formatDateTime`)缺口(強化前次候選 2)

> **決議:✅ 採納(user 2026-07-07)** — 已於 C 段落地:建 `frontend/src/lib/utils/datetime.ts`(照 `04-datetime.md` spec)、遷移就地實作(`excel.ts` 的 `formatBucketTaipei` → 改用共用 `formatDateTime`;`usage-logs/[uid]/page.tsx:182` 的 `new Date(...).toLocaleString()` → `formatDateTime`)、`04-datetime.md` 檔頭補「共用檔正式落地」變更紀錄。規則本已存在,本次補的是**缺失的檔案 + 遷移**。

- **類型**:強化(前次候選 2 的 datetime 分支再度復發)
- **來源**:fixed.md `v2.1 §5`(task-410 首個需日期顯示的前端 task,鎖檔下就地實作 `formatDateTime`)、`v2.1 §8`(task-422 時序 sheet 再次就地實作 `formatBucketTaipei`,**明標「§5 同源復發、第 2 次」**);另 `usage-logs/[uid]/page.tsx:195` 現存 `toLocaleString()` 亦為同缺口下的就地寫法
- **pattern**:同根因 **2 次**且**兩條 fixed 皆主動提名同一 reflect 候選**。嚴格論仍同版本(v2.1),未跨版本;但前次報告已將其列為候選 2 的一半(與 §3 合併),本次 §8 使「datetime util 缺口」單獨累積到 2 次自提名 → 建議自候選 2 **拆出獨立採納**,不再與「上游基建納範圍」的抽象議題綁一起。
- **建議**:開基建 task 建立 `frontend/src/lib/utils/datetime.ts`,匯出 `formatDateTime`(及 `formatBucketTaipei` 類 wall-clock 版),實作對齊 `02-frontend/04-datetime.md`(**禁** `new Date()` / `toLocaleString` / `timeZone`,用 ISO 字串切片);於 `02-frontend/05-components.md § 必抽` 補一行「日期時間顯示**必**走 `utils/datetime.ts`,禁各檔就地實作」。落地後把 §5(`AiRerunSection` 已刪除,略)、§8(`excel.ts`)、`usage-logs/[uid]/page.tsx:195` 的就地版一併改走共用入口。
- **影響**:純新增共用檔 + 遷移就地呼叫,無 backward 破壞;既有就地實作為 grandfather,遷移於清債 task 內完成。需同步:`02-frontend/05-components.md`(必抽清單)、`02-frontend/04-datetime.md`(指向共用入口)。**任務切分守則**:凡涉日期顯示的前端 task,orchestrator 須先確認共用 util 已存在,否則把「建立 util」納上游範圍。
- **driver**:前端 lead

---

## 觀察項(單案,未達 pattern 門檻,列出供 user 知情;暫不成正式候選)

> 依判準「單一 fixed.md 條目不算 pattern」(`寧空勿湊`),下列僅 1 次出現,**不**列為正式升規候選;若下版再現同類根因即跨門檻,屆時正式提。

- **OBS-1 · 改共用 repository 讀取方法回傳型別前須盤點全部消費端** — 來源 `v2.1 §9`(`get_by_uid` 被 3 個 AI 評審 service 直用,task-421 若改其回傳型別會連坐「本版不涉評審管線」的邊界,故另立 `get_by_uid_with_project`)。與前次候選 2「上游基建/契約」主題相關但具體根因不同(此為**契約變更盤點**而非**基建缺席**)。**觀察**:若後續版本再現「改共用方法契約連坐非範圍檔」,即與 §9 跨版本達門檻,升為「共用抽象契約變更前必盤點消費端」正式候選(落腳 `01-propose/02-task-decomposition.md § 依賴`)。
- **OBS-2 · 部門範圍過濾必須顯式防守 `department_uid IS NULL`** — 來源 `v2.1 §10`(`resolve_filters` 對「非-admin 且無部門」未防守 → usage-logs 明細外露跨部門 PII;scan AD-001,**已於本版修正**)。此為**安全/正確性**規則,價值高,但目前**單案**;fixed.md §10 已自提名落腳 `92-project-permission.md § 4`。**建議**:因已修正且落腳明確、成本極低,可**不經 pattern 門檻**,直接併入候選採納時的 C 段 task 一併補上 §4 明文條款(「非-admin 且無部門 → 一律 403,不得退化為無過濾」),避免此地板漏規重演。

---

## 已巡視、未成候選之判準(證明掃過,寧空勿湊)

- **判準②(同類根因跨 ≥ 2 版本 + 無對應規則)**:v2.1 各條根因(mypy 遮蔽 / datetime 缺口 / 契約盤點)**多集中於 v2.1 單版**;跨版本檢視 v1.2(Combobox 抽共用、`list_all` 回 `list[Model]`)、v1.5(SDK 明文策略)、v1.10(`model_dump` 漏 `mode="json"` 致 UUID 不可序列化)、v2.0(判別評審設計反覆)——各為**不同**根因,未與 v2.1 條目構成同類跨版本 pattern。v1.10 的 `mode="json"` 已於該版共用入口修補並自帶「後續建議」,無復發。
- **判準③(規範矛盾)**:本輪 fixed.md 無條目標「規範矛盾」;§6(pid 外露)為 user 主動拍板的**設計例外**(已於 propose 記錄破例),非規則衝突。
- **判準④(規則 ≥ 6 個月未違反 → 棄用)**:Design-Base 為 2026-06-25 起 re-baseline 的新體系,尚無規則達 6 個月無違反的棄用門檻,本輪無棄用候選。

---

## 前次報告候選狀態(提醒 user 一併裁決)

前次 [reflect-report-260626143642.md](./reflect-report-260626143642.md) 的候選 1（mypy acceptance vs 鎖檔）、候選 2（上游共用基建未納範圍）**未見決議標記(✅/❌/🕐)**,且皆因 v2.1 §7/§8/§9 **再度復發強化**。建議 user 於本報告 PR 上**一併決議前次兩候選**,避免持續累積。

---

## 決議方式(user 於 PR 逐條標記)

- ✅ 採納 → 開 task 走 C 段升級(改對應 Design-Base 檔 + 同步 checklist + 開清債 task)
- ❌ 拒絕 → 在本報告該候選下記「拒絕原因」(亦為學習素材)
- 🕐 暫緩 → 帶到下次 reflect 重評

---

## 本次結論

**2 個正式候選(皆強化)+ 2 個觀察項**:
1. **候選 1(強化)** — 禁方法名遮蔽內建型別(`list`);root-cause 全 8 repo 的 mypy `list` 債(§1/§4/§7 第 4 次),建議 A 命名規則 + ruff `A003` 對新碼強制,或 B 清債改名。
2. **候選 2(強化)** — 建立共用 `utils/datetime.ts`;§5/§8 第 2 次自提名,建議自前次候選 2 拆出獨立採納。
3. **OBS-1 / OBS-2** — 共用方法契約盤點、部門空值防守;單案未達門檻,OBS-2 因已修+落腳明確建議併入 C 段 task 直接補規。

等 user 於 PR 逐條決議(含前次兩候選)。
