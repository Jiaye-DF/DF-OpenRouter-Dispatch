# UI / UX 規範

樣式、主題、共用元件的視覺與互動規則。

> 元件工程結構（目錄、命名）參閱 [10-frontend.md](10-frontend.md)

---

## 整體風格

- 全站統一 `rounded-xl`（卡片、按鈕、輸入框、Dialog 等）
- 可點選元素**必須**加 `hover:cursor-pointer`
- 間距一律使用 Tailwind spacing scale（`p-4`、`gap-6`），不用任意數值

---

## 佈景主題

### 架構：系列（Series） + 主題（Theme）

兩層結構（系列 + 成員），為多系列擴充與使用者自訂主題預留彈性。

```ts
interface ThemeColors {
  background: string;
  foreground: string;
  primary: string;
  accent: string;
  // 其他項依 globals.css 擴充
}

interface ThemeItem {
  id: string;                   // builtin 如 'light'，user 如 'custom-<uuid>'
  labelZh: string;              // 中文主標
  labelEn: string;              // 英文副標
  icon: string;                 // Unicode 符號或 SVG 路徑
  colors: ThemeColors;          // 宣告式配色（thumb 繪製與自訂注入共用）
  source: 'builtin' | 'user';
}

interface ThemeSeries {
  key: string;                  // 'atmosphere' / 'gemstone' / 'user-custom'
  labelZh: string;
  labelEn: string;
  source: 'builtin' | 'user';
  items: ThemeItem[];
}
```

**關鍵原則**：

- 主題 `id` 一旦發布**不得改名**（綁 localStorage 值與 CSS 選擇器）
- 顯示欄位（`labelZh` / `labelEn` / `icon`）可隨時調整
- `colors` 為宣告式真相，須與 `globals.css` 對齊；`source: 'user'` 改以動態注入 `<html>` inline style，不寫入 CSS 檔
- `source: 'user'` 卡片右上角顯示「編輯 / 刪除」，`builtin` 則無

### 首發系列：光影 Atmosphere（v1.2）

以「一日光影變化」為敘事軸，五個主題分別對應不同時刻氛圍：

| id | labelZh | labelEn | icon | 氛圍 |
| --- | --- | --- | --- | --- |
| light | 晨曦 | Dawn | ◐ | 清透白光 |
| cool | 霧境 | Nordic | ❅ | 清冷霧藍 |
| warm | 夕映 | Ember | ◉ | 暖陽餘暉 |
| purple | 暮霞 | Twilight | ✦ | 霞紫漸層 |
| dark | 深夜 | Midnight | ☾ | 靜謐黑墨 |

> `id` 沿用舊值以避免 localStorage 遷移；僅顯示名與 icon 為新命名。

### 擴充協議

- **同族擴充**：既有系列新增 `ThemeItem`
- **跨族擴充**：新增 `ThemeSeries`，Dialog 自動多一個分區
- **使用者自訂**（v1.2 不實作）：獨立系列 `user-custom`，`colors` 存 DB，套用時動態注入 `<html>` 的 CSS Variable，不污染 `globals.css`

### 實作方式

- 色彩一律走 `globals.css` 的 CSS Variables，元件內**禁止**寫死 hex 色碼，**亦禁止**以 hex 作為 CSS Variable fallback（如 `bg-[color:var(--color-success-bg,#dcfce7)]`）— 若 fallback 會生效就代表變數未定義，應補進 `globals.css` 而非元件
- 透過 `<html data-theme="<id>">` 切換（`light` = `:root`、`dark` = `.dark`、其餘 `[data-theme="<id>"]`）
- 偏好存 localStorage（key：`agents-platform-theme`），重新載入時自動套用
- **例外**：`app/global-error.tsx` 因 `globals.css` 未載入，允許 inline style + 中性色 hex（如 `#6b7280`）呈現純文字錯誤頁，不得含業務邏輯

### CSS Variable 一覽（必備）

每個主題（`:root` / `.dark` / `[data-theme="<id>"]`）**必須**完整定義以下變數，並於 `@theme inline` 區塊轉接給 Tailwind v4 的 `bg-[color:var(--xxx)]` 語法使用。新增主題時，少一個變數就讓元件 fallback hex 滲入，視同違反「禁止寫死 hex」。

| 類別 | 變數 | 用途 |
| --- | --- | --- |
| 基礎 | `--color-background` / `--color-foreground` | 頁面底色 / 主要文字 |
| 主色 | `--color-primary` / `--color-primary-hover` | 主要按鈕、連結、選中態 |
| 強調 | `--color-accent` / `--color-accent-hover` | 次要 CTA、徽章 |
| 容器 | `--color-card-bg` / `--color-border` | 卡片底色、分隔線 |
| 弱化 | `--color-muted` / `--color-muted-bg` | 次要文字、空狀態底 |
| 危險 | `--color-destructive` / `--color-destructive-hover` / `--color-error-bg` | 刪除按鈕、錯誤訊息底 |
| 成功 | `--color-success` / `--color-success-hover` / `--color-success-bg` | 完成徽章、高 confidence 指示 |
| 警告 | `--color-warning` / `--color-warning-bg` | 注意提示、中等 confidence 指示 |
| 資訊 | `--color-info` / `--color-info-bg` | 一般訊息、Info Dialog |
| 紫色 | `--color-purple` / `--color-purple-bg` / `--color-purple-border` | scope=project 徽章、跨層記憶 UI |
| Header | `--color-header-bg` | 頂部導航條底色 |
| Sidebar | `--color-sidebar-bg` / `--color-sidebar-hover` / `--color-sidebar-active` | 側邊欄三態 |
| 遮罩 | `--color-overlay` | Dialog / Drawer 半透明遮罩 |
| 輸入 | `--color-input-bg` / `--color-input-border` / `--color-input-focus` | 表單欄位 |
| 陰影 | `--color-shadow` | `shadow-sm` 等使用 |

> 「藍 / 金」狀態色（如 scope=session 用藍、scope=user 用金）目前以 Tailwind 內建 palette（`blue-50/700/200`、`amber-50/700/200`）呈現，跨主題視覺一致；若未來需主題化再升級為變數。

```css
/* globals.css 範例（需與 ThemeItem.colors 對齊） */
:root {                    /* id: light，晨曦 Dawn */
  --color-background: #ffffff;
  --color-foreground: #171717;
  --color-primary: #2563eb;
  --color-accent: #3b82f6;
}

.dark {                    /* id: dark，深夜 Midnight */
  --color-background: #0a0a0a;
  --color-foreground: #ededed;
  --color-primary: #60a5fa;
  --color-accent: #93c5fd;
}

/* 其餘主題 (cool / warm / purple) 以 [data-theme="<id>"] 同模式宣告 */
```

### 主題選擇 UI（ThemeSwitcher）

- Header 主題按鈕開啟 **Content Dialog**（`size = lg`），不用懸浮下拉（無法承載多系列擴充）
- Dialog 內以系列分區（垂直），各系列下為主題卡片 grid（`grid-cols-2` / `sm:grid-cols-3`）
- 卡片：色彩縮影 thumb（依 `colors.background` / `primary` / `accent` / `foreground` 動態繪製）+ `labelZh` / `labelEn` + `icon`，選中以 `ring-primary` 標示
- **即時套用**：點擊卡片即套用全頁，無需按確認
- **取消才回復**：按「取消」回復 Dialog 開啟前主題；ESC / 遮罩 / X 僅關閉，**保留**當前選擇
- 主題狀態 hook（`useTheme`）提供 `applyTheme(id)` 與 `revertTo(id)` 供 Switcher 使用
- `source: 'user'` 卡片右上角顯示「編輯 / 刪除」（v1.2 未實作）

---

## Header

Header 為全站共用，固定於頂部，結構如下：

```text
┌──────────────────────────────────────────────────────────────────┐
│  [☰] [SVG 圖示] Agents-Platform          [🎨] {Username} [登出] │
└──────────────────────────────────────────────────────────────────┘
```

- **左側**：Sidebar 切換（☰）+ SVG 圖示 + 「Agents-Platform」文字（點擊回主頁）
- **右側**：主題切換（🎨）+ `{Username}` + 登出
- 主題按鈕**不**採用懸浮下拉（無法承載多系列擴充與使用者自訂）；詳細行為見 [主題選擇 UI](#主題選擇-uithemeswitcher)
- Sidebar 按鈕循環三態：完整展開（圖示+文字）→ 收合（僅圖示）→ 完全隱藏
- `md` 以下 Sidebar 預設隱藏，點擊以 overlay 展開
- Header 高度固定，背景跟隨主題 CSS Variable
- `sm` 以下「Agents-Platform」文字隱藏，僅保留 SVG 圖示

---

## Sidebar

登入後頁面（`(main)` 群組）共用左側 Sidebar，承載主要導航。

### 三態循環

由 Header 漢堡按鈕控制：

| 狀態 | 寬度 | 顯示 |
| --- | --- | --- |
| expanded | `w-56` | 圖示 + 文字 + 分組 label |
| collapsed | `w-16` | 僅圖示（label 隱藏、分隔線保留） |
| hidden | `w-0` | 完全隱藏 |

`md` 以下預設 overlay 模式，點擊遮罩 / 選項自動關閉。

### 分組結構（Group + Item）

Sidebar 以「分組」承載，避免擴充後退化為單一平面列表、同類型項目混雜。

```ts
interface SidebarItem {
  label: string;
  href: string;
  icon: React.ReactNode;
  adminOnly?: boolean;
}

interface SidebarGroup {
  key: string;              // 'overview' / 'resources' / 'admin'
  label: string;            // 僅 expanded 顯示
  adminOnly?: boolean;      // 整組僅 admin 可見
  items: SidebarItem[];
}
```

### 首發分組（v1.1+）

| group key | label | adminOnly | 成員 |
| --- | --- | --- | --- |
| overview | 概覽 | 否 | 儀表板 |
| resources | 我的資源 | 否 | Agent 管理 / Skill 管理 / Script 管理 |
| admin | 系統管理 | 是 | 使用者管理 / 模型管理 / 模型分級 / 語言管理 / Agent 範本 / 系統設定 |

### 權限與顯示規則

- 整組 `adminOnly: true` 對非 admin **完全隱藏**（含 label 與分隔線）
- 項目層級 `adminOnly: true` 僅該項隱藏，所屬 group 與同組其他項維持
- `collapsed` 狀態：group label 隱藏，**分隔線保留**（維持視覺節奏）
- 選中態：`bg-sidebar-active` + `text-primary`，以 `pathname.startsWith(item.href)` 判定

### 擴充協議

- **加項目**：擴 `SidebarGroup.items`；語義不屬既有組則開新組
- **開新組**：擴 `SIDEBAR_GROUPS` 陣列，依語義插入適當位置
- **權限隔離**：敏感功能一律放 `admin` 組或標 `adminOnly`，**不可**與一般使用者功能混在同一組

---

## 頁面佈局

所有登入後頁面（`(main)` 群組）共用相同的 main section 佈局結構：

```text
Sidebar 展開：                          Sidebar 隱藏：
┌──────────────────────────────────┐    ┌──────────────────────────────┐
│             Header               │    │            Header            │
├────────┬─────────────────────────┤    ├──────────────────────────────┤
│        │       Page Title        │    │         Page Title           │
│Sidebar │ ┌─────────────────────┐ │    │ ┌──────────────────────────┐ │
│        │ │                     │ │    │ │                          │ │
│        │ │   Main Content      │ │    │ │      Main Content        │ │
│        │ │                     │ │    │ │                          │ │
│        │ └─────────────────────┘ │    │ └──────────────────────────┘ │
└────────┴─────────────────────────┘    └──────────────────────────────┘
```

- 每個頁面含 **Page Title** + **Main Content 卡片容器**（`rounded-xl` + 背景 + 陰影）
- 外層佈局由 `(main)/layout.tsx` 統一控制，**禁止**頁面自行定義

---

## Dialog 元件

- **禁止** `alert()` / `confirm()` / `prompt()`，一律走 Dialog 元件
- 透過共用 Hook / Store（如 `useDialog`）程式觸發，無須逐一引入元件
- 容器 `rounded-xl`

分兩族：**提示型**（Info / Warning / Error）承載訊息，**內容型**（Content）承載表單 / 選擇器。

### 提示型 Dialog

| 類型    | 用途           | 圖示/色調 | 預設按鈕    |
| ------- | -------------- | --------- | ----------- |
| Info    | 一般資訊告知   | 藍色      | 確認        |
| Warning | 需使用者注意   | 黃色      | 取消 / 確認 |
| Error   | 錯誤或失敗通知 | 紅色      | 確認        |

使用範例：

```typescript
const { showDialog } = useDialog();
showDialog({ type: "error", title: "操作失敗", message: "無法取得資料" });
```

### 內容型 Dialog（Content Dialog）

承載表單、選擇器、複雜流程：

- 結構：`title` + `children`（JSX slot）+ 動作列
- 尺寸 `sm` / `md` / `lg`（預設 `md`）
- 三段回調分工：
  - `onConfirm`：使用者按「確認」，套用並關閉（即時副作用情境可省）
  - `onCancel`：使用者按「取消」，由呼叫端明確回復副作用後關閉；缺省時「取消」按鈕不渲染
  - `onDismiss`：ESC / 遮罩 / X，僅關閉、**不**回復（保留當前狀態）
- `< sm` 自動轉底部滑出式（bottom sheet）

```typescript
const { showContentDialog } = useDialog();
// 即時套用 + 取消才回復
showContentDialog({
  title: "選擇主題",
  size: "lg",
  content: <ThemeChooser />,
  cancelLabel: "取消",
  onCancel: () => revertTo(originalTheme),  // 取消時回復
  // onDismiss 預設不提供即等同「保留當前選擇直接關閉」
});
```

---

## 篩選與排序 chip

列表頁的「範圍 / 屬性 / 排序」切換一律以 `<FilterChip>` 水平平鋪呈現，搭配前綴標籤指明作用面。

### 共用規則

- 元件：`frontend/src/components/ui/FilterChip.tsx`（小圓角、單選切換、`active` 以 `bg-primary` 實心背景標示）
- 布局：`flex flex-wrap items-center gap-2`，窄寬度自然 wrap
- 前綴標籤：`<span className="shrink-0 text-sm text-muted">{面向}：</span>`（例：`範圍：` / `可見性：` / `按時間：`）
- **禁用**升降箭頭（↑↓）與方向性英文（asc / desc） — 面向使用者一律以中文呈現

### 排序 chip 慣例

排序本質是「排序欄位 × 方向」兩軸組合，**全站一律採用「軸前綴 + 方向 chip」格式**，不分多軸 / 單軸場景，亦不再使用「最新 / 最舊」之類的雙 chip 短形式。

軸前綴與對應 chip 標籤對照：

| 軸（前綴） | chip 標籤（desc / asc） | 對應欄位 |
| --- | --- | --- |
| `按時間：` | 由新到舊 / 由舊到新 | `created_at` |
| `按收藏：` | 由多到少 / 由少到多 | `favorite_count` |
| `按熱度：` | 由多到少 / 由少到多 | `download_count` |

- **單軸場景**（admin 管理頁、個人資源管理頁等只關心時間軸的列表）：僅渲染 `按時間：` 一列，仍維持軸前綴 + 兩顆方向 chip 結構
- **多軸場景**（dashboard 公開頁籤等）：每軸獨立一列，軸間以縱向堆疊（`flex flex-col gap-2`）；同頁只能同時選中**一個 chip**（跨軸單選），切換軸 = 切換排序欄位，切換方向 = 切換 order
- 後續加新維度（如「按建立者」）時，延伸同樣「`按X：` + 兩顆方向 chip」結構即可

### 放置位置

- 類型 / 範圍頁籤**下方**
- 搜尋框 + 作者 filter **下方**
- 列表上方
- 切換類型或範圍時**保留當前排序選擇**（不重置），重新進頁面才重置為預設值

### 範例參考

- 單軸：`frontend/src/app/(main)/admin/models/page.tsx`、`/agents`、`/skills`、`/scripts` 個人管理頁（皆為 `按時間：[由新到舊] [由舊到新]`）
- 多軸：`frontend/src/app/(main)/dashboard/page.tsx`（按時間 / 按收藏 / 按熱度，三列縱向堆疊）

---

## 表單驗證回饋

- 欄位錯誤：即時顯示於欄位下方（紅色文字）
- 伺服器錯誤：以 Error Dialog 呈現
- 送出按鈕請求期間顯示 loading 並禁用

---

## 響應式設計（RWD）

**Mobile First**，採 Tailwind 預設斷點：

| 斷點 | 寬度      | 佈局變化                      |
| ---- | --------- | ----------------------------- |
| 預設 | < 640px   | 單欄、Sidebar 為漢堡選單      |
| `sm` | >= 640px  | 單欄、間距微調                |
| `md` | >= 768px  | Sidebar 展開、雙欄            |
| `lg` | >= 1024px | Main Content 加寬             |
| `xl` | >= 1280px | 最大寬度、置中；多欄表格切卡片 |

- `md` 以下 Sidebar 收為漢堡選單，點擊以 overlay 展開
- 多欄表格（Admin 管理頁等）< `xl` 一律改為卡片式，>= `xl` 才顯示表格；表格儲存格以 `whitespace-nowrap` 保持單行水平顯示
- 觸控區域至少 44x44px（a11y）

### 斷點選擇原則：寧可提前，不可滯後

UI 實際跑版的寬度**不一定對齊** Tailwind 的預設斷點（640 / 768 / 1024 / 1280 / 1536）。當某個 layout 在兩個斷點之間就已斷裂時，**必須選擇大於等於該寬度的斷點做切換**，而不是等到下一個預設斷點才處理。

| 跑版發生於 | 正確做法            | 錯誤做法                  |
| ---------- | ------------------- | ------------------------- |
| 約 900px   | `lg:` (>= 1024) 切換 | `md:` (>= 768) 切換        |
| 約 1100px  | `xl:` (>= 1280) 切換 | `lg:` (>= 1024) 切換       |
| 約 1400px  | `2xl:` (>= 1536) 切換 | `xl:` (>= 1280) 切換       |

**Why**：若選較小斷點，會讓使用者在「跑版區間」（如 1024–1100px）看到實際已經擠壓變形的 layout；改選較大斷點雖然讓 desktop-grade UI 的啟用門檻提高，但在中間區段看到的是保守但乾淨的 mobile/tablet 版本，不會卡在中間態。

**適用場景**：桌面表格 ↔ 手機卡片、多欄 grid 收合、Sidebar 顯隱、字級縮放，所有需要在不同寬度呈現不同 layout 的情境。

---

## Loading 狀態

- 頁面級：全頁 Skeleton 或 Spinner
- 元件級：局部 Skeleton，避免整頁閃爍
- 按鈕：操作中顯 Spinner 並禁用