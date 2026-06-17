[//]: # (此檔為 v1.9.1 任務提案,實作前先由使用者確認範圍與設計取捨。)

# Propose v1.9.1 · 申請單狀態流轉 + 規則化自動建立部門/專案/使用者

> 此為 **proposal**(規劃草案),確認後即轉為正式 `tasks-v1.9.1.md`。
>
> 對應母本:[v1.9.0 API Key 申請表單(送出 + 檢視)](./propose-v1.9.0.md)。

## 1. 目標

把 v1.9.0 只「送出 + 檢視」的申請單,擴充為**完整生命週期 + 規則化自動開通**:

1. **申請單狀態流轉**(5 種狀態,見 § 4)。
2. **純規則自動開通**:申請進來後,依「部門 / 專案 / 使用者是否已存在」+ 確定性驗證,**自動路由**(見 § 5)。可自動者由確定性程式**自動建立 專案 → 使用者 → SDK Key + User Token**;新部門或有疑慮者轉人工。
3. **不接 AI**:路由與驗證皆為確定性規則,**不**使用 LLM(已於 2026-06-17 與使用者確認)。AI 留作未來選配(反濫用 / 模糊比對),非本版範圍。

> **使用者已確認的方向(2026-06-17)**:
> 1. 路由 / 驗證走**純規則**,不接 AI。
> 2. 規則判斷 OK → **自動執行寫入(呼叫既有建立 service)**;有疑慮 / 新部門 → **人工**。
> 3. 既有實體 **idempotent 沿用**(department_code / 同部門同名專案 / owner_email)。
> 4. 自動化**全套**:專案 + 使用者 + SDK Key(+ User Token)。新部門因需到 OpenRouter 後台建 Key,**一律人工**。

## 2. 動機

- v1.9.0 申請單送出後是死資料,管理員須手動建立部門/專案/使用者/金鑰,流程冗長易錯。
- 經分析:整個路由(自動 / 人工 / 取消)其實是「部門/專案/使用者三個存在性布林值」的函數,**純規則即可完整決定**,不需 AI。三種資源建立在現有系統也都已是確定性 service(部門 `code` 唯一、專案 `code` 走 Snowflake、使用者 `role=user` 時 account/password 後端自動產生)。
- 不接 AI 的好處:簡單、可預測、可單元測試、零 LLM 成本/延遲/失敗模式、免新建內部 LLM 基礎設施。

## 3. 範圍

### In Scope

- **規則路由引擎**(§ 5):依存在性 + 驗證,把每張申請路由到 自動開通 / 人工 / 系統取消。
- **自動開通(確定性執行,§ 6)**:沿用既有 service / repository,in-process 建立專案 → 使用者 → SDK Key + User Token,單一 transaction。
- **狀態流轉**(§ 4):補取消 / 撤銷 / 人工處理端點與前端操作。
- **資料模型**(§ 7):擴充 `api_key_requests` 欄位 + migration `0013`。
- **API / 前端**(§ 8 / § 9):新增端點與 UI(狀態 badge、取消/撤銷、人工處理、一次性憑證領取)。

### Out of Scope

- **AI / LLM 任何判斷**:本版不接;路由與驗證純規則。
- **背景 job queue / 非同步 worker**:純規則開通可**同步**於送出請求內完成(無 LLM 延遲),故本版**不需**背景佇列、不需「處理中」過渡狀態。
- **撤銷後自動停用 / 回收已建立資源**:預設不連動(見 § 10 待確認 #2)。
- **新部門的自動開通**:一律人工(需 OpenRouter 後台建 Key)。
- **通知(Email / 站內信)**:留待後續評估。

## 4. 狀態模型

申請單 `status`(對齊使用者指定的 5 種,**無過渡狀態**——同步處理):

| `status` 值 | 顯示 | 性質 | 說明 |
| --- | --- | --- | --- |
| `manual_pending` | 待人工處理 | 待辦 | 新部門 / 有疑慮 / 既有專案下的新使用者,轉管理員 |
| `agent_done` | Agent 已處理 | 終態(成功) | 規則自動建立完成,已產生憑證 |
| `done` | 已處理 | 終態(成功) | 管理員人工建立完成 |
| `revoked` | 已撤銷 | 終態(取消) | 在**處理前**(`manual_pending`)由使用者 / 管理員撤回 |
| `cancelled` | 已取消 | 終態(取消) | 申請人自行取消(附原因)**或**系統判定重複(附自動原因) |

> **狀態名稱維持「Agent 已處理」**:本版雖純規則處理,但保留此名以便未來套用 AI Agent 時沿用,值為 `agent_done`。
>
> **撤銷限制**:**一旦已處理(`agent_done` / `done`)即禁止撤銷**;撤銷僅允許於 `manual_pending`(尚未開通)階段。

## 5. 規則路由(確定性,無 AI)

送出時(同步)依下列**決策樹**路由。三個存在性判斷:

- **部門存在?** `DepartmentRepository.get_by_code(department_code)`。
- **專案存在?** 同部門下有同名專案(`project_name`)。
- **使用者存在?** `UserRepository.get_by_email(owner_email)` 命中**唯一一筆**。

| 部門 | 專案 | 使用者 | 路由 | 終態 |
| --- | --- | --- | --- | --- |
| **新** | 任意 | 任意 | **人工**(需 OpenRouter 後台建 Key) | `manual_pending` |
| 舊 | 新 | 新 | 驗證通過 → **自動** | `agent_done` |
| 舊 | 新 | 舊 | 驗證通過 → **自動** | `agent_done` |
| 舊 | 舊 | 新 | **人工**(既有專案要加新成員,需人工確認) | `manual_pending` |
| 舊 | 舊 | 舊 | **系統取消**(重複申請) | `cancelled`<br>原因:**過去已存在相同 Key 資料** |

**等價決策樹**(實作落點:`services/api_key_request_router.py`):

```
if 新部門:           → manual_pending      # 需 OpenRouter 後台建 Key
elif 新專案:         → auto(驗證通過)      # 舊部門 + 新專案(使用者新/舊皆可)
elif 新使用者:       → manual_pending      # 舊部門 + 舊專案 + 新使用者
else:                → cancelled           # 舊部門 + 舊專案 + 舊使用者(重複)
                       cancel_reason = "過去已存在相同 Key 資料"
```

**驗證閘(auto 路徑才檢查,任一不過 → `manual_pending`)**:

- 既有部門的 `name` 與申請 `department_name` 是否一致(以 `department_code` 命中;名稱差異過大 → 轉人工,見 § 10 已決議)。
- `owner_email` 命中**多筆**既有使用者 → 歧義 → 人工。
- (格式類:必填 / email 格式 / `project_url` 為 GitHub/Replit,送出 schema 已擋,不會走到這。)

## 6. 自動開通流程(確定性執行)

`auto` 路徑(舊部門 + 新專案),在**單一 DB transaction**內,沿用既有 service / repository:

| 步驟 | 動作 | Idempotency |
| --- | --- | --- |
| 1 部門 | 沿用既有(by `department_code`) | 必為既有(新部門不會走到此) |
| 2 專案 | 在部門下建立 `project_name` 專案(`code` 走 Snowflake) | 新專案(同名已存在不會走到此路徑) |
| 3 使用者 | 舊使用者 → 沿用(by email);新使用者 → 建立(`role=user`、`username=owner_name`、綁部門) | by `owner_email` |
| 4 SDK Key | 部門**已有可用 SDK Key → 沿用**;否則新建一把(名稱如「{project_name} 申請金鑰」) | 有就沿用(部門級) |
| 5 User Token | 為使用者發 User Token(重發即撤銷舊 token,既有行為) | — |

- 任一步失敗 → rollback → 轉 `manual_pending`(寫 `error_message`)。
- 產出的 **SDK Key 明文 / User Token / Project Code** 於送出回應直接帶回(顯示一次),並寫入 `provisioned_secrets` 供申請人在詳情頁**一次性領取後清空**(§ 7 / § 9)。
  - 沿用既有 SDK Key 時取其留存明文(`key_values`);若該既有 Key 無留存明文(v1.5 前舊資料),`provisioned_secrets` 該欄留空並提示向管理員索取。
- 每步寫 `write_audit`(沿用既有 `create_project` / `create_user` / `create_sdk_key`),另記 `auto_provision_api_key_request`。

## 7. 資料模型異動(`api_key_requests`)

migration `0013_api_key_requests_lifecycle`,新增欄位:

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| `status` | String(16) | 擴充允許值(§ 4);既有 `pending` → migration 轉 `manual_pending` |
| `cancel_reason` | Text, null | 取消原因(申請人填,或系統自動「過去已存在相同 Key 資料」) |
| `cancel_source` | String(8), null | `user` / `system` |
| `handled_by_user_uid` | UUID, null | 人工處理的管理員 |
| `error_message` | Text, null | 自動流程失敗原因 |
| `created_project_uid` | UUID, null | 開通建立的專案 |
| `created_user_uid` | UUID, null | 開通建立 / 沿用的使用者 |
| `created_sdk_key_uid` | UUID, null | 開通建立的 SDK Key |
| `matched_department_uid` | UUID, null | 命中沿用的既有部門 |
| `provisioned_secrets` | JSONB, null | 一次性憑證(SDK Key 明文 / User Token / Project Code),領取後清空 |
| `processed_at` | DateTime(tz), null | 進入終態的時間 |

> `provisioned_secrets` 存敏感明文,屬一次性領取:領取後即 `NULL` 覆寫,不長期留存(對齊既有「金鑰只顯示一次」與法務考量)。

## 8. API 端點(新增 / 擴充)

| Method | Path | 權限 | 說明 |
| --- | --- | --- | --- |
| `POST` | `/api-key-requests`(擴充) | 本人 | 送出即同步跑規則路由;auto 路徑於回應直接帶回憑證 |
| `POST` | `/api-key-requests/{uid}/cancel` | 本人 | 取消(附 `cancel_reason`,`cancel_source=user`);限 `manual_pending` |
| `POST` | `/api-key-requests/{uid}/revoke` | 本人 / admin | 撤銷申請;**限 `manual_pending`**,已處理(`agent_done`/`done`)回 `409` 禁止 |
| `POST` | `/api-key-requests/{uid}/process` | admin | 人工處理:確定性開通 → `done` |
| `GET` | `/api-key-requests/{uid}` | 本人 / admin | 詳情(狀態、路由結果、可領取的一次性憑證) |
| `POST` | `/api-key-requests/{uid}/claim-secrets` | 本人 | 領取一次性憑證後清空 `provisioned_secrets` |

- 既有 `GET /api-key-requests`(列表)不變,回傳含新 `status`。

## 9. 前端設計

- **列表**:狀態 badge(待人工處理=warning、Agent 已處理/已處理=success、已撤銷/已取消=secondary)。
- **申請人視角**:
  - 送出後若被自動開通 → 立即在回應 / 詳情頁**一次性領取**憑證(SDK Key / User Token / Project Code)。
  - 若為重複(系統取消)→ 顯示取消原因「過去已存在相同 Key 資料」。
  - `manual_pending` 可**取消**(彈窗填原因)或**撤銷**(二次確認);**已處理(Agent 已處理 / 已處理)後禁止撤銷**。
- **管理員視角**:「待人工處理」清單可開**人工處理**(檢視申請與路由原因 → 一鍵確定性開通或調整後建立);新部門案在此完成(含 OpenRouter 後台建 Key 的提示)。
- 沿用既有元件(Dialog / Table / Badge / LoadingButton / showDialog / toast)。

## 10. 權限與稽核 / 設計取捨

### 權限與稽核

- 取消 / 領取憑證:**僅申請本人**。撤銷:本人或 admin。人工處理:**僅 admin**。
- 稽核 action 新增:`cancel_api_key_request` / `revoke_api_key_request` / `process_api_key_request` / `auto_provision_api_key_request`;子資源沿用既有 `create_*`。

### 已決議(2026-06-17)

- **狀態命名**:維持「**Agent 已處理**」(`agent_done`),保留供未來套 AI。
- **撤銷規則**:**一旦已處理(`agent_done`/`done`)即禁止撤銷**;撤銷僅限 `manual_pending`。
- **撤銷連動停用資源**:不適用——撤銷只發生在開通前(尚無已建立資源),無連動問題。
- **SDK Key 策略**:既有部門**已有可用 SDK Key → 沿用**(有就用,不另建);部門無可用 Key 時才新建。
- **既有部門名稱一致性檢查**:申請 `department_name` 與 `department_code` 命中的既有部門名稱差異過大 → **轉人工**(防代號打錯誤開通到別的部門)。
- **一次性憑證傳遞**:auto 路徑於送出回應帶回 + 詳情頁**一次性領取後清空**。
- **「舊專案」判定鍵**:以「**同部門 + 同 `project_name`**」視為既有專案(專案 `code` 為 Snowflake、名稱非唯一,故以名稱比對)。

> 本提案範圍與設計取捨已全數確認,可轉為正式 `tasks-v1.9.1.md`。
