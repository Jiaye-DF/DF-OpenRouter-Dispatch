# 專案掃描報告 — Issue-Scan-Project-260707050320

> 掃描時間:2026-07-07 05:03:20 (UTC+8)
> 範圍焦點:**v2.1.1 變更**(task-420~423:Excel 專案×模型全維度 + 用量記錄下放部門)+ 通用規則回歸
> 基準報告:[Issue-Scan-Project-260626142613.md](./Issue-Scan-Project-260626142613.md)(v2.1.0)
> 掃描者:資深工程師(非 linter)。規則為地板;AD 寧空勿湊。

---

## 0. 與前次差異

以 `R-xxx`/`AD-xxx` ID + 路徑為 key:

| 狀態 | 項目 | 嚴重度 | 說明 |
| --- | --- | --- | --- |
| 🆕 新增 | AD-001 `resolve_filters` 空部門漏洞(`_scope_filters.py:17-21`)經 usage-logs 放大 | 🟠 | v2.1.1 把敏感的 usage-logs(含 request/response PII)接上共用 `resolve_filters`;非-admin 且 `department_uid=None` 時**部門鎖失效**。詳見第 3 章。 |
| 🆕 新增 | AD-002 非-admin usage-log 視圖外露內部 UID(`schemas/usage_log.py:22-24`) | 🟡 | 下放部門後,非-admin 可見 `user_uid`/`department_uid`/`openrouter_key_uid`(內部識別,非機密)。 |
| ⏸ 既有債維持 | fixed.md §7 `UsageLogRepository.list` 方法名遮蔽內建 `list` → mypy 連坐 | 🟠→記錄 | 跨 §1/§2/§4/§7 **第 4 次**,已遠超升規門檻。v2.1.1 新碼以 `builtins.list[...]` 迴避,零新增 mypy 錯。建議開清債 task。 |
| ⏸ 既有債維持 | fixed.md §8 共用 `utils/datetime.ts` 仍未建 | 🟡→記錄 | 跨 §5/§8 第 2 次;task-422 只能於 `excel.ts` 就地實作 `formatBucketTaipei`。 |
| ✅ 沿用通過 | R-BE-005 usage-logs 受保護 | 🔴 | `AdminDep→UserDep` 仍為認證端點;權限收斂於 `resolve_filters`,未散落 `if role`。 |
| ✅ 沿用通過 | R-SEC-008 權限後端強制 | 🔴 | 部門鎖於 service/資料層(`resolve_filters` + repo WHERE),非前端過濾。 |
| ✅ 沿用通過 | R-BE-003 ApiResponse 殼 | 🟠 | 新端點 `by-project-model`、usage-logs 皆走 `success_response`。 |

**本次結論:v2.1.1 四個 task 新碼品質高,無 🔴。1 個 🟠(AD-001 空部門漏洞,建議本週修)+ 1 個 🟡(AD-002 內部 UID 外露)。既有 mypy `list` 遮蔽債第 4 次復發,強烈建議開清債 task 並交 `/reflect-rules`。**

---

## 1. 總覽

| 項目 | 值 |
| --- | --- |
| 掃描時間 | 2026-07-07 05:03:20 (UTC+8) |
| 類別涵蓋 | ENV / AI / FE / BE / DB / SEC / PII / LOG / GIT / TEST / DEP |
| 🔴 Critical | 0 |
| 🟠 High | 1(AD-001) |
| 🟡 Medium | 1(AD-002)+ 2 既有債記錄(fixed.md §7/§8) |
| 🔵 Low | 0 新增 |
| ⚪ Info | — |

**結論**:功能一(Excel by-project-model + 全維度鏡射)後端純讀 ApiResponse、前端強型別 + 就地時區格式化(不用 `new Date`),乾淨。功能二(用量記錄下放部門)後端把權限正確收斂於共用 `resolve_filters`、前端 RouteGuard/Sidebar 放行 + role gate AI 區塊,整體良好;**唯一實質缺陷**是 `resolve_filters` 對「非-admin 且無部門」的使用者未防守,而 usage-logs 明細會外露跨部門 PII,放大了此既有邏輯漏洞。

---

## 2. 專案摘要

- **目標**:OpenRouter API 中控派發管理平台(金鑰/配額/路由/稽核 + 用量統計)。
- **技術棧對照**:FastAPI + SQLAlchemy 2 async + PostgreSQL 17(後端)/ Next.js App Router + TS + RTK + Tailwind(前端)/ taskiq + Redis(背景任務)。與 Design-Base 一致。
- **目錄結構**:`backend/app/{api,services,repositories,schemas,models,core}` 分層清楚;`frontend/src/{app,components,lib,store}`。符合規範。
- **Task 進度**:v2.1.1 四 task(420 後端 stats / 421 後端 usage-logs / 422 前端 Excel / 423 前端用量記錄)**全數 done**,4/4;fixed.md 累積至 §9。
- **完成度**:v2.1.1 功能完整,測試覆蓋(test_stats 5、test_usage_logs 10,repo 整合測試無 DB 自動 skip)。

---

## 3. 詳細發現(依嚴重度)

### 🟠 [AD-001] `resolve_filters` 對「非-admin 且無部門」未防守,usage-logs 明細會外露跨部門 PII — ✅ 已修正,見 fixed.md §10

- **檔案**:`backend/app/api/v1/_scope_filters.py:17-21`;放大點 `backend/app/api/v1/usage_logs.py:35`(列表)、`:69,76`(明細)
- **內容**:
  ```python
  # _scope_filters.py
  if actor.is_admin:
      return department_uid, project_uid, user_uid
  if department_uid is not None and department_uid != actor.department_uid:
      raise AppError("forbidden", code=403)
  return actor.department_uid, project_uid, user_uid   # ← actor.department_uid 可能為 None
  ```
- **白話**:`users.department_uid` 為 `nullable=True`(`backend/app/models/user.py:71-73`),`Actor.department_uid` 亦 `UUID | None`。若一個**非-admin 使用者沒有部門**(dept=None):
  - **列表**:`resolve_filters` 回 `dept=None` → `repo.list(department_uid=None)` **不加部門 WHERE** → 看到**全平台所有部門**的用量紀錄。
  - **明細**:`usage_logs.py:76` 的 `if dept is not None and log.department_uid != dept` 因 `dept is None` **整段跳過** → 可開啟**任一部門**的 usage-log 明細,而明細含 `request_content` / `response_summary`(使用者實際輸入輸出,**可能含 PII**)。
  - 此漏洞在 stats 端點(同用 `resolve_filters`)已潛在存在,但 stats 只吐彙總數字;v2.1.1 首次把**含 PII 原文**的 usage-logs 接上此函式,後果升級。
- **修正(具體)**:於 `_scope_filters.py:20` 前補「非-admin 無部門 → 拒絕」防線:
  ```python
  if actor.department_uid is None:
      raise AppError("forbidden", code=403)   # 非-admin 必須隸屬部門才可查詢
  return actor.department_uid, project_uid, user_uid
  ```
  一次修好同時保護 stats 與 usage-logs。若不願改共用函式(顧慮 stats 行為),則在 `usage_logs.py` 兩端點對 `dept is None and not actor.is_admin` 明確回 403 / 空集。**建議改共用函式**,語義最一致。
- **首次發現**:2026-07-07

---

## 4. 修正優先序

- **立刻**:無(無 🔴)。
- **本週**:
  - 🟠 AD-001 — `resolve_filters` 補「非-admin 無部門 → 403」防線(3 行,含 stats/usage-logs 一次到位;補一條 pytest:非-admin dept=None 取列表/明細 → 403)。
- **有空**:
  - 🟡 AD-002 — 評估非-admin usage-log 視圖是否需 DTO 剔除 `user_uid`/`department_uid`/`openrouter_key_uid`(內部識別)。
  - 🟡 清債(fixed.md §7)— `UsageLogRepository.list` 改名(如 `list_page`)後全 class 回歸 `list[...]` 標註,根治 mypy 連坐(第 4 次復發,已達升規門檻)。
  - 🟡 清債(fixed.md §8)— 建立共用 `frontend/src/lib/utils/datetime.ts`,收斂各處就地時間格式化。

---

## 5. 已跳過類別(附原因)

- **R-DB-013/014/015(migration COMMENT / table_catalog)**:v2.1.1 **無 migration、不動 DB schema**(propose 明訂),整批 DB-schema 規則不適用。
- **R-ENV-***:v2.1.1 未新增/變更 env（propose 明訂無新 env），無 `.env*` 異動。
- **R-DEP-***:未動 `pyproject.toml` / `package.json` / lock 檔。
- **R-SEC-001/004/006(JWT alg / eval / 上傳)**:v2.1.1 未觸及認證簽章、無 `eval`/`exec`、無檔案上傳。
- **R-LOG-***:v2.1.1 未動啟動/健康檢查/log 基建。
- **R-GIT-***:commit 皆 `(AI) [v2.1.1][task-NNN]` 格式,符合規範。

---

## 6. AD-xxx(規則外架構判斷)

### 🟠 AD-001 — 見第 3 章(空部門部門鎖漏洞,usage-logs PII 放大)。

### 🟡 AD-002 — 非-admin usage-log 視圖外露內部識別 UID

- **檔案**:`backend/app/schemas/usage_log.py:22-24`(`UsageLogListItem` 含 `user_uid` / `department_uid` / `openrouter_key_uid`)
- **白話**:下放部門前這些欄位只有 admin 看;v2.1.1 後同部門的非-admin 也看得到同事的 `user_uid` 與該次呼叫的 `openrouter_key_uid`。皆為**內部 UID(非金鑰明文/hash)**,後果低,但 `90-third-party-service/50-openrouter.md § 6` 對代理回應要求「移除內部識別欄位」。管理端歷來外露、propose 也僅承諾「不外露金鑰類機密」,故列 🟡 供評估,非必修。
- **修正**:若要收緊,對非-admin 分支回傳精簡 DTO(去 `user_uid`/`openrouter_key_uid`),保留 `project_*` / `model` / tokens / cost / 時間。

### 已巡視、低後果未列正式項

- **R-BE-011(data 為 array)**:`stats/by-project-model` 回 `data=[...]` 陣列——**沿用既有全體 stats 端點慣例**(by-department/by-model/by-project 皆然),非 v2.1.1 引入的偏差,不重複計。
- **功能二 intra-department PII 可見性**:同部門成員可見彼此 `request_content`——**user 已拍板部門邊界(用量即部門成本)**且 propose「風險與相依」已揭露 PII 不遮罩(沿用 v2.0.1 現況),屬已知設計取捨,不列缺陷。
- **前端變更檔**:`usage-logs/page.tsx`、`[uid]/page.tsx`、`excel.ts`、`dashboard/page.tsx` grep 無 `any`/`localStorage`/`dangerouslySetInnerHTML`;明細頁 AI 區塊以 `role === "admin"` 正確 gate(`[uid]/page.tsx:235`)。
- **時區**:task-422 時序 sheet 以 regex 切片格式化,未用 `new Date()`,對齊 `05-timezone.md` / `04-datetime.md`。

---

## 7. 規範自身問題(Design-Base 矛盾 / 缺漏)

1. **`resolve_filters` 空部門語義未於 Design-Base 明定**:`92-project-permission.md § 4` 只寫「User 看自身部門」,未規範「非-admin 但**無部門**」的行為。AD-001 正是踩此缺口。**建議**於 `92-project-permission.md § 4` 補一條:「非-admin 且 `department_uid` 為 NULL → 一律拒絕管理端資料查詢(403),不得回退為無過濾」,並於 `resolve_filters` 落實。
2. **既有債達升規門檻(第 4 次)**:mypy `list` 方法名遮蔽(fixed.md §1/§2/§4/§7)。前次報告(260626142613 第 7 章)已建議開清債 task,至今未開。**建議**跑 `/reflect-rules` 將「repository 方法名禁與內建型別同名」升為 Design-Base 規則(`03-backend/00-overview.md` 命名段),並開清債 task。
3. **共用 `utils/datetime.ts` 缺漏(第 2 次,fixed.md §5/§8)**:`04-datetime.md` 規定共用檔存在,但實際未建。**建議**開基建 task 建立,終止「就地實作」復發。

---

> 總結:v2.1.1 四 task 新碼**無 🔴**、品質高。唯一需本週處理者為 **AD-001**——`resolve_filters` 對「非-admin 無部門」缺防線,而 usage-logs 明細會因此外露跨部門 PII(3 行可修,含測試)。其餘為既有跨版技術債(mypy `list` 遮蔽第 4 次、datetime util 第 2 次),應交 `/reflect-rules` 升規並開清債 task。

---

**幫你修 AD-001(本週唯一 High)?** 我可加上 `resolve_filters` 的空部門 403 防線 + 對應 pytest,一併保護 stats 與 usage-logs。
