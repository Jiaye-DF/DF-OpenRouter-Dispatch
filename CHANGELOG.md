# CHANGELOG

對外 user-facing 變更紀錄,對齊 [Keep a Changelog](https://keepachangelog.com/zh-TW/) 簡化版。內部根因見各版本 `docs/Tasks/v*/fixed.md`;格式規範見 `docs/Design-Base/01-propose/06-changelog.md`。

> 本檔自 2026-06-25 導入,以下 v1.x 為**回溯彙整**(條目取自各 `propose-v*.md` 標題,日期待依 git 史補填)。v2.0 起 release 前即時維護。

## [Unreleased]

- (無)

---

## [v2.1.1] — 2026-07-07

### 新增(Added)
- 下載 Excel 全面對齊儀表板:新增「總覽 KPI / 專案×模型花費明細 / 依模型 / 時序」工作表(保留原部門 / 專案 / 使用者),**每個專案的花費可再依模型拆解**。
- 用量紀錄新增「所屬專案」欄與可搜尋的**專案篩選**,每筆呼叫看得出屬於哪個專案。

### 變更(Changed)
- 用量紀錄(列表 + 明細)由僅限管理員,開放給**一般使用者查看自身部門**的紀錄(用量即部門成本);無所屬部門的帳號不開放。
- `/api/v1/usage-logs` 回應新增專案欄位、列表支援專案篩選;新增 `/api/v1/stats/by-project-model` 彙總端點(向下相容)。

### 修復(Fixed)
- 修補授權邊界:無所屬部門的非管理員帳號原可能越權查看跨部門用量紀錄(含請求 / 回應內容),現一律拒絕。

## [v2.1.0] — 2026-06-29

### 新增(Added)
- **AI 判決總覽**(管理端):對 AI 推薦的模型以原本輸入**實際重跑一次**,把「原模型 vs 推薦模型」的真實輸出並排比較,附成本差額與 AI 對比裁決,讓「該不該換模型」有可驗證的依據。
- AI 判決總覽支援依編號排序與搜尋。

### 變更(Changed)
- AI 分析術語白話化(原模型 / AI 推薦模型 / 對比裁決)。

## [v2.0.0] — 2026-06-26

### 新增(Added)
- **AI 模型適配評審**:以多個評審模型(Claude / GPT / Gemini)對既有用量紀錄評分,推薦每筆請求「最適合的模型」;背景管線以 taskiq + Redis 週期執行。
- 後台可設定擔任評審的 3 個模型。
- 用量紀錄明細頁內嵌「AI 分析」區塊,顯示評審結果。
- 可設定 AI 分析**起始時間門檻**(只分析門檻後的資料,節省成本)。

---

## [v1.10.0]

### 變更(Changed)
- 申請表單欄位**下拉化**,降低人工配對落空。

## [v1.9.0]

### 新增(Added)
- API Key **申請表單**(送出 + 檢視)。
- 申請單**狀態流轉** + **規則路由** + **AI 欄位驗證自動開通**。
- 開通完成後**Email 通知**專案負責人(Microsoft Graph 寄信)。

## [v1.8.0]

### 新增(Added)
- 代理請求支援**檔案上傳(PDF 等)**。

## [v1.7.0]

### 新增(Added)
- 模型回應**串流(SSE)**支援(OpenRouter)。

## [v1.6.0]

### 新增(Added)
- 部門 + SDK Key **管理整合**,後台導引動線清理。
- Chat 代理支援**透傳 `tools` 參數**(server 端工具)。
- 用量紀錄加 **tools 標記** + 單筆 **Input/Output 詳情頁**。

## [v1.5.0]

### 新增(Added)
- **專案維度**串接 + 儀表板**多維度篩選**。

## [v1.4.0]

### 修復(Fixed)
- 部署與 UX 維護修正集。

## [v1.3.0]

### 新增(Added)
- **DF-SSO 單一登入**整合。

## [v1.2.0]

### 新增(Added)
- **本地(Internal)模型**支援(OpenAI-compatible 地端 server)。
- 平台**主動速率限制**(per-Key / per-Provider)。

### 變更(Changed)
- 代理 endpoint 收斂為 `/api/v1/model/<action>`(舊 `/model/openrouter/chat` 轉 deprecated alias)。

## [v1.1.0]

### 新增(Added)
- **Models 管理與同步**(DB 驅動白名單,取代環境變數 `ALLOWED_MODELS`)。

## [v1.0.0]

### 新增(Added)
- OpenRouter **中控派工平台**:集中管理金鑰、配額、路由與用量稽核。
- 代理端 **SDK Key + User Token 雙因子**認證(部門一致)。
- OpenRouter 原生 Key 僅存後端(AES-256-GCM 加密),禁下發前端。
