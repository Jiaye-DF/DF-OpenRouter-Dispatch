# Tasks v1.4.0 · 部署與 UX 維護修正集

> 狀態:已完成(全數 done)。
>
> 母本 propose:[`propose-v1.4.0.md`](./propose-v1.4.0.md)(追溯補寫)。
> 本版定位為 **v1.3 上線後的穩定化版本**:不引入新功能,只修部署與 UX 痛點,**無任何 schema / API 變更**。各變更彼此無相依,可獨立 cherry-pick / revert。

## 版本資訊

- 前置依賴:v1.3.0(DF-SSO 整合)。
- 本版本範圍:表格 UX、`.env.example` 結構重整 + 前端 build-time 注入、SSO 顯示名稱、postgres healthcheck、API Base URL 與 Email 多網域。
- 對齊的 Design-Base 章節:
  - [`02-frontend/05-components.md`](../../Design-Base/02-frontend/05-components.md) · [`06-rwd.md`](../../Design-Base/02-frontend/06-rwd.md)
  - [`06-Coolify-CD/01-compose.md`](../../Design-Base/06-Coolify-CD/01-compose.md) · [`03-dockerfile-frontend.md`](../../Design-Base/06-Coolify-CD/03-dockerfile-frontend.md) · [`04-env-and-secrets.md`](../../Design-Base/06-Coolify-CD/04-env-and-secrets.md)
  - [`90-third-party-service/08-df-sso.md`](../../Design-Base/90-third-party-service/08-df-sso.md)(§ cookie 規格)

## 涵蓋 commit

| Commit | 類型 | 主題 |
|---|---|---|
| `75fdf03` | Modify | 表格水平滾動 + 操作欄移至每列最前 |
| `8d9b159` | Modify | `.env.example` 重整為 `[BOTH]/[LOCAL]/[REMOTE]/[COOLIFY]` + 修正前端 build-time 注入 |
| `9c8ae63` | Modify | SSO 登入後 `Actor.username` 顯示對應使用者姓名 |
| `460ad4b` | Fix | postgres 加 healthcheck,避免 alembic 競態啟動失敗 |
| `91cdae4` | Modify | 填入實際 API Base URL + 使用者建立支援 Email 多網域選擇 |

## Definition of Done

### 前端 UX(`75fdf03`)
- [x] `components/ui/table.tsx` 的 `TH` / `TD` 加 `whitespace-nowrap`,長文字不換行改由外層水平捲動
- [x] 7 個管理頁(`users` / `sdk-keys` / `departments` / `projects` / `internal-keys` / `openrouter-keys` / `model-tiers`)操作欄從最後一欄移至第一欄

### 環境變數結構(`8d9b159`)
- [x] `.env.example` 以 `[BOTH]` / `[LOCAL]` / `[REMOTE]` / `[COOLIFY]` 註記每變數適用環境
- [x] `frontend/Dockerfile` builder stage 加 `NEXT_PUBLIC_API_BASE_URL` 的 `ARG` + `ENV`(值於 build 階段內聯進 client bundle)
- [x] `docker-compose-prod.yml` frontend `build.args` 帶入 `NEXT_PUBLIC_API_BASE_URL`

### SSO 顯示名稱(`9c8ae63`)
- [x] `require_user` 依新增的 `sso_display_name` cookie 決定 `Actor.username`(SSO 登入顯示本人姓名;帳密登入顯示本地 username)
- [x] SSO callback 寫入該 cookie;refresh 延展;logout / 帳密 login 清除
- [x] DB `users.username` 不變動
- [x] [`90-third-party-service/08-df-sso.md`](../../Design-Base/90-third-party-service/08-df-sso.md) 補 `sso_display_name` cookie 規格

### Postgres healthcheck(`460ad4b`)
- [x] `docker-compose-prod.yml` 加 postgres `healthcheck`(`pg_isready`)
- [x] alembic / backend service 改 `depends_on.condition: service_healthy`

### API Base URL 與 Email 多網域(`91cdae4`)
- [x] `docs/INTEGRATION.md` 填入測試 / 正式環境實際網址,範例替換 `<正式站網址>`
- [x] `frontend/src/app/(main)/user-guide/page.tsx` 的 `TEST_API_BASE` / `PROD_API_BASE` 填實際值,並補「查詢可用模型清單」(GET `/api/v1/models`)區塊
- [x] `frontend/src/app/(main)/users/page.tsx` 建立使用者 Email 後綴改下拉(`@df-recycle.com` / `@df-recycle.com.tw`)

## Out of Scope(本版不做)

- 任何 schema migration(本版完全不改 DB)
- API 路徑 / Request / Response 結構變更
- 新功能(專案串接、預算管理等留待 v1.5+)
- 既有測試案例調整

## 交付物清單

| 動作 | 路徑 |
|---|---|
| 修改 | `frontend/src/components/ui/table.tsx` |
| 修改 | `frontend/src/app/(main)/{users,sdk-keys,departments,projects,internal-keys,openrouter-keys,model-tiers}/page.tsx`(操作欄移前) |
| 修改 | `frontend/Dockerfile`、`docker-compose-prod.yml`、`.env.example` |
| 修改 | `backend/app/core/deps.py`(`require_user` 讀 `sso_display_name`)、`backend/app/services/sso.py`(寫 cookie) |
| 修改 | `frontend/src/app/(main)/user-guide/page.tsx`、`frontend/src/app/(main)/users/page.tsx`、`docs/INTEGRATION.md` |
