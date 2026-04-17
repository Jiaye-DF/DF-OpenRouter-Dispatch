# 10 · 前端基本設計

本文件定義前端（Next.js / React / Tailwind）不隨版本異動的基礎規範。技術棧版本詳見 [00-overview.md § 技術棧](./00-overview.md#技術棧)。

## 技術棧與套件

| 項目 | 選用 | 強制度 |
| --- | --- | --- |
| Framework | Next.js（App Router） | 必須 |
| UI Library | React | 必須 |
| 樣式 | Tailwind CSS | 必須 |
| 狀態管理 | Redux Toolkit | 必須 |
| 伺服器資料快取 | RTK Query | 必須 |
| UI 元件 | `shadcn/ui` + `lucide-react`（圖示） | 應 |
| 表單驗證 | `react-hook-form` + `zod` | 應 |
| 主題管理 | `next-themes`（支援 SSR-safe 切換） | 應 |

## 目錄結構

```
frontend/src
├── app/                    # App Router 頁面
│   ├── (auth)/             # 登入相關頁面群組
│   ├── (main)/             # 已登入後的主要頁面群組
│   ├── error.tsx           # 錯誤邊界（必須存在）
│   ├── global-error.tsx    # 全域錯誤邊界（必須存在）
│   ├── layout.tsx          # Root Layout（Theme Provider）
│   └── page.tsx
├── components/
│   ├── ui/                 # 基礎 UI（Button, Card, Dialog, ...）
│   ├── layout/             # Header, NavBar
│   └── feature/            # 業務元件（金鑰管理、用量統計、稽核等）
├── hooks/
├── lib/
│   ├── api/                # API Client、Response 型別
│   └── utils/
├── store/                  # Redux slices
└── types/
```

## 1. 深淺模式切換

- **必須支援** Light / Dark 兩種模式，首次造訪時跟隨系統偏好（`next-themes` 的 `defaultTheme="system"` 僅作初始值）。使用者點擊切換後即固定為 `light` 或 `dark`，**不再**提供獨立的 System 選項。
- 使用者選擇需**持久化**（`localStorage` key：`theme`），避免每次進站重設。
- 切換時**不得閃爍**（FOUC），`next-themes` 透過 `suppressHydrationWarning` + `<html>` class 的機制處理。
- Tailwind 使用 class 策略：`dark:` 前綴搭配 `<html class="dark">`。
- 所有自訂色彩**必須**在 `globals.css` 用 CSS variables 定義兩套（light / dark），**禁止**在元件內寫死 hex 色碼。

## 2. Header 設計

固定於頁面頂部（`sticky top-0 z-50`）。

**左側：**
- 專案簡寫名稱（例：`ORD` — OpenRouter Dispatch）
- 專案圖示（`lucide-react` 或自訂 SVG，大小 24×24）
- 點擊整個區塊導向 `/`

**右側功能欄：**

| 元件 | 說明 |
| --- | --- |
| 主題切換 | 圖示按鈕（Sun / Moon），點擊循環 `light → dark` 或展開選單 |
| 個人資訊 | 頭像 / 圖示按鈕，hover 或點擊顯示 Popover |
| 登出按鈕 | 紅色警示色、置於個人資訊 Popover 最下方（或獨立按鈕） |

**個人資訊 Popover 內容：**

```
┌──────────────────┐
│  Name            │  ← 第一行：粗體，較大字
│  user@domain.com │  ← 第二行：次要色，較小字
├──────────────────┤
│  登出            │
└──────────────────┘
```

- `Name` 與 `Email` 來自後端 `/api/v1/auth/me` 回應。
- 未登入時 Header 右側僅顯示「登入」按鈕與主題切換。

### 2.1 NavBar 與 Header 分離

Header 與 NavBar 為**獨立兩列**，職責不同：

| 元件 | 職責 | sticky 層級 |
| --- | --- | --- |
| `<Header>` | 品牌識別 + 主題切換 + 個人資訊 + 登出 | `sticky top-0 z-50` |
| `<NavBar>` | 路由導覽（依角色動態渲染 nav 項目） | `sticky top-[--header-h] z-40` |

**規則：**
- **禁止**將 NavBar 與 Header 合併回同一列。
- Header 的 z-index **必須**高於 NavBar，避免捲動時 NavBar 蓋到 Header 陰影。
- NavBar 背景使用 `bg-[rgb(var(--card))]`，底部加 `border-b` 與主內容區分隔。
- NavBar 項目以 `usePathname()` 判斷 active 狀態。

**響應式行為：**
- 桌面版：NavBar 全寬水平列。
- 手機版（`< md`）：NavBar 同為水平列，項目可橫向滾動。

## 3. 主要區域 Layout

- 主要內容區使用 `mx-12 my-8` 作為外距。
- 響應式：手機版（`< md`）改為 `mx-4 my-6`，避免內容過擠。
- 最大寬度 `max-w-screen-2xl`，居中對齊。
- 背景色使用 CSS variable（例 `bg-background`），確保深淺模式切換無縫。

```tsx
<main className="mx-4 my-6 md:mx-12 md:my-8 max-w-screen-2xl">
  {children}
</main>
```

## 4. 卡片式主題

- 所有資料呈現**必須**以 `Card` 元件為單位，避免純表格直接貼在背景上。
- `Card` 基本樣式：
  - 圓角 `rounded-2xl`
  - 陰影 `shadow-sm`（hover 可加 `hover:shadow-md` transition）
  - 邊框 `border border-border`（符合 shadcn/ui 規範）
  - 內距 `p-6`
- 卡片內部分區：`CardHeader` / `CardContent` / `CardFooter`。
- 列表類卡片可採用 Grid Layout（`grid gap-4 md:grid-cols-2 xl:grid-cols-3`）。

## 5. API 串接格式

後端統一 Response 結構詳見 [20-backend.md § 1 統一 Response 格式](./20-backend.md#1-統一-response-格式)。前端型別定義：

```ts
interface ApiResponse<T = unknown> {
  success: boolean;   // 業務是否成功
  code: number;       // HTTP 狀態碼或業務錯誤碼
  data: T | null;     // 成功時的資料
  detail: string;     // 面向使用者的簡要訊息
}
```

**前端 API Client 規範：**

- 統一封裝 `fetch`（或 `axios`）於 `src/lib/api/client.ts`，所有 request **必須**帶 `credentials: 'include'`（cookie 需跨埠送達）。
- Response 攔截：
  - HTTP 2xx 且 `success: true` → 回傳 `data`
  - HTTP 2xx 但 `success: false` → 丟 `ApiError`，由呼叫端決定是否 toast
  - HTTP 4xx / 5xx → 統一丟 `ApiError`，由全域攔截器呼叫 Dialog 顯示 `detail`
  - HTTP 401 → 自動導向 `/login`
- **禁止**在元件內直接 `fetch`；一律透過 `lib/api/*` 的函式。
- 伺服器資料（列表、詳細）**應**使用 RTK Query，避免自行處理 loading / error。
- **禁止**在前端直接呼叫 OpenRouter API，所有模型呼叫**必須**經由後端代理（見 [50-openrouter.md](./50-openrouter.md)）。

## 6. Dialog 與訊息提示

統一使用 `Dialog` 元件提供重要訊息，必須包含以下三種類型並搭配圖示（`lucide-react`）：

| 類型 | 圖示 | 圖示色 | 使用情境 |
| --- | --- | --- | --- |
| `Info` | `Info` | `text-blue-500` | 一般性提示、操作說明 |
| `Warning` | `AlertTriangle` | `text-amber-500` | 不可逆操作確認（例：刪除前確認） |
| `Error` | `XCircle` | `text-red-500` | API 失敗、權限不足、系統錯誤 |

**Dialog 規範：**

- 標題必須有對應類型的圖示（圖示在左、標題在右）
- 內容區顯示 `detail`（或業務錯誤訊息）
- 按鈕至少一個（`確認` / `關閉`）
- 不可逆操作需兩個按鈕（`取消`、`確定`），且 `確定` 為危險色
- Dialog **禁止**用於純成功通知（成功訊息請用非阻斷式的 Toast）

## 7. 其他前端規範

- **Loading 狀態**：按鈕在 pending 期間**必須** `disabled` 並顯示 spinner；列表載入使用 Skeleton 佔位。
- **Empty 狀態**：列表為空時顯示 `EmptyState` 元件（圖示 + 文案 + 可選動作按鈕）。
- **Toast**：非阻斷式提示（例：儲存成功）使用 Toast，置於右上或右下，自動消失 3 秒。
- **錯誤邊界**：`app/error.tsx` 與 `app/global-error.tsx` **必須**存在，避免白畫面。
- **無障礙（a11y）**：所有互動元件**必須**可 Tab 聚焦，Dialog **必須**支援 ESC 關閉，圖示按鈕**必須**有 `aria-label`。
- **i18n**：預設 `zh-TW`，若未來需要 `en-US` **應**預留 `next-intl` 或等效方案的結構。
- **環境變數**：前端僅能使用 `NEXT_PUBLIC_*` 前綴變數，**禁止**在客戶端讀取後端敏感設定（OpenRouter API Key、DB 連線等）。

## 8. 元件樣式原則

- 樣式以 Tailwind CSS 為主，**應**避免額外 CSS 檔案分散樣式來源。
- 全域狀態（登入資訊、使用者偏好、通知）統一由 Redux Toolkit 管理。
