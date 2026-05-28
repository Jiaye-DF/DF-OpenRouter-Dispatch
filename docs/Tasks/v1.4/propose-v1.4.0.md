# Propose v1.4.0 · 部署與 UX 維護修正集

> 此為**追溯補寫的 proposal**(原版本實作落地時未撰寫 spec,本檔依 git 歷史回填,方便後續維護)。
>
> 對應母本:[v1.3 DF-SSO 整合](../v1.3/propose-v1.3.0.md)。

## 1. 目標

無單一主軸的維護版本 — 集合 v1.3 上 production 後浮現的部署、UX、文件層面修正,以及 SSO 整合的延伸增量。**不包含任何破壞性 schema 變更或 API 變更**。

涵蓋的 commit:

| Commit | 類型 | 主題 |
|---|---|---|
| `75fdf03` | Modify | 表格水平滾動 + 操作欄移至每列最前 |
| `8d9b159` | Modify | `.env.example` 結構重整為 `[BOTH]/[LOCAL]/[REMOTE]/[COOLIFY]`、修正前端 build-time 注入 |
| `9c8ae63` | Modify | SSO 登入後 Actor.username 顯示對應使用者姓名 |
| `460ad4b` | Fix | postgres 加 healthcheck,避免 alembic 競態啟動失敗 |
| `91cdae4` | Modify | 填入實際 API Base URL + 使用者建立支援 Email 多網域選擇 |

## 2. 動機

- **75fdf03**:後台多張表格欄位過寬時,內容會被擠壓或自動換行影響可讀性;操作欄在最後一欄需向右捲才能點到,動線冗長。
- **8d9b159**:`.env.example` 在 v1.0~v1.3 不斷加新區段,順序與作用域混亂;前端 `NEXT_PUBLIC_API_BASE_URL` 因為是 build-time 注入,在 Coolify build 階段沒帶入導致 bundle 內為空字串。
- **9c8ae63**:v1.3 SSO 登入完成後,Actor.username 顯示的是本地 `users.username`(常為 `admin`),而非 SSO 中央的本人姓名,在多管理員場景無法分辨「誰在操作」。
- **460ad4b**:production 部署觀察到 alembic 容器常因 postgres 尚未 ready 而第一次啟動失敗,雖會自動 restart 但會留下 false-positive 錯誤紀錄。
- **91cdae4**:v1.2 釋出時 INTEGRATION.md / user-guide 頁面留有「(待補)」占位網址;同時部分使用者 Email 是 `@df-recycle.com.tw`(而非 `@df-recycle.com`),建立使用者時硬編碼後綴無法相容。

## 3. 範圍

### In Scope

**前端 UX(`75fdf03`)**:
- `components/ui/table.tsx` 的 `TH` / `TD` 加 `whitespace-nowrap`,長文字不換行改由外層水平捲動
- 7 個管理頁(`users` / `sdk-keys` / `departments` / `projects` / `internal-keys` / `openrouter-keys` / `model-tiers`)的操作欄從最後一欄移到第一欄

**環境變數結構(`8d9b159`)**:
- `.env.example` 改以 `[BOTH]` / `[LOCAL]` / `[REMOTE]` / `[COOLIFY]` 註記每個變數的適用環境
- `frontend/Dockerfile` builder stage 加入 `NEXT_PUBLIC_API_BASE_URL` 的 `ARG` + `ENV`,讓值能在 build 階段內聯進 client bundle
- `docker-compose-prod.yml` frontend `build.args` 帶入 `NEXT_PUBLIC_API_BASE_URL`

**SSO 顯示名稱(`9c8ae63`)**:
- `require_user` 依新增的 `sso_display_name` cookie 決定 `Actor.username`(SSO 登入顯示 SSO 本人姓名;帳密登入顯示本地 username)
- SSO callback 寫入該 cookie;refresh 延展;logout / 帳密 login 清除
- DB `users.username` 不變動
- `docs/Design-Base/70-auth.md` § 18.7 補上 cookie 規格

**Postgres healthcheck(`460ad4b`)**:
- `docker-compose-prod.yml` 加 postgres `healthcheck`(`pg_isready`)
- alembic / backend service 改 `depends_on.condition: service_healthy`

**API Base URL 與 Email 多網域(`91cdae4`)**:
- `docs/INTEGRATION.md` 填入測試 / 正式環境實際網址,範例同步替換 `<正式站網址>`
- `frontend/src/app/(main)/user-guide/page.tsx` 的 `TEST_API_BASE` / `PROD_API_BASE` 常數填入實際值;額外補上「查詢可用模型清單」(GET `/api/v1/models`)區塊
- `frontend/src/app/(main)/users/page.tsx` 建立使用者 Email 後綴改為下拉選單(`@df-recycle.com` / `@df-recycle.com.tw`)

### Out of Scope

- 任何 schema migration(本版完全不改 DB)
- API 路徑 / Request / Response 結構變更
- 新功能(專案串接、預算管理等都留待 v1.5+)
- 既有測試案例調整

## 4. 性質說明

本版定位為**「v1.3 上線後的穩定化版本」**:不引入新功能,只修部署與 UX 上的痛點;適合做為 v1.5 大型功能版本的前置 baseline。所有變更皆可獨立 cherry-pick / revert,彼此無相依。
