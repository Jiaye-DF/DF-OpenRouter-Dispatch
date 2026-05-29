# Tasks v1.6.0

## 版本資訊

- 前置依賴:v1.5.0(專案維度串接 + 儀表板多維度篩選);v1.5.0 SDK Key 改可逆加密
- 本版本範圍:部門 + SDK Key 管理整合進「部門」單一頁;後台導引動線雜訊清理
- 對齊的 Design-Base 章節:
  - [10-frontend.md](../../Design-Base/10-frontend.md)
  - [11-ui-ux.md](../../Design-Base/11-ui-ux.md)
- 母本 propose:[`propose-v1.6.0.md`](./propose-v1.6.0.md)(包含設計推導與決議過程)

> 本 Tasks 為**實作契約**;設計理由與替代方案請參考母本 propose。內容若與 propose 衝突,以本檔為準。

## Definition of Done

### 後端

- [N/A] 本版本不動 DB schema、不新增 migration、不改變既有 API 形狀。

### 前端

#### Sidebar

- [x] `src/components/layout/Sidebar.tsx`:
  - 移除「存取金鑰」section 整段(底下只有 SDK Keys 一項,合進部門頁後此 section 失去意義)
  - 一併移除已不再使用的 `KeyRound` / `Server` icon import
  - 註解標註 v1.6 變更原因(舊書籤直打 `/sdk-keys` 仍可進入)

#### Departments 頁(主要改動)

- [x] `src/app/(main)/departments/page.tsx`:
  - 表格新增展開欄(最左、ChevronRight / ChevronDown);admin only;狀態以 `expanded: Set<department_uid>` 管理,不影響部門 row 排序與分頁
  - 表格新增右側「部門金鑰數量」欄(KeyRound icon + 數字);admin only
  - 展開後在原 row 下方插入 second row(`colSpan=7`)渲染 `<DepartmentKeysPanel>`,內容包含:
    - 該部門所有 SDK Keys mini-table:名稱 / 部門金鑰明文 / 啟停 badge / 刪除 icon
    - 部門金鑰明文欄:有 `key_values` 的 row 顯示完整明文 + 複製 icon;`key_values=null`(舊資料)的 row 顯示「(舊資料,請重新建立)」(v1.5 Fix 04 後改為純 TEXT `key_values` 欄儲存,admin 可在 DB 直接補)
    - 「+ 新增 SDK Key」inline 輸入框(支援 Enter 觸發);成功後一次性明文 Dialog
  - 進頁時批次拉一次 `/api/v1/sdk-keys?page=1&size=200`(admin only),前端依 `department_uid` group 為 `Record<department_uid, SdkKey[]>`;之後 SDK Key 操作(新增 / 啟停 / 刪除)用 `reloadKeys()` 重抓,不重抓部門列表
  - 「新增部門」對話框新增「主金鑰名稱」欄(預設 placeholder「{部門名稱} 主金鑰」),留空時送出 `${dept.name.trim()} 主金鑰`
  - 提交流程:
    1. `POST /api/v1/departments` 建立部門
    2. 成功後立刻 `POST /api/v1/sdk-keys` 建立第 1 把 key
    3. key 明文存入 `newKeyPlain` state,觸發既有的明文 Dialog 一次性顯示
    4. 新部門 row 預設展開(`setExpanded` add 該 UID),使用者可立即看到 row 下方的 key
    5. 若 step 2 失敗:顯示警告(部門已建立,但主金鑰建立失敗,請從 row 展開後手動補建);**不 rollback step 1**(rollback 需要刪除剛建的部門,使用者很可能就是想要繼續用,反而 UX 差)
  - 編輯部門邏輯維持不動(`first_key_name` 欄位編輯時不顯示)
  - 刪除部門邏輯維持不動(後端 4xx 已涵蓋「部門下還有啟用 Key / 專案 / 使用者」的擋下)
  - 複製 SDK Key 明文使用 `useToast()` 給「已複製部門金鑰」通知

#### SDK Keys 獨立頁

- [x] `src/app/(main)/sdk-keys/page.tsx`:**保留**,不從 sidebar 連過去;舊書籤直打網址仍能進來。本版本不刪檔。

#### User Guide

- [x] `src/app/(main)/user-guide/page.tsx`:
  - 錯誤碼表 `project_code_required` 描述移除「(v1.5+ 必填)」字串

### 文件

- [x] `docs/Tasks/v1.6/propose-v1.6.0.md`:任務提案(已建立並由使用者確認)
- [x] `docs/Tasks/v1.6/tasks-v1.6.0.md`(本檔):實作契約

### 驗證

- [x] `npm run type-check` 通過
- [ ] 手動驗證(待使用者執行):
  - admin 進部門頁:展開 row 可看到 SDK Keys、複製可用、新增 / 啟停 / 刪除 SDK Key 都能更新
  - 「新增部門」對話框「主金鑰名稱」欄留空 → 新建後 key 名稱為「{部門名稱} 主金鑰」
  - 「新增部門」對話框「主金鑰名稱」欄填值 → 新建後 key 名稱為使用者輸入值
  - 建立部門後明文 Dialog 自動彈出 + 複製可用 + 新部門預設展開
  - non-admin 進部門頁:看不到展開欄、操作欄、部門金鑰欄(維持原 v1.5 行為)
  - sidebar 已無「存取金鑰」section;直接訪問 `/sdk-keys` 路徑仍可進舊頁
