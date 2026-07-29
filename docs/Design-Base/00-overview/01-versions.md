# 01-versions — 版本鎖定 + 套件清單

> **何時讀**:加套件 / 升版 / 啟動新版本。本檔為**版本 + 套件清單**的 single source,其他檔案**不重述**;禁裝 / 使用規則對應 `02-frontend` / `03-backend` / `04-databases` / `90-third-party-service`。
>
> **本檔已 re-baseline 為 DF-OpenRouter-Dispatch 目標棧**(Next 14.2 / React 18.3 / **Tailwind v4** / argon2id / Seq),非 HE 模板預設值的 React 19.2 / bcrypt(Tailwind 採 HE 的 v4)。採 HE「鎖到 patch、禁浮動版本」紀律,數字以本專案 lock file 為準。
>
> ⚠️ **Tailwind v4 升級**:本專案規劃自 v3.4 升 v4(2026-06-25 拍板)。本檔版本表已標 v4;**前端實際程式碼遷移**(`package.json` / PostCSS 設定 / `globals.css` 的 `@import "tailwindcss"` + `@theme`)為獨立 breaking-change 工作,須走 `docs/Tasks/v*/propose-v*.md` 評估後執行。

---

## 強制鎖定(硬底線)

| 項目 | 鎖定線 | lock 範例 |
| --- | --- | --- |
| Next.js | **`14.2.x`** | `14.2.15` |
| React / react-dom | **`18.3.x`** | `18.3.1` |
| Python | **`3.14.x`** | `3.14.0` |
| Node.js | 22.x LTS | `22.13.0` |
| PostgreSQL | 17.x | `17.2` |

跨 minor 升版(Next 14→15 / React 18→19 / Tailwind 4→5 / SQLAlchemy 2→3 / Python 3.14→3.15)→ 先寫 `docs/Tasks/v*/propose-v*.md` 評估 breaking,**禁**單一 commit 帶過。Python 3.14 下 `argon2-cffi` 為密碼雜湊主路徑(本專案**不**用 passlib/bcrypt)。

---

## 鎖定原則

- **禁**浮動版本(`^` / `~` / `*` / `latest`),最終以 lock file 鎖到 `MAJOR.MINOR.PATCH`。現行 `package.json` / `pyproject.toml` 仍用 `^` / `>=` 區間,**以 `package-lock.json` / `uv.lock` 的實際解析版本為準**;本表「lock 範例」逐步校正為 lock file 實際值。
- `engines.node` / `requires-python` 同樣鎖到 patch
- 服務版本於 `.env` 用 `<SERVICE>_VERSION` 變數,`docker-compose*.yml` 用 `${POSTGRES_VERSION}` 引用,**禁**直寫 image tag
- 升版**獨立 commit**:`(AI?) Modify: 升級 <套件> 從 <舊> 至 <新>(<理由>)`,同 commit 含本表 + lock file +(若涉)`.env`

---

## Frontend 套件(`frontend/package.json`)

> 本專案為 **Next.js (App Router) 單一路線**;HE 模板的 Vite 路線(`vite` / `react-router-dom` / `@tailwindcss/vite`)**本專案不採用**。

| 套件 | 鎖定線 | lock 範例 |
| --- | --- | --- |
| `next` | 14.2.x | `14.2.15` |
| `react` / `react-dom` | 18.3.x | `18.3.1` |
| `@types/react` / `@types/react-dom` | 18.3.x | `18.3.11` / `18.3.0` |
| `typescript` | 5.x | `5.6.2` |
| `@reduxjs/toolkit` | 2.x | `2.2.7` |
| `react-redux` | 9.x | `9.1.2` |
| `tailwindcss` | **4.x** | `4.0.0` |
| `@tailwindcss/postcss` | 4.x | `4.0.0`(Tailwind v4 的 PostCSS plugin;autoprefixer 已內建,v4 不需 `postcss` / `autoprefixer` 手動設定)|
| `next-themes` | 0.3.x | `0.3.0` |
| `react-hook-form` | 7.x | `7.53.0` |
| `zod` | 3.x | `3.23.8` |
| `lucide-react` | 0.45x | `0.453.0` |
| `clsx` / `tailwind-merge` | 2.x / 2.x | `2.1.1` / `2.5.2` |
| `recharts` | 2.x | `2.12.7` |
| `xlsx` | 0.18.x | `0.18.5` |
| `eslint` / `eslint-config-next` | 8.x / 14.x | `8.57.1` / `14.2.15` |

---

## Backend 套件(`backend/pyproject.toml`)

| 套件 | 鎖定線 | lock 範例 |
| --- | --- | --- |
| Python | 3.14.x | `3.14.0`(`requires-python = ">=3.14"`)|
| `fastapi` | 0.115.x | `0.115.x` |
| `uvicorn[standard]` | 0.32+ | `0.32.x` |
| `pydantic[email]` / `pydantic-settings` | 2.9+ / 2.6+ | `2.9.x` / `2.6.x` |
| `sqlalchemy[asyncio]` | 2.0.x | `2.0.35` |
| `asyncpg` | 0.30.x | `0.30.0` |
| `psycopg[binary]` | 3.2.x | `3.2.x`(Alembic migration 用 sync driver)|
| `alembic` | 1.14.x | `1.14.x` |
| `httpx` | 0.28.x | `0.28.x` |
| `argon2-cffi`(密碼雜湊主路徑) | 23.1+ | `23.1.x` |
| `pyjwt` | 2.10.x | `2.10.x` |
| `cryptography`(AES-256-GCM 加密 Key/Token) | 43.0+ | `43.0.x` |
| `uuid-utils`(UUIDv7) | 0.10.x | `0.10.x` |
| `python-multipart` | 0.0.12+ | `0.0.12` |
| `seqlog`(Seq 集中式 log) | 0.4.x | `0.4.3` |
| `boto3`(S3 物件儲存;**同步** SDK,呼叫必經 `asyncio.to_thread`) | 1.43.x | `1.43.58` |
| `botocore`(boto3 傳遞相依;`Config` timeout / retry 與 `stub.Stubber` 測試替身) | 1.43.x | `1.43.58` |
| `jinja2`(開通 / 通知信模板) | 3.1.x | `3.1.x` |
| `pytest` / `pytest-asyncio` / `pytest-cov` / `respx` | 8.x / 0.24+ / 6.x / 0.22.x | `8.3.x` / `0.24.x` / `6.0.x` / `0.22.x` |
| `ruff` / `mypy` | 0.8.x / 1.13.x | `0.8.x` / `1.13.x` |
| `uv`(唯一 package manager) | 0.5.x | `0.5.x` |

> 本專案**不**使用 `passlib` / `bcrypt`(改 `argon2-cffi` 的 argon2id);**不**使用 `loguru`(改 `seqlog` 送 Seq)。

---

## Sources of Truth

本檔「lock 範例」與下列 lock file 必**逐字一致**:

- `frontend/package-lock.json`
- `backend/uv.lock`
- `.env` 的 `<SERVICE>_VERSION`(例 `POSTGRES_VERSION=17.2`)

不一致時:**以 lock / `.env` 為準**,立即修本表。

---

## 升版流程

1. 升版理由(security / bug / 需求);**禁**「順手升一下」
2. 獨立 commit + 同 commit 含:本表 + lock file +(若涉)`.env*` / `docker-compose*.yml`
3. 跨 major(Next 14→15 / React 18→19 / Tailwind 4→5 / SQLAlchemy 2→3 / Python 3.14→3.15)→ 先寫 `docs/Tasks/v*/propose-v*.md` 評估 breaking,**禁**單一 commit 帶過
