---
name: create-project-doc
description: 在任何專案內建立一份「單頁式專案說明文件 HTML」(對齊 DF-OpenRouter 派工系統說明文件的整體風格:漸層 Hero + 分區卡片式目錄 + PART 分隔橫幅 + 編號區塊 + 量化指標卡 + 分層架構 + 版本時間軸 + Mermaid 流程圖 + 有序步驟清單 + Playbook 情境標頭)到 docs/<name>-專案說明文件.html。文件採雙部結構(PART I 系統與技術設計 / PART II 維運操作手冊)。預設會**掃描專案結構**(技術棧/版本/API 端點/git 版本史)自動填客觀章節(架構/版本演進/API 總覽),主觀章節(摘要/目的/痛點/技術價值/維運手冊)留 placeholder 由使用者手填;也可選擇只 cp 模板手動填。當使用者說「建專案說明文件 / 產生說明文件 HTML / create project doc / 套這個文件風格」時觸發。
---

# create-project-doc

從本 skill 內建的 `_template/project-doc.html` cp 出一份新的單頁式專案說明文件到 `<cwd>/docs/<name>-專案說明文件.html`,風格對齊 `DF-OpenRouter-派工系統-專案說明文件.html`(自包含設計系統:單一 `<style>` + CSS 變數色票 + 全 class 化構件,零外部依賴,僅 Mermaid 走 CDN)。

文件採**雙部結構**(以 `.part-divider` 橫幅分隔,目錄以 `.toc-section-label` 分區):

- **PART I · 系統與技術設計**:摘要 / 目的 / 問題與效益 / 核心概念 / 流程圖 / 系統架構 / 版本演進 / 技術價值(§1–8)
- **PART II · 維運操作手冊**:以「有人來找你說 ___,你該怎麼做」情境為主 — 線上環境 / 登入後台 / 分頁導覽 / 維運核心觀念 / Playbook / 呼叫手冊 / API 總覽 / 故障排除 Runbook(§9–16)

PART II 多為運維脈絡(網址 / 操作動線 / 情境),**無對外維運需求的專案**(純函式庫 / CLI)可整個 PART II 刪除。

兩種模式:

- **scan 模式(預設推薦)**:掃描專案 → 偵測技術棧/版本/API/git 版本史 → LLM 寫入**客觀章節**(系統架構分層、版本演進時間軸、API 端點總覽、Hero 技術徽章);**主觀章節**(摘要/目的/問題與效益/核心概念/技術價值)留 placeholder 由使用者手填
- **raw cp 模式**:純 cp 模板 + 改 `<title>` 與 Hero 系統名,使用者完全手填

本 skill **不限定 Harness-Engineering 套用過的專案**,任何有實質結構的專案目錄都可跑。

## 設計系統(模板提供的可重用構件)

模板把整套風格集中在單一 `<style>`,以 CSS 變數定義色票(藍主色 + 綠/琥珀/紅語意色),所有構件 class 化:

| 構件 | class | 用途 |
| --- | --- | --- |
| 漸層 Hero | `header.hero` / `.kicker` / `.hbadge` | 版頭:分類標籤 + 標題 + 定位敘述 + 技術徽章列 |
| 分區卡片式目錄 | `nav.toc` / `.toc-section-label` / `.toc-item`(`.n`/`.tt`/`.ds`) | 兩欄編號導覽,以 `.toc-section-label` 分 PART |
| PART 分隔橫幅 | `.part-divider`(`.pk` / `h2` / `p`) | 深色漸層橫幅,分隔 PART I / II |
| 編號區塊 | `section` / `h2.sec .num` / `.sectlead` | 卡片化章節 + 編號標題 + 導言 |
| 文字層級 | `.hl` `.mk` `.em` `.key` `.rd` | 關鍵術語 / 螢光標 / 強調 / 注意 / 風險 |
| 量化指標卡 | `.metrics` / `.metric`(`.big`/`.ml`/`.ms`) | 1×4 成效數字 |
| 子卡 / 徽章 | `.grid.cols2/3` `.subcard` `.badge`(`.green`/`.amber`/`.gray`/`.red`) | 能力卡、概念卡 |
| 有序步驟清單 | `ol.steps`(CSS counter 編號方塊) | 操作步驟、規則清單 |
| Playbook 情境標頭 | `.playbook-head`(`h3` / `.ctx`) | 「情境 → 步驟」式維運手冊 |
| 表格 | `.table-wrap` + `table` | 條紋表,thead 灰底 |
| 程式碼 | `.codeblock`(`.lang` + `.k`/`.s`/`.c`) | 深色區塊 + 語法上色 |
| 提示框 | `.note`(`.info`/`.tip`/`.warn`/`.danger`) | 四色左框提示 |
| 純 CSS 流程 | `.flow-node`(`.accent`/`.ext`/`.store`) + `.arrow` | 橫向 / 縱向節點圖 |
| Mermaid 圖 | `figure.diagram` / `pre.mermaid` / `figcaption` | 序列圖 + 流程圖 |
| 分層架構 | `.layer`(`.lh`/`.lb`)+ `.chip` | 前端/後端/資料/外部分層 |
| 時間軸 | `.timeline` / `.tl-item`(`.milestone`) | 版本演進 |

模板預設 16 個章節 skeleton(分兩 PART,每章示範至少一種構件):

- **PART I**(§1–8):摘要 / 目的 / 問題與效益 / 核心概念 / 流程圖 / 系統架構 / 版本演進 / 技術價值
- **PART II**(§9–16):線上環境一覽 / 第一次登入後台 / 後台分頁導覽 / 維運核心觀念 / 常見需求 Playbook / 使用者呼叫手冊 / API 端點總覽 / 故障排除 Runbook

章節可依專案增減(整段刪 `<section>` 並從 `nav.toc` 移除對應項);純函式庫 / CLI 等無維運需求的專案可整個刪除 PART II(連同 `.part-divider` 與目錄 PART II 區)。

## 心法

1. **填寫模式分明**:scan 模式下,LLM 可寫**客觀章節**(架構分層/版本軸/API 表/Hero 徽章),但**必須先給使用者看偵測結果**讓他確認;raw cp 模式下,LLM **禁**寫任何章節內容
2. **主觀章節不由 LLM 偽造**:摘要 / 目的 / 問題與效益 / 核心概念 / 技術價值 需要業務脈絡(定位、痛點、價值主張、權限模型)— scan 模式下**永遠留 placeholder**,**禁**從 README 推測偽造痛點 / 效益數字 / 價值總結
3. **冪等不可逆**:cp 會落實體檔 — target 已存在時,**必須**用 `AskUserQuestion` 詢問處理,**禁**直接覆寫
4. **單一動作**:本 skill 只做「建一份說明文件 HTML」一件事,不跑 server / 不開瀏覽器 / 不 commit / 不裝套件
5. **掃描範圍受限**:只讀 manifest / config / 結構 / 公開 README / `.env.example` / git tag,**禁**讀真 `.env*`(非 example)/ 任何含密碼 hash / token 的檔
6. **輸出語言**:繁體中文(回應 / 註解 / commit message)
7. **保留設計系統**:`<style>` 區塊與 Mermaid init `<script>` **原封不動保留**(這就是「整體風格」)— 只改 body 內的內容,**禁**改 CSS class 名 / 色票 / Mermaid 設定
8. **AskUserQuestion 必有「推薦」選項**:首項標 `(Recommended)`,且 Recommended 必須 (a) 命中典型意圖、(b) 不造成不可逆 / 高破壞性後果(若典型意圖含覆寫既存檔,Recommended 退一階到「中止」或「改名」)

## 執行步驟

### 1. cwd 健全性檢查(寬鬆)

確認當前目錄是個專案(任一存在即可):`<cwd>/.git/`、`package.json`、`pyproject.toml`、`pom.xml`/`build.gradle`、`Cargo.toml`/`go.mod`、`composer.json`/`Gemfile`、`README.md`。

**完全空目錄** → **中止**,告知:「當前目錄看起來不是專案。請 `cd` 到實際專案根目錄。」

### 2. 收集文件名稱

用 plain text 詢問(自由輸入,不用 AskUserQuestion):

```
請輸入文件檔名前綴(例如 DF-OpenRouter-派工系統 / payment-platform / hr-overtime):
```

最終檔名 = `<cwd>/docs/<name>-專案說明文件.html`(沿用 DF-OpenRouter 既有命名)。

### 3. 衝突偵測

#### 3a. 確認 `<cwd>/docs/` 是否存在

不存在 → `mkdir -p <cwd>/docs`(可逆,無風險,直接做)

#### 3b. 確認 `<cwd>/docs/<name>-專案說明文件.html` 是否存在

存在 → 用 `AskUserQuestion`(Recommended = 中止):

- **中止 (Recommended)** — 不動既存內容
- **改用其他檔名** — 回到 § 2 重新詢問
- **覆寫(刪掉舊檔再 cp)** — ✱ 不可逆,需獨立再確認一次

### 4. cp 模板(永遠先放 baseline)

不管 § 6 模式選什麼,先 cp 模板做 baseline,確保 target 至少有完整 10 章 skeleton。

skill 安裝後路徑通常為 `~/.claude/skills/create-project-doc/`。

#### Windows / PowerShell

```powershell
Copy-Item "<skill-root>\_template\project-doc.html" "<cwd>\docs\<name>-專案說明文件.html"
```

#### macOS / Linux / bash

```bash
cp "<skill-root>/_template/project-doc.html" "<cwd>/docs/<name>-專案說明文件.html"
```

cp 完後 `ls` 確認檔案已建立。

### 5. 改顯示文字(永遠做,兩種模式都做)

| 位置 | placeholder | 改為 |
| --- | --- | --- |
| `<title>` | `<系統名稱> — 專案說明文件` | `<name> — 專案說明文件` |
| `header.hero` 內 `<h1>` | `<系統名稱><br><一句話副標>` | 實際系統名 + 副標(副標主觀則留 placeholder) |
| `footer.page` | `<系統名稱> · <一句話副標>` | 同上 |

> Hero 的 `.kicker` 與 `.lead`、其他 `<...>` placeholder 此時**先保留**:scan 模式由 § 8 改寫客觀章節,主觀章節維持 placeholder。

### 6. 模式選擇(AskUserQuestion)

Recommended = scan-and-fill(典型意圖,寫到新檔不毀既有):

| 選項 | 行為 |
| --- | --- |
| **掃描專案 + 自動填客觀章節 (Recommended)** | 進 § 7 掃描 → § 7c 給使用者確認 → § 8 寫入客觀章節(架構/版本/API/Hero 徽章);主觀章節維持 placeholder |
| **只 cp 模板(我自己填)** | 跳過 § 7 / § 8,直接 § 9 報告 |
| **中止** | baseline 已 cp(§ 4),不繼續寫入 |

### 7. 掃描專案(scan 模式)

#### 7a. 必讀檔(若存在)

- **語言 / 框架 / 版本**:`package.json`(deps + version)、`pyproject.toml`、`pom.xml`/`build.gradle`、`Cargo.toml`、`go.mod`、`composer.json`、`Gemfile`
- **資料庫**:`alembic/`/`prisma/`/`migrations/`/`*.sql`/`docker-compose.yml`(找 `image: postgres|mysql|mongo|redis`)
- **外部 client**:`src/clients/`/`src/integrations/`/`app/clients/`
- **環境變數線索**:`.env.example`(**只讀 example 檔**,**禁**讀真 `.env*`)
- **API 端點**:後端路由檔(FastAPI `APIRouter`、Express router、Spring `@RequestMapping`)/ OpenAPI 規格 / `docs/` 內既有 API 文件
- **版本史**:`git tag --sort=-v:refname`、`CHANGELOG.md`、`docs/` 內 `v*.md` / 版本提案文件
- **部署**:`Dockerfile`/`docker-compose.yml`/`.coolify/`/`Caddyfile`/`nginx.conf`
- **既有說明文件**:`README.md` / `docs/*.html`(若已有舊文,參考但不照抄)

#### 7b. 偵測產出表

整理成這張表(scan 結果)給使用者看:

```
| 維度 | 偵測結果 | 來源 |
| --- | --- | --- |
| Frontend | Next.js 15 + TypeScript | frontend/package.json |
| Backend | FastAPI + Pydantic v2 | backend/pyproject.toml |
| Database | PostgreSQL 17 | docker-compose.yml |
| 外部依賴 | OpenRouter / Microsoft Graph | backend/app/clients/, .env.example |
| API 前綴 | /api/v1/auth, /api/v1/users, ... | backend/app/api/ |
| 版本史 | v1.0 → v1.10 | git tag + docs/ |
| 部署 | Docker Compose + Coolify | docker-compose.yml + .coolify/ |
```

**禁**偽造偵測結果 — 沒看到的寫「未偵測」,不憑空想像。

#### 7c. 使用者確認(AskUserQuestion)

Recommended = 直接寫入(偵測結果可審,使用者已看過,寫入新檔不毀東西):

| 選項 | 行為 |
| --- | --- |
| **照這個結果寫入 (Recommended)** | 進 § 8 |
| **我先補充 / 修正後再寫** | 使用者用 plain text 列補充項,LLM 整合後重出 § 7b 表再次確認 |
| **不寫了,保留 baseline** | 跳到 § 9 報告 |

### 8. 寫入(scan 模式)

依 § 7c 確認的偵測結果,**只填客觀章節**,主觀章節維持 placeholder。

#### 8a. 客觀章節(LLM 依 scan 結果填)

- **Hero `.badge-row`**:用偵測技術棧填 `.hbadge`(框架 + 版本 + DB + 部署)
- **§ 6 系統架構**:依偵測層級填 `.layer` + `.chip`(前端 / 後端 / 資料與基礎設施 / 外部整合);偵測不到的層整層刪除,**禁**保留模板範例 chip
- **§ 7 版本演進**:依 git tag / CHANGELOG / 版本文件填 `.timeline`,首版 / 重大版用 `.tl-item.milestone` + `.badge.green`;無版本史則整章刪除
- **§ 14 呼叫手冊**(PART II):若有對外 API,依 OpenAPI / 路由填端點 `.codeblock` 與 Request / Response 欄位表;無對外 API 則整章刪除
- **§ 15 API 端點總覽**(PART II):依偵測路由 / OpenAPI 填分類表(分類 / 路徑前綴 / 說明);無後端 API 則整章刪除並從目錄移除
- **§ 5 流程圖**:若偵測到清楚的核心資料流 / auth 機制,可改寫 Mermaid 序列圖 / 流程圖;**不確定就留 placeholder**,**禁**杜撰流程

#### 8b. 主觀章節(維持 placeholder,不寫)

- **PART I 主觀**:§ 1 摘要、§ 2 目的、§ 3 問題與效益、§ 4 核心概念與角色、§ 8 技術價值
- **PART II 主觀**(整部多為運維脈絡):§ 9 線上環境(網址)、§ 10 登入後台、§ 11 分頁導覽、§ 12 維運核心觀念、§ 13 Playbook、§ 16 故障排除 Runbook

以上**全部維持 placeholder**。理由(對齊心法 § 2):這些需要業務定位、組織痛點、量化效益、權限模型、線上網址、操作動線、故障經驗 — 沒問清楚就寫等於猜。**禁**從 `.env.example` 推測線上網址。

LLM **可選擇性地**:把 §1 摘要與 footer 的系統名 placeholder 換成偵測到的專案名;其他主觀文字一律不動。

#### 8c. 章節 / PART 增減

- 模板 16 章為**上限範本**,非每個專案都需全部 — 沒有對應內容的客觀章節(如無 API / 無版本史)**直接刪該 `<section>` 並從 `nav.toc` 移除對應 `toc-item`**,重編號
- **純函式庫 / CLI / 無對外維運需求**的專案:可整個刪除 **PART II**(連同 `.part-divider`、§9–16 各 `<section>`、目錄 PART II 區),只留 PART I;此時 PART I 的 `.part-divider` 也可一併移除(單部文件)
- **禁**為了湊滿章節而保留空殼或杜撰內容

#### 8d. 預覽

寫入後,簡述「填了哪幾章、改成什麼樣子、刪了哪些章 / 是否保留 PART II」給使用者看,並**明確列出哪些章節是 placeholder 待填**,不必貼完整 diff。

### 9. 報告

不管走哪個模式,最後告知:

```
✓ 已建立 docs/<name>-專案說明文件.html

  <若 scan>已自動填:Hero 技術徽章、系統架構分層、版本演進時間軸、API 端點總覽（PART II）
  <若 scan>待手填(placeholder):PART I 摘要 / 目的 / 問題與效益 / 核心概念 / 技術價值；PART II 維運手冊（環境 / 登入 / 分頁 / Playbook / Runbook）
  <若 raw cp>全部 placeholder 待填
  <若刪 PART II>已移除 PART II（純函式庫 / 無維運需求）

下一步:
1. 用瀏覽器開啟 docs/<name>-專案說明文件.html(雙擊即可,Mermaid 圖會自動渲染)
2. 用 VSCode 編輯 <section> 內容,搜尋 < 與 > 包住的 placeholder 逐一替換
3. 文字重點用 class 標記:.hl(術語) .mk(螢光標) .key(注意) .rd(風險)
4. 維運步驟用 <ol class="steps">；Playbook 情境用 <div class="playbook-head">
5. 不需要的章節整段刪 <section> 並從 nav.toc 移除對應項;不需要 PART II 可整部刪除
6. 完成後 commit docs/<name>-專案說明文件.html
```

## 自我約束

- **scan 模式下**:LLM 可填客觀章節(架構 / 版本 / API / Hero 徽章),但 § 7c 必須先給使用者確認偵測結果;**禁**未確認直接寫入。主觀章節(摘要 / 目的 / 問題與效益 / 核心概念 / 技術價值)**留 placeholder**
- **raw cp 模式下**:LLM **禁**寫任何章節內容,只能 cp + § 5 改顯示文字
- **禁改** `<style>` 區塊(色票 / class 名 / 構件樣式)與 Mermaid init `<script>` — 那就是「整體風格」本身
- **禁讀**任何真 `.env*`(非 `.env.example`)/ 任何含 token / password / private key 的檔
- **禁**自動 commit / git add
- **禁**啟動 HTTP server / 自動開瀏覽器
- **禁**修改 `<cwd>` 既有檔案(除了 § 4 cp 的新 HTML)
- **禁**覆寫 target 已存在的檔而不問使用者(§ 3b 擋住)
- **禁**偽造 scan 結果 — 沒讀到的寫「未偵測」
- **禁**偽造主觀章節內容(痛點 / 效益數字 / 價值總結 / 權限模型)— 需業務脈絡,沒問清楚就寫等於猜

## 不做的事

- 不跑 `/scan-project`(那是偵測**問題清單**的 skill;本 skill 只產**說明文件**)
- 不裝套件 / 不跑 build(模板靠 CDN 載 mermaid.js)
- 不檢查 git 狀態(但會讀 git tag 作版本史素材)
- 不更新其他索引檔

## 與其他 skill 的關係

| Skill | 何時用 |
| --- | --- |
| `/create-arch-diagram` | 建**簡報式架構圖 bundle**(多張 slide,翻頁 + zoom)— 偏架構視覺 |
| `/create-project-doc`(本檔)| 建**單頁式專案說明文件**(摘要 → 架構 → 手冊 → 版本 → 價值的完整敘事)— 偏對外 / 對上說明 |
| `/analyze-project` | 純分析輸出(架構摘要 / 環境變數 / API 串接),不產 HTML |
| `/scan-project` | 偵測**問題清單**(env / security / 規範違反) |

## 內建模板維護

本 skill 內建的 `_template/project-doc.html` 是**單一分發源**(自包含,CSS + Mermaid init 全內嵌,不依賴任何外部目錄);風格對齊 `DF-OpenRouter-派工系統-專案說明文件.html`。

維護規則:

- **更新模板**:直接改 `Harness-Engineering/Skills/create-project-doc/_template/project-doc.html`
- **變更不影響既存文件**:既存 `docs/*-專案說明文件.html` 不會自動跟進;新模板只影響「之後新建」的文件
- **風格變動以參考實作為準**:色票 / class 約定 / 構件以 `DF-OpenRouter-派工系統-專案說明文件.html` 最新版為基準
