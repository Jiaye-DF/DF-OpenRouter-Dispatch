[//]: # (此檔為 v1.9.1 任務提案,實作前先由使用者確認範圍與設計取捨。)

# Propose v1.9.1 · 申請單狀態流轉 + 規則路由 + AI 欄位驗證自動開通

> 此為 **proposal**(規劃草案),確認後即轉為正式 `tasks-v1.9.1.md`。
>
> 對應母本:[v1.9.0 API Key 申請表單(送出 + 檢視)](./propose-v1.9.0.md)。

## 1. 目標

把 v1.9.0 只「送出 + 檢視」的申請單,擴充為**完整生命週期 + 自動開通**,採**規則路由 + AI 欄位驗證**的混合設計:

1. **申請單狀態流轉**(5 種狀態,見 § 4)。
2. **規則路由**(確定性,§ 5):依「部門 / 專案 / 使用者是否已存在」決定 自動候選 / 人工 / 系統取消。
3. **AI 欄位驗證**(§ 6):對「自動候選」的申請,由 **AI 判斷欄位內容是否正確/合理**(尤其 `project_url` 這類規則難寫的 GitHub/Replit 連結)。AI 通過 → 確定性程式**自動建立 專案 → 使用者 → SDK Key + User Token**(`agent_done`);AI 有疑慮 / 呼叫失敗 → 轉 `manual_pending`。
4. **內部 LLM 呼叫用 `DEFAULT_OPENROUTER_KEY`**(環境變數,既有 `config.DEFAULT_OPENROUTER_KEY`),經既有 `OpenRouterClient.chat_completion(...)`,**不**經 SDK proxy、不寫 usage_logs。

> **使用者已確認的方向(2026-06-17)**:
> 1. **路由走純規則**;**欄位正確性由 AI 判斷**(規則難寫,如 GitHub/Replit 連結是否有效/相符)。
> 2. AI 通過 → **自動執行寫入(呼叫既有建立 service)**;AI 有疑慮 / 新部門 → **人工**。
> 3. 既有實體 **idempotent 沿用**;**SDK Key 部門已有可用的就沿用**。
> 4. AI 內部呼叫一律使用 **`DEFAULT_OPENROUTER_KEY`**。

## 2. 動機

- v1.9.0 申請單送出後是死資料,管理員須手動建立部門/專案/使用者/金鑰,冗長易錯。
- **路由**(自動 / 人工 / 取消)是「部門/專案/使用者三個存在性布林值」的函數,純規則即可決定。
- 但**欄位是否正確**(例:`project_url` 是否真的是有效、且與專案相符的 GitHub/Replit 連結)**用規則很難寫**,正是 AI 的強項 —— 故以 AI 做欄位驗證閘。
- 三種資源建立在現有系統都已是確定性 service,LLM **只驗證、不寫入**,實際開通仍由確定性程式執行(安全)。

## 3. 範圍

### In Scope

- **規則路由引擎**(§ 5):依存在性把申請路由到 自動候選 / 人工 / 系統取消。
- **AI 欄位驗證**(§ 6):新增內部 LLM 呼叫(`DEFAULT_OPENROUTER_KEY` + 既有 `chat_completion`),對自動候選做欄位正確性結構化判斷。
- **自動開通(確定性執行,§ 7)**:沿用既有 service / repository,in-process 建立專案 → 使用者 → SDK Key + User Token,單一 transaction。
- **狀態流轉**(§ 4):取消 / 撤銷 / 人工處理端點與前端操作。
- **資料模型**(§ 8):擴充 `api_key_requests` 欄位 + migration `0013`。
- **API / 前端**(§ 9 / § 10)。
- **設定**:`DEFAULT_OPENROUTER_KEY`(既有)+ 新增 `API_KEY_AGENT_MODEL`(AI 驗證用模型,預設 `anthropic/claude-sonnet-4.6`)同步進 `.env.example` 與 `config.py`。

### Out of Scope

- **AI 直接 tool-calling 執行建立**:不採用;AI 只驗證,寫入永遠是確定性程式。
- **AI 介入路由 / 模糊比對部門**:路由純規則(部門以 `department_code` 精確比對),AI 不參與路由。
- **背景 job queue / 重試框架**:本版 AI 驗證 + 開通**同步**於送出請求內完成(單次 flash 呼叫,延遲可接受);正式佇列留待後續。
- **新部門的自動開通**:一律人工(需 OpenRouter 後台建 Key)。
- **URL 真實連線驗證 / 爬取內容**:本版 AI 做**合理性/相符性判斷**(連結是否像有效且對應專案);實際 HTTP 連線可達性檢查屬選配,留待後續(見 § 11 #2)。
- **通知(Email / 站內信)**:留待後續。

## 4. 狀態模型

申請單 `status`(對齊使用者指定的 5 種,**無過渡狀態**——同步處理):

| `status` 值 | 顯示 | 性質 | 說明 |
| --- | --- | --- | --- |
| `manual_pending` | 待人工處理 | 待辦 | 新部門 / AI 認為欄位有疑慮 / 既有專案下的新使用者,轉管理員 |
| `agent_done` | Agent 已處理 | 終態(成功) | AI 驗證通過 + 規則自動建立完成,已產生憑證 |
| `done` | 已處理 | 終態(成功) | 管理員人工建立完成 |
| `revoked` | 已撤銷 | 終態(取消) | 在**處理前**(`manual_pending`)由使用者 / 管理員撤回 |
| `cancelled` | 已取消 | 終態(取消) | 申請人自行取消(附原因)**或**系統判定重複(附自動原因) |

> **撤銷限制**:**一旦已處理(`agent_done` / `done`)即禁止撤銷**;撤銷僅允許於 `manual_pending` 階段。
>
> 「Agent 已處理」名實相符:本版 AI(Agent)確實參與了欄位驗證。

## 5. 規則路由(確定性,無 AI)

送出時(同步)依**決策樹**路由。三個存在性判斷:

- **部門存在?** `DepartmentRepository.get_by_code(department_code)`。
- **專案存在?** 同部門下有同名專案(`project_name`)。
- **使用者存在?** `UserRepository.get_by_email(owner_email)` 命中**唯一一筆**。

| 部門 | 專案 | 使用者 | 路由 | 終態 |
| --- | --- | --- | --- | --- |
| **新** | 任意 | 任意 | **人工**(需 OpenRouter 後台建 Key) | `manual_pending` |
| 舊 | 新 | 新 | **AI 驗證欄位**,信心 ≥95 則自動 | `agent_done`(否則降級 `manual_pending`) |
| 舊 | 新 | 舊 | **AI 驗證欄位**,信心 ≥95 則自動 | `agent_done`(否則降級 `manual_pending`) |
| 舊 | 舊 | 新 | **人工**(既有專案要加新成員,需人工確認) | `manual_pending` |
| 舊 | 舊 | 舊 | **系統取消**(重複申請) | `cancelled`<br>原因:**過去已存在相同 Key 資料** |

**等價決策樹**(實作落點:`services/api_key_request_router.py`):

```
if 新部門:           → manual_pending             # 需 OpenRouter 後台建 Key
elif 新專案:         → AI 驗證欄位 → confidence    # 舊部門 + 新專案(使用者新/舊皆可)
                         ├ confidence >= 95 → 自動開通 → agent_done
                         └ < 95 或 AI 失敗 → manual_pending(降級)
elif 新使用者:       → manual_pending             # 舊部門 + 舊專案 + 新使用者
else:                → cancelled                  # 舊部門 + 舊專案 + 舊使用者(重複)
                       cancel_reason = "過去已存在相同 Key 資料"
```

**確定性硬規則(AI 之外,先檢查)**:

- 既有部門 `name` 與申請 `department_name` 差異過大(代號命中但名稱對不上)→ 直接 `manual_pending`(防代號打錯誤開通到別的部門)。
- `owner_email` 命中**多筆**既有使用者 → 歧義 → `manual_pending`。
- `DEFAULT_OPENROUTER_KEY` 未設定 / 為空 → AI 不可用 → 自動候選一律退 `manual_pending`(優雅降級)。

## 6. AI 欄位驗證層

### 6.1 角色與輸出

AI **只驗證欄位、不寫入、不決定路由**。輸入申請 6 欄 + 命中的既有部門摘要,輸出結構化 JSON,**核心為單一信心分數**:

```json
{
  "confidence": 97,
  "reason": "簡短中文理由(供稽核/人工參考)"
}
```

- `confidence`:0–100 整數,代表「欄位內容正確/合理」的信心。
- 驗證重點:`project_url` 是否像**有效且與 `project_name` 相符**的 GitHub/Replit 連結;`owner_email` 網域是否合理;`department_name`/`department_code` 是否相稱;整體是否疑似亂填 / 濫用。
- **自動化門檻**:`confidence >= 95` → 進自動開通(§ 7,`agent_done`);**否則降級** → `manual_pending`。
- `confidence` 與 `reason` 全文存 `agent_decision`(§ 8)供管理員參考。

### 6.2 內部 LLM 呼叫

- 落點:新增 `services/api_key_request_agent.py`。
- 機制:`get_openrouter_client().chat_completion(payload, api_key=settings.DEFAULT_OPENROUTER_KEY)`,要求 JSON 結構化輸出(`response_format` / prompt 約束)。
- 模型:`settings.API_KEY_AGENT_MODEL`(預設 `anthropic/claude-sonnet-4.6`)。
- **與 SDK proxy 分離**:不需 SDK caller 身分、不寫 usage_logs、不過白名單(系統內部用途)。
- 失敗處理:LLM 逾時 / 非 2xx / JSON 不可解析 → 視為驗證未通過 → `manual_pending`,`error_message` 記錄(不讓申請卡死)。

## 7. 自動開通流程(確定性執行)

AI 驗證通過後,在**單一 DB transaction**內,沿用既有 service / repository:

| 步驟 | 動作 | Idempotency |
| --- | --- | --- |
| 1 部門 | 沿用既有(by `department_code`) | 必為既有(新部門不會走到此) |
| 2 專案 | 在部門下建立 `project_name` 專案(`code` 走 Snowflake) | 新專案(同名已存在不會走到此路徑) |
| 3 使用者 | 舊使用者 → 沿用(by email);新使用者 → 建立(`role=user`、`username=owner_name`、綁部門) | by `owner_email` |
| 4 SDK Key | 部門**已有可用 SDK Key → 沿用**;否則新建一把(名稱如「{project_name} 申請金鑰」) | 有就沿用(部門級) |
| 5 User Token | 為使用者發 User Token(重發即撤銷舊 token,既有行為) | — |

- 任一步失敗 → rollback → 轉 `manual_pending`(寫 `error_message`)。
- 產出的 **SDK Key 明文 / User Token / Project Code** 於送出回應帶回(顯示一次),並寫入 `provisioned_secrets` 供申請人在詳情頁**一次性領取後清空**(§ 8 / § 10)。
  - 沿用既有 SDK Key 時取其留存明文(`key_values`);若該既有 Key 無留存明文(v1.5 前舊資料),該欄留空並提示向管理員索取。
- 每步寫 `write_audit`(沿用既有 `create_project` / `create_user` / `create_sdk_key`),另記 `auto_provision_api_key_request`。

## 8. 資料模型異動(`api_key_requests`)

migration `0013_api_key_requests_lifecycle`,新增欄位:

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| `status` | String(16) | 擴充允許值(§ 4);既有 `pending` → migration 轉 `manual_pending` |
| `cancel_reason` | Text, null | 取消原因(申請人填,或系統自動「過去已存在相同 Key 資料」) |
| `cancel_source` | String(8), null | `user` / `system` |
| `handled_by_user_uid` | UUID, null | 人工處理的管理員 |
| `agent_decision` | JSONB, null | AI 欄位驗證輸出(`confidence` 0–100 + `reason`) |
| `error_message` | Text, null | AI 呼叫或自動開通失敗原因 |
| `created_project_uid` | UUID, null | 開通建立的專案 |
| `created_user_uid` | UUID, null | 開通建立 / 沿用的使用者 |
| `created_sdk_key_uid` | UUID, null | 開通建立 / 沿用的 SDK Key |
| `matched_department_uid` | UUID, null | 命中沿用的既有部門 |
| `provisioned_secrets` | JSONB, null | 一次性憑證(SDK Key 明文 / User Token / Project Code),領取後清空 |
| `processed_at` | DateTime(tz), null | 進入終態的時間 |

> `provisioned_secrets` 存敏感明文,屬一次性領取:領取後即 `NULL` 覆寫(對齊「金鑰只顯示一次」與法務考量)。

## 9. API 端點(新增 / 擴充)

| Method | Path | 權限 | 說明 |
| --- | --- | --- | --- |
| `POST` | `/api-key-requests`(擴充) | 本人 | 送出即同步跑 路由 → AI 驗證 → 開通;agent_done 於回應帶回憑證 |
| `POST` | `/api-key-requests/{uid}/cancel` | 本人 | 取消(附 `cancel_reason`,`cancel_source=user`);限 `manual_pending` |
| `POST` | `/api-key-requests/{uid}/revoke` | 本人 / admin | 撤銷;**限 `manual_pending`**,已處理(`agent_done`/`done`)回 `409` 禁止 |
| `POST` | `/api-key-requests/{uid}/process` | admin | 人工處理:確定性開通 → `done` |
| `GET` | `/api-key-requests/{uid}` | 本人 / admin | 詳情(狀態、AI 驗證結果、可領取的一次性憑證) |
| `POST` | `/api-key-requests/{uid}/claim-secrets` | 本人 | 領取一次性憑證後清空 `provisioned_secrets` |

- 既有 `GET /api-key-requests`(列表)不變,回傳含新 `status`。

## 10. 前端設計

- **列表**:狀態 badge(待人工處理=warning、Agent 已處理/已處理=success、已撤銷/已取消=secondary)。
- **申請人視角**:
  - 送出後若被自動開通 → 立即在回應 / 詳情頁**一次性領取**憑證(SDK Key / User Token / Project Code)。
  - 若 AI 信心分數 < 95 → 顯示「待人工處理」(附 AI 的 `reason` 與分數)。
  - 若為重複(系統取消)→ 顯示取消原因「過去已存在相同 Key 資料」。
  - `manual_pending` 可**取消**(彈窗填原因)或**撤銷**(二次確認);**已處理後禁止撤銷**。
  - 送出採 loading 狀態(同步含一次 AI 呼叫,約數秒)。
- **管理員視角**:「待人工處理」清單可開**人工處理**(檢視申請 + AI 的 `agent_decision`/issues → 一鍵確定性開通或調整後建立);新部門案在此完成。
- 沿用既有元件(Dialog / Table / Badge / LoadingButton / showDialog / toast)。

## 11. 權限與稽核 / 設計取捨

### 權限與稽核

- 取消 / 領取憑證:**僅申請本人**。撤銷:本人或 admin(限 `manual_pending`)。人工處理:**僅 admin**。
- 稽核 action 新增:`cancel_api_key_request` / `revoke_api_key_request` / `process_api_key_request` / `auto_provision_api_key_request`;子資源沿用既有 `create_*`。

### 已決議(2026-06-17)

- **AI 角色**:只做**欄位正確性驗證**(規則難寫的 `project_url` 等),不寫入、不決定路由;內部呼叫用 **`DEFAULT_OPENROUTER_KEY`**。
- **AI 輸出 + 自動化門檻**:回傳**單一信心分數 `confidence`(0–100)**;**`confidence >= 95` 才自動化**,否則降級走人工。
- **AI 驗證模型**:`anthropic/claude-sonnet-4.6`(`API_KEY_AGENT_MODEL` 可調)。
- **狀態命名**:維持「**Agent 已處理**」(`agent_done`)。
- **撤銷規則**:已處理即禁止撤銷;僅限 `manual_pending`。
- **SDK Key 策略**:部門已有可用 Key → **沿用**;無才新建。
- **既有部門名稱一致性檢查**:名稱與代號對不上 → 轉人工。
- **一次性憑證傳遞**:送出回應帶回 + 詳情頁一次性領取後清空。
- **「舊專案」判定鍵**:同部門 + 同 `project_name`。

### 待使用者確認

1. **是否要 URL 真實連線檢查**:本版 AI 只判斷「看起來是否有效/相符」,不實際連線。是否需另加一個確定性 HTTP 可達性檢查(或給 AI web 工具)?(建議:本版先不做,留後續)
2. **同步 vs 背景**:本版 AI 驗證 + 開通同步於送出請求(約數秒 loading)。是否接受?(若日後量大再改背景處理)
