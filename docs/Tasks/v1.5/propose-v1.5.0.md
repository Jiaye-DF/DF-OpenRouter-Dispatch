# Propose v1.5.0 · 專案維度串接 + 儀表板多維度篩選

> 此為 **proposal**(規劃草案),確認後即轉為正式 [`tasks-v1.5.0.md`](./tasks-v1.5.0.md)。
>
> 對應母本:[v1.4 部署與 UX 維護修正集](../v1.4/propose-v1.4.0.md)。

## 1. 目標

兩件事一起做:

1. **把既有「專案」(`projects` 表)真正串進代理鏈與用量稽核**:目前 `projects` 從 v1.0 baseline 就建好且有 CRUD UI,但 **未被任何核心流程引用** — usage_logs 不記 project_uid、SDK Key 不綁 project、代理請求也沒有對應 header。v1.5 補齊這條串接,讓「部門底下還能分專案」變成可用的維度。
2. **儀表板擴展為多維度篩選**:既有儀表板只能看「全平台」或「依部門」單一維度。v1.5 加上「部門 / 專案 / 使用者」三層篩選,並新增「依專案彙總」「依使用者彙總」兩個視圖。

不做:**預算管理 / 超支警告**(使用者明確表示「不需要這麼複雜」);如未來需要,留待 v1.6+ 再做。

## 2. 動機

- 業務上「資訊部底下會有多個應用」(例如 OpenRouter 正式站、簽核 AI、點檢系統 AI),管理者需要知道「哪個應用花最多錢」,而不只是「資訊部花了多少」。
- 既有資料模型中專案這層 schema 已備,但因從未串接,所有 usage_logs 在「依部門」之上無法再細分 → 直接補一個欄位即可解鎖。
- 儀表板目前無法回答「使用者 X 這個月用了多少 token」「專案 Y 這個月燒了多少錢」這類常見問題;加上篩選後可大幅減少 admin 在 usage-logs 頁面手動撈資料的時間。

## 3. 範圍

### In Scope

**Schema**:
- `usage_logs` 加 `project_uid UUID NULL`(FK to `projects(project_uid)`,`ON DELETE SET NULL`);新增 partial index `(project_uid, created_at DESC) WHERE is_deleted = FALSE`

**後端認證(代理鏈)**:
- `SdkCallerContext` 加 `project_uid` / `project_code` 欄位
- `require_sdk_caller` 解析 `X-Project-Id` header;缺 → `400 project_id_required`,格式錯 → `400 project_invalid`
- `resolve_sdk_caller` 在既有 SDK Key + User Token + 部門一致性檢查之後追加 project ownership 驗證(必須屬於 SDK Key 的部門、`is_active=TRUE`、`is_deleted=FALSE`),否則 → `400 project_invalid`
- `ProjectRepository.get_active_by_uid_and_dept(project_uid, dept_uid)` 新查詢方法

**後端代理 + 用量寫入**:
- `run_chat` / `_run_chat_openrouter` / `_run_chat_internal` / `_try_internal_call` 簽名加 `project_uid`
- `schedule_usage_log` 簽名加 `project_uid`,寫入 `usage_logs.project_uid`
- 所有寫 log 的呼叫點(成功 / 各類錯誤共 7 處)都把 `project_uid` 傳入

**後端統計 API**:
- `UsageLogRepository._apply_filters` 加 `project_uid` 參數
- 既有 4 個 method (`overview` / `by_department` / `by_model` / `timeseries`) 都加 `project_uid` / `user_uid` 篩選
- 新增 `by_project()`(INNER JOIN projects;歷史 NULL 紀錄自然排除)
- 新增 `by_user()`(LEFT JOIN users;未知使用者顯示為 `null`)
- `app/schemas/stats.py` 加 `ProjectStatItem` / `UserStatItem`
- `app/api/v1/stats.py`:`_resolve_dept` 改為 `_resolve_filters`(三維一次過濾);4 個既有 endpoint 加 query params;新增 `GET /stats/by-project` 與 `GET /stats/by-user`

**新端點**:
- `GET /api/v1/users/dropdown`(`UserDep`,non-admin 強鎖自己部門;admin 可不傳取全公司或傳 `department_uid` 過濾)— 免分頁、預設 limit 2000;只回精簡欄位 `user_uid / username / employee_id / department_uid`
- `UserRepository.list_for_dropdown()` 對應方法

**前端**:
- `types/api.ts` 加 `StatsByProject` / `StatsByUser` / `UserDropdownItem`;`UsageLog` / `StatsByDepartment` 補對應欄位
- `lib/api/endpoints.ts` 加 `statsByProject` / `statsByUser` / `usersDropdown`
- `lib/api/error-map.ts` 加 `project_id_required` / `project_invalid` 中文化
- 新元件:
  - `components/feature/stats/ByProjectBar.tsx`(抄 DeptTokensBar)
  - `components/feature/stats/ByUserBar.tsx`(抄 DeptTokensBar)
  - `components/feature/stats/DashboardFilters.tsx`(三個 select + 隨選定部門限縮專案/使用者選項;non-admin 部門固定顯示為 badge)
- `app/(main)/dashboard/page.tsx` 重寫:加 filters state、6 個 stats 呼叫都帶上 filters、新增 ByProjectBar / ByUserBar 行

**文件**:
- `docs/INTEGRATION.md` § 2 / § 4 / § 7 / § 8 同步加 `X-Project-Id` header 與 2 個新錯誤碼
- `frontend user-guide page`:憑證 grid 改 3 columns、HTTP 範例 / curl / Python 加 header、錯誤碼表加新條目
- 補寫 `docs/Tasks/v1.3/propose-v1.3.0.md` 與 `docs/Tasks/v1.4/propose-v1.4.0.md`(原版本未撰寫,本次一併追溯)

### Out of Scope

- **預算管理**(部門 / 專案的月預算、超支警告、警告通知)→ 留待 v1.6+ 視業務需求
- **SDK Key 綁專案**(本版 SDK Key 仍只綁部門;一把 Key 可呼叫同部門任一專案;若未來需要「一把 Key 只能用一個專案」再延伸)
- **User Token 內嵌 project**(維持 stateless,不更動既有 token 結構;呼叫者不需重發 token 就能用新功能)
- **自助查詢 project 清單端點**(`/api/v1/sdk/projects`)— admin 直接告知 project_uid 即可,需求出現再加
- **使用者綁專案**(使用者仍只綁部門,一人可跨多個專案)
- **既有 deprecated alias `/model/openrouter/chat`** 的變更
- **v1.3 / v1.4 補 tasks 檔**:只追溯 propose;tasks 為實作契約,事後補無意義

## 4. 流程概要

```
SDK ─POST /api/v1/model/chat──────────▶ chat handler
                                         │  (require_sdk_caller)
                                         │
                                         │ 1. 解析 X-SDK-Key / X-User-Token / X-Project-Id
                                         │    缺任一 → 401 / 400 project_id_required
                                         │ 2. 驗證 SDK Key 有效、User Token 解密 + dept 一致
                                         │ 3. 驗證 project_uid 屬於 SDK Key 的部門 + is_active
                                         │    失敗 → 400 project_invalid
                                         │
                                         ▼
                                  run_chat(department_uid, project_uid, user_uid, model, ...)
                                         │
                                         ├─ provider=openrouter → existing flow
                                         └─ provider=internal   → existing flow
                                         │
                                         ▼
                                  schedule_usage_log(..., project_uid=...)
                                         │
                                         ▼
                                  INSERT INTO usage_logs (..., project_uid)
```

儀表板:

```
admin / non-admin
   │
   └─ Dashboard 頁
       │
       ├─ DashboardFilters(部門 / 專案 / 使用者 三層 select)
       │     │
       │     ├─ admin:部門可任選「全部」與具體值;選後 projects/users 下拉自動限縮
       │     └─ non-admin:部門固定為自己;只能在自己部門裡選 project / user
       │
       └─ 6 個 stats API(overview / by-dept / by-model / by-project / by-user / timeseries)
              │
              └─ 全部帶上 {department_uid, project_uid, user_uid} 三維篩選
```

## 5. 既有資料相容

- 既有 `usage_logs` 紀錄(v1.0 ~ v1.4 寫入的)`project_uid` 為 `NULL`
- 在 `overview` / `by_department` / `by_model` / `timeseries` 視圖中**仍包含**(因為總量不應憑空消失)
- 在 `by_project` 視圖中**自然排除**(INNER JOIN projects);這是「依專案分組,無專案的不出現」的合理行為
- 在 `by_user` 視圖中**仍包含**(LEFT JOIN users),極少數無 user 的歷史紀錄會顯示為 null
- 不回填、不遷移既有資料(回填需要管理員人工判斷哪個專案對應哪筆呼叫,成本不對等)

## 6. 後續可考慮(留待後續版本)

- 預算管理 + 超支警告(月 budget USD + 軟性提醒 → v1.6 候選)
- 自助查詢 project 清單端點(`GET /api/v1/sdk/projects` 帶 SDK Key 即可查)
- 儀表板加「依時間 × 專案」二維 timeseries(目前 timeseries 只有單一序列)
- SDK Key 綁特定 project(更嚴格的隔離)
