# Tasks v1.10.0

## 版本資訊

- 前置依賴:**v1.9.x**(申請單生命週期 + 規則路由 + AI 欄位驗證自動開通 + 開通通知信)已完成併入 `main` / `development`。
- 本版本範圍:**申請表單欄位下拉化**,從輸入端降低送出值與系統主檔對不上、被打回人工的機率。本版聚焦「**專案負責人改 Combobox + 自動帶入信箱**」。
- 母本 propose:[`propose-v1.10.0.md`](./propose-v1.10.0.md)

> 本 Tasks 為**實作契約**;設計理由請參考母本。內容衝突以本檔為準。

## 本版固定決定

- **負責人清單來源**:**現有平台 member**(`GET /api/v1/users` 同源資料,SSO 首登自動建立);`username` = M365 顯示名、`email` = M365 信箱,從源頭確保名稱與 M365 一致。
- **不接 M365 目錄即時查詢**:不新增 Graph `User.Read.All`;清單僅含「登入過本平台」的 member(取捨見 propose §3)。
- **信箱欄位唯讀**:選取負責人後自動帶入 `owner_email` 並設唯讀,比照既有「部門 → 部門代號」模式,避免手打不一致。
- **新端點開放所有登入者**:`owner-options` 用 `UserDep`(非 admin-only),因申請表單由一般 member 填寫;排除系統管理員 `account='admin'`(與規則路由 `list_by_email` 一致)。

## Definition of Done

### DB / Migration

- [x] 無資料模型異動(沿用既有 `users` 表;不需 migration)。

### 後端 — 資料層 / Schema

- [x] `repositories/user.py`:新增 `list_owner_options(limit=2000)`,撈未刪除、啟用、具 Email 的使用者,排除 `account='admin'`,依 `username` 排序。
- [x] `schemas/user.py`:新增 `UserOwnerOption`(`username` + `email`,`from_attributes=True`)。

### 後端 — API

- [x] `api/v1/users.py`:新增 `GET /api/v1/users/owner-options`(`UserDep`,回傳 `username` + `email` 純陣列);路由宣告於 `/{user_uid}` **之前**,避免被路徑參數攔截。
- [x] Swagger(`/api/docs`):端點 summary 與回應自動同步。

### 前端

- [x] `types/api.ts`:新增 `OwnerOption`(`username` + `email`)。
- [x] `lib/api/endpoints.ts`:新增 `userOwnerOptions: "/api/v1/users/owner-options"`。
- [x] `app/(main)/api-key-requests/page.tsx`:
  - [x] 載入負責人清單(`owners` state + 一次性 effect)。
  - [x] `ownerOptions` memo(value = `email`,label = `名稱（信箱）`)+ `onSelectOwner`(同時帶出 `owner_name` / `owner_email`)。
  - [x] 「專案負責人」改 `Combobox`(可搜尋姓名 / 信箱);「專案負責人信箱」改唯讀自動帶入。

### 驗證

- [x] 前端 `tsc --noEmit` 無錯。
- [x] 後端 `py_compile` 通過(`users.py` / `schemas/user.py` / `repositories/user.py`)。

### 不做(v1.10.0 明確排除)

- M365 目錄即時查詢(Graph `User.Read.All`);含未登入者的完整人員清單。
- 其他申請表單欄位的下拉化(待後續盤點)。

## 交付物清單

- 後端修改:`repositories/user.py`、`schemas/user.py`、`api/v1/users.py`。
- 前端修改:`types/api.ts`、`lib/api/endpoints.ts`、`app/(main)/api-key-requests/page.tsx`。

## 對應 commit

- `(AI) Modify: 申請表單專案負責人改為 Combobox(取自平台 member),選取後自動帶入信箱;新增 owner-options 端點`
- 已併入 `development`、`main`(均 `--no-ff`),並推送 origin + df-it。
