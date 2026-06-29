# CHANGELOG

對外 user-facing 變更紀錄,對齊 [Keep a Changelog](https://keepachangelog.com/zh-TW/) 簡化版。內部根因見各版本 `docs/Tasks/v*/fixed.md`;格式規範見 `docs/Design-Base/01-propose/06-changelog.md`。

> 本檔自 2026-06-25 導入,以下 v1.x 為**回溯彙整**(條目取自各 `propose-v*.md` 標題,日期待依 git 史補填)。v2.0 起 release 前即時維護。

## [Unreleased]

### 新增(Added)
- **模型適配評審**(v2.0,規劃中):對既有用量紀錄做 AI 多評審(Claude/GPT/Gemini)+ 推薦模型真實重跑 + 人類裁決,產出每筆請求的「該用哪個模型最適合」與成本差額。

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
