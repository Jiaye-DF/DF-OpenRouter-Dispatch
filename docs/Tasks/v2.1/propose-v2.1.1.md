[//]: # (此檔為 v2.1.1 任務提案,實作前先由使用者確認範圍與設計取捨。Agent 草擬、User 拍板。)

# Propose v2.1.1 · Excel 補齊「專案×模型花費 + 儀表板全維度」 + 用量記錄下放部門(顯示所屬專案 + 專案篩選)

> 此為 **proposal**(詳設母本),確認後即據以拆 `workflow/` + `tasks/`。
>
> 對應母本鏈:[v1.5 依專案/使用者彙總](../v1.5)(stats by-project / by-user 起點) → [v2.1.0 AI 判決總覽](./propose-v2.1.0.md)。本版**不**涉及 AI 評審管線。
>
> **狀態**:皆為**定案**(user 2026-07-07 拍板)。功能一 = 「專案×模型 + 鏡射儀表板」;功能二 = 用量記錄**以部門為邊界**下放(非-admin 看自己部門用量),並在 UI 標示每筆呼叫所屬**專案**。

---

## ⚠️ 版號判定註記(需 user 確認)

依 [`01-propose/05-version-bump.md`](../../Design-Base/01-propose/05-version-bump.md) 判準:

- 功能一新增**唯讀彙總 endpoint** `GET /api/v1/stats/by-project-model`(向下相容、read-only)。
- 功能二**放寬授權**(usage-logs admin-only → 非-admin 可讀**自身部門**用量;權限**放寬非收緊**,不屬 breaking;且對齊 [`92-project-permission.md § 4`](../../Design-Base/03-backend/92-project-permission.md) 已載明「自身部門用量 ✅ User」),並於列表/明細 response **新增專案欄位**(向下相容欄位新增)。**不新增 DB 欄位、不動 schema**(`usage_logs.project_uid` 早已存在)。

上述「新 endpoint / 向下相容欄位新增 / 權限放寬」按判準屬 **minor(→ v2.2.0)**,非 patch。前例:v2.1.0 原暫定 v2.0.5 patch,因需新表 + 新 endpoint 而 bump 為 minor。**本檔依 user 指示暫以 v2.1.1 落檔**;若希望對外開新 API 版,建議改置於 `docs/Tasks/v2.2/propose-v2.2.0.md`。**版號最終由 user 決定**。

---

## 版本目標

兩件對「成本可視性 / 自助查詢」有價值的補強:

1. **Excel 匯出補齊**:下載的 Excel 目前只鏡射儀表板的「部門 / 專案 / 使用者」三維度且**無模型花費**;補上「**每個專案再依模型拆解的花費明細**」與儀表板其餘維度(總覽 KPI / 依模型 / 時序),讓 Excel 成為儀表板的**完整實體表格**,供離線成本分析與報表。
2. **用量記錄下放部門**:用量記錄(列表 + 明細)目前**一律 admin-only**;以**部門**為邊界開放給一般使用者自助查看**自身部門**的用量紀錄(用量本質即部門成本),並在 UI 標示**每筆呼叫所屬專案**、提供**專案 Combobox 篩選**,降低 admin 代查負擔、提升部門對自身成本的掌握度。

## In Scope

### 功能一 · Excel(定案)

- **新後端唯讀彙總 endpoint**(§B.1):`GET /api/v1/stats/by-project-model` — 依「專案 × 模型」雙維度彙總請求數 / tokens / 成本;沿用現有 stats 篩選(部門 / 專案 / 使用者 / 日期)與非-admin 鎖部門邏輯(`_resolve_filters`)。
- **新 Response schema**(§B.2):`ProjectModelStatItem`(Pydantic 明確定義,`Decimal` 成本)。
- **Excel 匯出擴充**(§C):在既有「部門 / 專案 / 使用者」三 sheet 外,補上 —
  - **總覽 sheet**(KPI:總請求數 / 總 Tokens / 總成本 USD)。
  - **依模型 sheet**(模型 / 請求數 / Prompt Tokens / Completion Tokens / Tokens / 成本 USD)。
  - **專案×模型明細 sheet**(專案代碼 / 專案名稱 / 模型 / 請求數 / Tokens / 成本 USD)。
  - **時序 sheet**(時間桶 UTC+8 / 請求數 / Tokens / 成本 USD)。
- **儀表板下載流程串接**(§C.2):下載時補抓 `by-project-model`(其餘維度儀表板已在畫面取得,直接複用)。

### 功能二 · 用量記錄以部門為邊界下放(定案)

- **授權放寬**(§B.3):`GET /api/v1/usage-logs`(列表)與 `GET /api/v1/usage-logs/{uid}`(明細)由 `AdminDep` 改為 `UserDep` + **非-admin 鎖部門**:admin 看全部;非-admin 僅能看**自己部門**(`department_uid = actor.department_uid`)的用量。**沿用** stats 端點既有的 `_resolve_filters` 模式(跨部門顯式傳參 → 403;明細取他部門 log → 404)。
  - 理由(user 拍板):**用量本質即部門成本**,以部門為邊界最貼合且與 [`92-project-permission.md § 4`](../../Design-Base/03-backend/92-project-permission.md)「自身部門用量 ✅ User」一致,無須新增 owner 關聯 / 欄位。
- **顯示所屬專案**(§B.3 / §C.3):列表與明細 response **新增專案欄位**(`project_uid` / `project_code` / `project_name`,repository JOIN `projects` 取得);前端列表加「專案」欄、明細加「專案」欄位,讓查看者知道**每筆呼叫屬於哪個專案**。
- **專案篩選 Combobox**(§B.3 / §C.3):列表篩選器新增**專案** Combobox(可輸入搜尋),對應後端 `project_uid` 查詢參數;專案選項來源複用 `GET /api/v1/projects`(非-admin 已鎖部門)。
- **前端可見性**(§C.3):`RouteGuard` 放行 `/usage-logs` 給一般使用者;`Sidebar` 該入口對非-admin 顯示;非-admin 檢視隱藏「部門」等 admin-only 篩選(後端仍鎖部門把關)。

## Out of Scope

- **新角色 / 細粒度 RBAC**:不新增 `project_owner` 角色;維持 `admin` / `user` 二元(對齊 [`92-project-permission.md § 2`](../../Design-Base/03-backend/92-project-permission.md))。負責關聯以資料界定,不以 role 固化。
- **後端產生 .xlsx**:Excel 仍走**前端 SheetJS**(client-side),不新增後端匯出端點 / 檔案串流(現況 `frontend/src/lib/export/excel.ts`)。
- **用量記錄的寫入 / 稽核改動**:只放寬**讀取**,不動 `usage_logs` 寫入鏈路與稽核表。
- **AI 分析區塊下放**:usage-log 明細頁的 `AiAnalysisSection`(AI 評審 / 判決)**維持 admin-only**;非-admin 明細頁**不**顯示 AI 分析(§C.3 註記)。
- **匯出的權限外擴**:非-admin 於儀表板匯出 Excel 時,資料範圍仍受後端鎖部門約束(沿用現況),本版不擴增匯出可見範圍。

## 對外承諾

- **新增 API**(`/api/docs` 可查):
  - `GET /api/v1/stats/by-project-model`(`UserDep`,非-admin 鎖部門)→ 依專案×模型彙總陣列;無資料 → `200 + []`。
- **調整 API 授權 + 欄位**(功能二):
  - `GET /api/v1/usage-logs`、`GET /api/v1/usage-logs/{uid}`:`AdminDep` → `UserDep` + 非-admin 鎖部門。**admin 行為不變**(看全部);新增「一般使用者可讀自身部門用量」路徑;跨部門 → 403 / 404。
  - 兩端點 response **新增** `project_uid` / `project_code` / `project_name`(向下相容);列表新增 `project_uid` 查詢參數。
- **行為**:功能一為純新增(舊 Excel 欄位 / sheet 不移除、不改名);功能二為**授權放寬 + 欄位新增**(既有 admin 存取與回傳欄位不受影響)。

## 資料流

### 功能一(Excel)

```
[儀表板頁] 使用者按「下載 Excel」
   │  畫面已持有 overview / byDept / byModel / byProject / byUser / timeseries
   │  下載時額外補抓 GET /stats/by-project-model(同一組篩選)
   ▼
[frontend/src/lib/export/excel.ts] exportDashboardToExcel(擴充輸入)
   │  組 sheet:總覽 / 部門 / 專案 / 使用者 / 依模型 / 專案×模型 / 時序
   │  成本欄套 USD 六位小數格式($0.000000)
   ▼
XLSX.writeFile → 瀏覽器下載 dashboard_{from}_{to}.xlsx
```

### 功能二(用量記錄下放)

```
[使用者] GET /api/v1/usage-logs?project_uid=...(帶登入 Cookie)
   ▼
require_user → Actor(role, department_uid)
   ▼
_resolve_filters(actor, department_uid, project_uid):
   ├─ admin        → 用傳入的 department_uid / project_uid(不強制)
   └─ 非-admin     → 強制 department_uid = actor.department_uid
                     跨部門顯式傳參 → 403;project_uid 非本部門 → WHERE 自然篩空
   ▼
UsageLogRepository.list(... + department_uid + project_uid) JOIN projects
   → 每筆帶 project_uid / project_code / project_name
   ▼
明細 get_by_uid:非-admin 取他部門 log → 404 not_found(不揭露存在);admin 不變
```

## 後端(§B)

### B.1 新 endpoint `GET /api/v1/stats/by-project-model`

- 落點:`backend/app/api/v1/stats.py`(新增 `by_project_model_endpoint`,緊鄰既有 `by_project_endpoint`)。
- 依賴:`UserDep` + `_resolve_filters`(**沿用**,非-admin 鎖部門、跨部門 403)。
- Repository:`backend/app/repositories/usage_log.py` 新增 `by_project_model()`:
  - `SELECT project_uid, Project.code, Project.name, model, count(pid), sum(total_tokens), sum(cost_usd)`
  - `.join(Project, Project.project_uid == UsageLog.project_uid)`(**INNER JOIN**,與 `by_project` 一致 → 歷史 `project_uid IS NULL` 不出現)
  - `.group_by(project_uid, code, name, model)`;套用共用 `_apply_filters`。
  - 排序建議:`project_code, cost_usd DESC`(同專案內模型花費由大到小)。
- 索引:現有 `idx_usage_logs_project_uid_time`、`idx_usage_logs_model_time` 已足供彙總;**不新增索引**(本版不動 DB)。

### B.2 Response schema

- 落點:`backend/app/schemas/stats.py` 新增:

```python
class ProjectModelStatItem(BaseModel):
    project_uid: UUID
    project_code: str
    project_name: str
    model: str
    total_requests: int
    total_tokens: int
    total_cost_usd: Decimal
```

- 對外殼為統一 `ApiResponse`(`success_response(data=[...])`),`Decimal` 序列化沿用既有 `model_dump(mode="json")` 慣例。

### B.3 用量記錄授權放寬 + 部門鎖 + 專案欄位/篩選(定案)

- 落點:`backend/app/api/v1/usage_logs.py`。
- **授權**:列表 + 明細兩處 `AdminDep` → `UserDep`;**引入與 stats 同款 `_resolve_filters`**(admin 不鎖、非-admin 強制 `department_uid = actor.department_uid`、跨部門顯式傳參 → 403)。**禁止**在 router 散落 `if role`(對齊 [`92-project-permission.md § 6`](../../Design-Base/03-backend/92-project-permission.md));建議把 `stats.py` 的 `_resolve_filters` 抽為共用工具供兩者引用(避免複製)。
- **列表新增 `project_uid` 查詢參數**:`backend/app/repositories/usage_log.py` 的 `list()` 支援 `project_uid` 過濾(現有 `_apply_filters` 已具 `project_uid`,列表方法補接參數即可)。
- **回傳專案欄位**:`list()` 與 `get_by_uid()` **JOIN `projects`** 取 `code` / `name`;`UsageLogListItem` / `UsageLogDetail` 新增 `project_uid: UUID | None`、`project_code: str | None`、`project_name: str | None`(歷史 `project_uid IS NULL` → 三欄皆 NULL,以 **LEFT JOIN** 保留無專案的歷史列,有別於 stats 的 INNER JOIN)。
- **明細 `get_by_uid`**:非-admin 取他部門 log → `404 not_found`(不以存在與否側漏,§D.1);admin 不變。
- **敏感欄位**:明細含 `request_content` / `response_summary`(可能含 PII);下放對象為同部門使用者,對齊 v2.0.1「本版不遮罩、保留 mask hook」現況;仍**禁止**回傳金鑰類機密(沿用現況過濾)。
- 稽核:讀取放寬,**不**寫稽核 Log(對齊「代理端業務紀錄入 usage_logs、管理端異動才入稽核表」)。

## 前端(§C)

### C.1 Excel 模組擴充

- 落點:`frontend/src/lib/export/excel.ts`。
- `DashboardExportInput` 擴充:加 `overview?`、`byModel?`、`byProjectModel?`、`timeseries?`。
- 新增 sheet builder(沿用既有 `buildSheet` / `USD_FORMAT` / 欄寬估算):
  - **總覽**:兩欄 key-value(`指標` / `值`),列「總請求數 / 總 Tokens / 總成本 (USD)」;成本列套 USD 格式。
  - **依模型**:`模型 / 請求數 / Prompt Tokens / Completion Tokens / Tokens / 成本 (USD)`。
  - **專案×模型**:`專案代碼 / 專案名稱 / 模型 / 請求數 / Tokens / 成本 (USD)`。
  - **時序**:`時間 (UTC+8) / 請求數 / Tokens / 成本 (USD)`;時間以既有 `utils/datetime` 格式化(對齊 [`02-frontend/04-datetime.md`](../../Design-Base/02-frontend/04-datetime.md))。
- sheet 順序建議:總覽 → 部門 → 專案 → 專案×模型 → 依模型 → 使用者 → 時序。既有三 sheet 欄位不動。

### C.2 儀表板下載串接

- 落點:`frontend/src/app/(main)/dashboard/page.tsx`(`onDownloadExcel`)。
- 下載時 `await` 補抓 `GET /stats/by-project-model`(同畫面篩選參數),連同畫面已持有的 `overview/byModel/timeseries` 一併傳入 `exportDashboardToExcel`。
- 型別 / 端點常數:`frontend/src/types/api.ts` 加 `StatsByProjectModel`;`frontend/src/lib/api/endpoints.ts` 加 `statsByProjectModel`。
- `!hasAnyData` disabled 邏輯不變。

### C.3 用量記錄前端:可見性 + 專案欄 + 專案 Combobox(定案)

- 可見性落點:`frontend/src/components/layout/RouteGuard.tsx`(`MEMBER_ALLOWED_PREFIXES` 加 `/usage-logs`)、`frontend/src/components/layout/Sidebar.tsx`(用量記錄入口由 `adminOnly:true` 改為對所有登入者顯示)。
- **顯示所屬專案**:
  - 列表頁 `frontend/src/app/(main)/usage-logs/page.tsx` 新增「**專案**」欄(顯示 `project_code` + `project_name`;NULL → 顯示「—」或「(無專案)」)。
  - 明細頁 `frontend/src/app/(main)/usage-logs/[uid]/page.tsx` 基本資訊區新增「專案」欄位。
- **專案篩選 Combobox**:
  - 列表頁篩選列新增**專案** `Combobox`(`frontend/src/components/ui/Combobox.tsx`,可輸入搜尋),選定後帶 `project_uid` 查詢。
  - 選項來源:`GET /api/v1/projects`(`API_ENDPOINTS.projects`,非-admin 已鎖部門);沿用 `DashboardFilters` 抓專案清單的既有模式(改用 Combobox 呈現)。
- 型別 / 端點:`frontend/src/types/api.ts` 的 usage-log 型別補 `project_uid` / `project_code` / `project_name`;列表查詢參數補 `project_uid`。
- 非-admin 檢視隱藏「部門」等 admin-only 篩選(UX 提示;後端仍鎖部門把關,**禁止**前端自行判斷可見性)。
- **明細頁**:非-admin 檢視**不**渲染 `AiAnalysisSection`(AI 分析維持 admin-only);其餘基本欄位(時間 / 專案 / 模型 / tokens / 成本 / 延遲 / 狀態 / 輸入輸出)照常顯示。

## 設定(環境變數)

- 功能一 / 功能二:**皆無新增 env、無 migration、不動 DB schema**(功能一為唯讀彙總 + 前端組表;功能二只放寬授權 + JOIN 既有 `projects` 吐欄 + 前端呈現)。

## D. 已決議細節(user 2026-07-07 拍板)

### D.1 明細越權回應碼 — 採 `404 not_found`

非-admin 開啟他部門 usage-log 明細 → 回 **`404 not_found`**(不以「存在與否」側漏),與現況 `get_usage_log` 找不到即回 404 一致;非 403。

### D.2 負責關聯 = 部門邊界(已捨棄 owner 欄 / 申請單推導)

user 拍板:「**用量本質即部門成本**,提高到部門即可。」故**不**建立 `projects.owner_user_uid`、**不**由申請單推導個人負責關聯;非-admin 可見範圍 = 自身部門,與 stats 端點完全一致。先前討論的「User-Token 持有者」語義**本版不採用**(留作日後若需「個人負責專案」再議)。

## 風險與相依

- **成本 / 效能**:`by-project-model` 為多維 GROUP BY;現有複合索引可支撐,惟大時間範圍彙總仍應以 `EXPLAIN ANALYZE` 抽查(對齊 [`04-databases/09-indexes-and-perf.md`](../../Design-Base/04-databases/09-indexes-and-perf.md))。
- **Excel 體積**:專案×模型明細列數 = Σ(專案的相異模型數),可能較大;必要時前端提示或分頁匯出(本版先不分頁,列數評估於 task 驗證)。
- **越權外洩(功能二)**:授權放寬的核心風險是「部門鎖漏網」。**必須**於後端強制 `department_uid = actor.department_uid`(沿用 `_resolve_filters`),並以測試覆蓋「他部門 user 取不到本部門 log(列表 + 明細)、跨部門顯式傳參 403、他部門明細 404」。
- **PII**:明細下放使同部門使用者可見該部門呼叫輸入輸出(可能含 PII);對齊 v2.0.1「本版不遮罩、保留 mask hook」現況,限定「自身部門」範圍。
- **版號**:見開頭「版號判定註記」——本檔暫落 v2.1.1;若需對外開新 API 版建議改 v2.2.0(最終由 user 決定)。

## 驗收標準

### 功能一

- `GET /api/v1/stats/by-project-model` admin 可取全部、非-admin 鎖部門(跨部門 403)、無資料 `200 + []`;`/api/docs` 可查。
- 回傳每列含 `project_uid/project_code/project_name/model/total_requests/total_tokens/total_cost_usd`;歷史 `project_uid IS NULL` 不出現。
- 下載的 Excel 含 7 個 sheet(總覽 / 部門 / 專案 / 專案×模型 / 依模型 / 使用者 / 時序);成本欄為 USD 六位小數格式;既有三 sheet 欄位不變。
- 專案×模型 sheet 的每個專案花費 = 其各模型花費加總,且與「專案」sheet 該專案總成本一致(交叉驗證)。
- 後端單元 / 整合測試涵蓋 `by_project_model` 彙總與鎖部門;前端 `exportDashboardToExcel` 對擴充輸入產生正確 sheet(可加輕量單測或手測 case)。

### 功能二

- admin 取 `/usage-logs` 列表 / 明細行為不變(且回傳新增專案欄位)。
- 非-admin 取列表 → 僅回自身部門 log;帶 `project_uid`(本部門專案)→ 正確過濾;跨部門顯式傳 `department_uid` → 403;取他部門明細 → 404。
- 列表 / 明細 response 每筆含 `project_uid` / `project_code` / `project_name`(歷史 NULL 專案三欄為 NULL、列仍出現)。
- 前端:列表有「專案」欄 + 專案 Combobox(可搜尋、選定過濾);明細有「專案」欄位;`RouteGuard` 放行 `/usage-logs` 給一般使用者;非-admin 明細頁不顯示 AI 分析區塊。
- 後端測試涵蓋:鎖部門、`project_uid` 過濾、跨部門 403、他部門明細 404、JOIN 專案欄位正確。`/api/docs` 可查新參數與欄位。

## 設計取捨 / 已決議(user 拍板)

| # | 決議 | 落點 |
| --- | --- | --- |
| 1 | **功能一範圍 = 專案×模型 + 鏡射儀表板全維度**(非只鏡射、非只專案×模型) | user 2026-07-07;§B/§C |
| 2 | Excel 維持**前端 SheetJS**,不做後端匯出端點 | Out of Scope |
| 3 | `by-project-model` 沿用既有 stats 篩選 + 非-admin 鎖部門,不新增索引 / env / migration | §B.1 |
| 4 | 功能二**不新增角色**,以**部門邊界**界定可見範圍(用量即部門成本);捨棄 owner 欄 / 申請單推導 / User-Token 持有者語義 | §B.3、§D.2 |
| 5 | 明細 AI 分析區塊維持 admin-only,不隨用量記錄下放 | §C.3、Out of Scope |
| 6 | 用量記錄新增「所屬專案」顯示 + 專案 Combobox 篩選(複用 `/projects` 清單) | §B.3、§C.3 |
| 7 | 明細越權回應碼採 **404**(不側漏存在) | §D.1 |
| — | **版號**(v2.1.1 vs v2.2.0) | **待 user 拍板**(見開頭註記) |

## 變更紀錄

| 日期 | 改動 | 理由 |
| --- | --- | --- |
| 2026-07-07 | 初版草擬:功能一(Excel 專案×模型 + 全維度鏡射)定案;功能二(用量記錄下放專案負責人)草案 + 負責關聯待拍板 | user 提兩需求;功能一範圍已拍板,功能二負責關聯 user 思考中 |
| 2026-07-07 | 功能二定案:負責關聯 = **部門邊界**(用量即部門成本);新增「用量記錄顯示所屬專案」+「專案 Combobox 篩選」;明細越權採 404;移除 §D 待確認,只留版號待拍板 | user 拍板部門邊界,並要求 UI 能知道每筆呼叫屬哪個專案、篩選器加專案 Combobox |
