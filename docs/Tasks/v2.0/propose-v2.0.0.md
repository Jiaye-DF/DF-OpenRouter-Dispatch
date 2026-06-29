[//]: # (此檔為 v2.0.0 任務提案,實作前先由使用者確認範圍與設計取捨。)

# Propose v2.0.0 · 模型適配評審【地基:資料表 + 判別模型設定】

> 此為 **proposal**(規劃草案),確認後即轉為正式 `tasks-v2.0.0.md`。
>
> v2.0.x 系列把「模型適配評審」拆成多個小版本遞進。**本版只鋪地基**:建立資料表 + 判別模型設定 UI,**不打任何 OpenRouter API、不導入排程**。

## 1. 目標(本版)

為「模型適配評審」功能鋪好**最小地基**:

1. **判別模型設定**:管理員可在前端設定 **3 個判別模型**(從「模型管理」既有模型挑選),存入 DB。
2. **資料表建立**:新增本功能所需資料表(全部 `ai_` 前綴),僅建表結構。
3. **前端骨架**:新增 side-bar 分類「**AI 分析**」,其下第一個頁面「**設定判別模型**」。

> **本版刻意不做**:不呼叫任何 OpenRouter / LLM、不導入 taskiq/Redis、不跑評審、不重跑、無人類裁決、無成本計算、無儀表板。純地基。

## 2. v2.0.x 拆版藍圖

| 版本 | 主題 | 重點 | API 呼叫 |
| --- | --- | --- | --- |
| **v2.0.0(本版)** | 地基 | 資料表 + 判別模型設定 UI + side-bar | ❌ 不打 |
| **v2.0.1** | 判別管線 | 導入 **taskiq + Redis**;3 判別模型實際對 `usage_logs` 打分,結構化輸出回寫 | ✅ 三評審 |
| v2.0.2(暫定) | 真實重跑 | 推薦模型實際打一次 API,取真實成本 + A/B 對照 | ✅ 重跑 |
| v2.0.3(暫定) | 人類裁決 | 複審佇列 UI,人類選最佳 = ground truth,校準評審偏差 | — |
| v2.0.4(暫定) | 成本與彙總 | `ai_cost_delta`、部門/使用者彙總、儀表板卡 | — |
| v2.1(暫定) | 節流/擴展 | 抽樣 / 去重聚類 / 學習窗口快取;broker 換 RabbitMQ | — |

> 後續版本範圍為**暫定**,各自再開 propose 細談。

## 3. 範圍(本版)

### In Scope

- **判別模型設定資料表**(§ 4.1):`ai_eval_judge_settings`,存被選為判別模型的 3 個模型。
- **評審結果資料表骨架**(§ 4.2):`ai_model_evaluations`(父)+ `ai_model_eval_candidates`(子),**僅判別階段欄位**(重跑/裁決/成本欄位留待後續版本以 migration 增補)。
- **設定 CRUD API**(§ 5)。
- **前端**(§ 6):side-bar「AI 分析」+「設定判別模型」頁(Combobox 從模型管理選,限 3 個)。

### Out of Scope(本版不做,留待後續)

- **任何 LLM / OpenRouter 呼叫**、評審執行 → v2.0.1。
- **taskiq / Redis / 排程** → v2.0.1。
- **真實重跑 / 真成本** → v2.0.2。
- **人類裁決 / 複審佇列** → v2.0.3。
- **成本 delta / 部門彙總 / 儀表板** → v2.0.4。

## 4. 資料模型(全部 `ai_` 前綴)

migration `0018_ai_model_eval_foundation`。**不動既有表結構**(`usage_logs` 旗標欄 `ai_evaluated_at` 留待 v2.0.1 與排程一起加)。

### 4.1 `ai_eval_judge_settings`(判別模型設定)

存「被選為判別模型」的模型;**恰 3 筆有效**。

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| `ai_judge_setting_uid` | UUID, PK | 識別 |
| `model_uid` | UUID, FK → `models` | 被選為判別模型的模型 |
| `ai_judge_slot` | SMALLINT | 槽位 1/2/3(唯一,限定恰 3 個) |
| `is_active` | BOOLEAN | 是否啟用 |
| `created_at` / `updated_at` | TIMESTAMPTZ | 自動 |

> 設定即「哪 3 個模型當評審」;不綁定特定廠商,管理員自選(建議跨廠商以利日後偏差抵銷)。

### 4.2 `ai_model_evaluations`(評審結果父表,本版只建表)

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| `ai_evaluation_uid` | UUID, PK | 識別(UUIDv7) |
| `usage_log_uid` | UUID, FK, **unique** | 來源 log,一對一 |
| `department_uid` | UUID, null | denormalize |
| `user_uid` | UUID, null | denormalize |
| `ai_original_model` | VARCHAR(128) | 原模型(= `usage_logs.model`) |
| `ai_task_summary` | TEXT, null | dim1 工作摘要(v2.0.1 寫入) |
| `ai_task_intent` | VARCHAR(64), null | dim2 任務意圖 |
| `ai_task_complexity` | VARCHAR(16), null | dim2 複雜度 |
| `status` | VARCHAR(16) | `pending` / `evaluated` / `error` |
| `ai_evaluated_at` | TIMESTAMPTZ, null | 評審完成時間 |
| `created_at` / `updated_at` | TIMESTAMPTZ | 自動 |

> 重跑(v2.0.2)、人類裁決(v2.0.3)、成本 delta(v2.0.4)欄位**屆時各自 migration 增補**,本版不放。

### 4.3 `ai_model_eval_candidates`(各評審候選子表,本版只建表)

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| `ai_candidate_uid` | UUID, PK | 識別 |
| `ai_evaluation_uid` | UUID, FK | 對應父表 |
| `model_uid` | UUID, FK → `models` | 此候選由哪個判別模型產生 |
| `ai_recommend_model` | VARCHAR(128), null | 推薦模型(限白名單;v2.0.1 寫入) |
| `ai_recommend_tier` | VARCHAR(32), null | 由 model 反查 |
| `ai_recommend_reason` | TEXT, null | 推薦理由 |
| `ai_fit_score` | NUMERIC(4,3), null | dim3 吻合度 0–1 |
| `ai_self_vote` | BOOLEAN, null | 推薦是否與**判別模型自己**同廠商(自我偏好偏差監控;v2.0 更正:原誤寫為「與原模型」,比對對象應為裁判 vs 推薦) |
| `created_at` | TIMESTAMPTZ | 自動 |

## 5. 設定 CRUD API(新增)

| Method | Path | 權限 | 說明 |
| --- | --- | --- | --- |
| `GET` | `/api/v1/ai-eval/judge-settings` | admin | 取目前 3 個判別模型 |
| `PUT` | `/api/v1/ai-eval/judge-settings` | admin | 整批設定 3 個判別模型(以 `model_uid` 陣列,長度須恰 3) |

- **驗證**:陣列長度恰 3、`model_uid` 須存在於 `models` 且 active、不可重複。
- Swagger 於 `/api/docs` 同步補 Schema。

## 6. 前端設計(additive,不改既有頁)

- **Side-bar 新增分類「AI 分析」**(admin 可見)。
- 其下頁面「**設定判別模型**」:
  - 3 個 Combobox 槽位,清單來源 = **模型管理的所有 active 模型**(純前端過濾)。
  - 限定恰 3 個、不可重複;儲存呼叫 `PUT /ai-eval/judge-settings`。
  - 顯示目前設定與更新時間。
- 沿用既有元件(Combobox / Card / toast);**不碰現有任何頁面與 proxy 流程**。

## 7. 設定(環境變數)

- 本版**無新增 env**(判別模型走 DB 設定,非 env;taskiq/Redis 等待 v2.0.1)。

## 8. 設計取捨 / 待使用者確認

### 已決議(2026-06-25)

- **拆版**:v2.0.0 只鋪地基(表 + 設定 UI),不打 API、不導入排程;判別管線進 v2.0.1。
- **判別模型**:由 UI 設定、存 DB、**恰 3 個**,從模型管理現有模型挑選。
- **命名**:表與 AI 產出欄位一律 `ai_` 前綴。

### 待使用者確認

1. **結果表是否本版就建**:傾向本版即建 `ai_model_evaluations` / `ai_model_eval_candidates` 骨架(僅判別階段欄位),後續版本再 migration 增補重跑/裁決/成本欄位。可接受嗎?(或你希望結果表也延到 v2.0.1 再建?)
2. **判別模型可否跨廠商強制**:是否要在 UI 提示/建議「3 個盡量挑不同廠商」以利日後自我偏好偏差抵銷?(非強制,僅提示)
3. **`ai_eval_judge_settings` 設計**:用「3 槽位列」還是「單列存 model_uid 陣列 JSONB」?(傾向 3 槽位列,FK 完整、好查)
