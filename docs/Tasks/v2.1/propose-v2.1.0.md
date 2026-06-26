[//]: # (此檔為 v2.1.0 任務提案,實作前先由使用者確認範圍與設計取捨。Agent 草擬、User 拍板。)

# Propose v2.1.0 · AI 推薦模型「真實重跑 + 對比裁決」

> 此為 **proposal**(詳設母本),確認後即據以拆 `workflow/` + `tasks/`。
>
> 對應母本鏈:[v2.0.0 地基](../v2.0/propose-v2.0.0.md) → [v2.0.1 判別管線](../v2.0/propose-v2.0.1.md) → [v2.0.3 評審結果顯示](../v2.0/propose-v2.0.3.md)。
>
> **版號**:本功能原暫定 v2.0.5「真實重跑」(見 propose-v2.0.3 開頭 slot)。因其**需新表 + 新 endpoint + 新管線**,依 [`01-propose/05-version-bump.md`](../../Design-Base/01-propose/05-version-bump.md) 判準(「新表 / 新 endpoint = minor」、「patch 不寫 propose、禁開 API 路徑」),**必為 minor bump → v2.1.0**。
>
> **名詞約定(2026-06-26 修訂,移除黑話)**:本版一律用白話,不再用 challenger / champion / GAN / discriminator 等術語。
> - **原模型** = 使用者實際呼叫、寫進 `usage_logs` 的模型。
> - **AI 推薦模型** = 評審 AI 判別後推薦、且 ≠ 原模型的模型(原文件所稱 challenger;DB 欄位仍叫 `rerun_model`,僅 prose 改白話)。
> - **真實重跑** = 拿 AI 推薦模型,用原本同一份輸入實際打一次 API,取真實輸出 / 成本 / 延遲。
> - **對比裁決** = 再用 AI 比對「原模型輸出 vs 推薦模型輸出」對該任務何者較佳(原文件所稱 discriminator)。

## 版本目標

把 v2.0.1 判別管線「只憑文字判斷」的推薦,升級為**有真憑據的決策**:依評審推薦的模型**實際打一次 API**,拿真實輸出與成本,再由 AI **裁決原模型輸出 vs 推薦模型輸出何者較佳**,讓「該不該換模型」從主觀建議變成**可驗證的決策依據**。對 admin / 成本決策者有價值。

## In Scope

- **新表**(§4):`ai_model_eval_reruns`(與 `usage_logs` 結構相似,但**獨立**——標記「因 AI 推薦而觸發」,不混入正常用量/計費統計),記錄每個 AI 推薦模型的真實呼叫 + 對比結果;父表 `ai_model_evaluations` 增重跑游標欄。**(v2.1.0 已建,本次重做不動 DB,§4 僅供查照)**
- **自動觸發管線**(§5):評審完成、推薦 ≠ 原模型時,**自動**對**三裁判各自推薦的模型(去重)**各打一次真實 API;以 env flag 控管(§7)。
- **對比裁決**(§5):**客觀指標**(成本 / tokens / 延遲 delta)+ **AI 對比裁決**(比對「原模型輸出 vs 推薦模型輸出」何者較適合任務)。
- **唯讀查詢 API**(§6):**跨用量紀錄的總覽端點**,回傳依 `usage_log` 分組的所有 AI 推薦模型重跑 + 對比 + **真實輸出原文(原模型 + 各推薦模型)**,admin 限定。
- **前端展示**(§6):**獨立 admin 頁「AI 判決總覽」**(`/ai-analysis/verdicts`,sidebar「AI 分析」section)。**此頁即詳細頁本身**:依用量紀錄分組,並排呈現「原模型 vs 推薦模型1/2/3 真實輸出比較」+ 成本效益 + 裁決 + 跨 log 裁決分布統計。**不** link 回用量紀錄。
- **usage-log 明細頁回退**(§6):移除 v2.1.0 初版加在 `/usage-logs/[uid]` AI 分析卡內的重跑區塊(`AiRerunSection`),**只保留 v2.0.3 版 AI 分析區塊(`AiAnalysisSection`)樣式**。
- **環境變數控管**(§7):`AI_RERUN_ENABLED` 等;`.env.example` / `.env` 同步。**(v2.1.0 已建)**
- **Migration**(§4):新表 + 父表游標欄。**(v2.1.0 已建,本次不動)**

## Out of Scope

- **人類裁決 / 複審佇列**(採納/駁回推薦結果的人工流程)→ 後續版本(原 v2.0.6 slot)。
- **成本 delta / 部門彙總儀表板**(跨筆深度統計)→ 後續版本(原 v2.0.7 slot);本版總覽頁的裁決分布只做輕量彙總(§6.1),不做部門切片。
- **自動「換模型」**:本版只產出證據與裁決,**不**自動改派工 / 不改使用者實際用的模型。
- **串流重跑**:重跑一律非串流(只需最終文字供對比),不做 SSE。
- **多輪對話 / messages[] 重跑**:沿用單輪 text/images 輸入快照(對齊現況)。
- **DB 重建**:本表 / 父表游標 / migration 於 v2.1.0 已建妥,真實輸出原文已存於 `response_summary.output_text`;本次重做**不動 DB**,只改 schema 對外吐欄、API、前端。

## 對外承諾

- **新增 / 調整 API**(admin,`/api/docs` 可查):
  - `GET /api/v1/ai-eval/reruns`(分頁,admin)→ **依用量紀錄分組**的總覽:每組 = 一筆原始呼叫(原模型 + 原模型輸出原文 + 原成本)+ 其底下去重後的推薦模型1/2/3(各帶真實輸出原文 / 成本 / 成本Δ / 延遲 / 裁決 / 信心 / 理由)。無資料 → `200 + items=[]`。
  - **(移除)** 原 `GET /api/v1/ai-eval/reruns/by-usage-log/{usage_log_uid}`:usage-log 明細頁不再內嵌重跑區塊,此端點無消費者 → 連同 schema 一併移除(讀取全收斂到總覽端點)。
- **行為**:`AI_RERUN_ENABLED=false`(預設)時**完全不觸發**任何真實重跑(零額外成本)。
- **資料隔離**:推薦模型真實呼叫**不**寫入 `usage_logs`、**不**計入部門用量/成本報表(獨立新表),避免污染計費。

## 資料流 / 觸發與對比流程

```
[v2.0.1 評審完成] ai_model_evaluations.status='evaluated'(≥1 推薦)
   │  條件:AI_RERUN_ENABLED=true 且 至少一裁判推薦 ≠ 原模型
   ▼
[排程派發] dispatch_unrerun(taskiq beat,掃父表游標 ai_reran_at IS NULL 的待重跑筆)
   │  逐筆 → rerun task
   ▼
[rerun task] 對「三裁判推薦模型去重後、且 ≠ 原模型」的每個推薦模型:
   ├─ 1) 真實呼叫推薦模型(同原輸入快照,非串流,走 DEFAULT_OPENROUTER_KEY,不寫 usage_logs)
   │     → 取推薦模型輸出 / tokens / cost / latency / status
   ├─ 2) 客觀指標:cost_delta = 推薦模型_cost − 原_cost(tokens / latency 同記)
   ├─ 3) AI 對比裁決:比對「原模型輸出 vs 推薦模型輸出」對任務何者較佳
   │     → winner(原模型 / 推薦模型 / 平手)+ reason(+ 信心分數)
   └─ 4) 寫一筆 ai_model_eval_reruns(原子,含推薦模型輸出原文 response_summary.output_text)
   ▼  全部推薦模型完成 → 標父表游標 ai_reran_at/status
[前端] AI 判決總覽頁(/ai-analysis/verdicts)依用量紀錄分組:
        左原模型輸出 vs 右推薦模型1/2/3 輸出並排 + 成本Δ + 裁決 + 跨 log 分布統計
```

**狀態機**(父表 `ai_model_evaluations` 重跑游標,對齊 v2.0.1 評審游標設計):

| 狀態 | 條件 | 說明 |
| --- | --- | --- |
| 未重跑 | `ai_reran_at IS NULL` | 尚未輪到 / `AI_RERUN_ENABLED=false` / 無 ≠ 原模型的推薦(跳過也標終局) |
| 重跑成功 | `ai_rerun_status=1` | ≥1 推薦模型跑完(含對比裁決) |
| 重跑失敗 | `ai_rerun_status=0` | 全推薦模型失敗(終局,不重派) |

## 資料模型(新表 + 父表游標)·v2.1.0 已建,本次不動

> **本次重做不修改任何 DB 結構 / migration**。下列為現況查照;真實輸出原文已存於 `response_summary.output_text`,本次僅在 schema/API 把它對外吐出(§5.4)。

### 4.1 新表 `ai_model_eval_reruns`(一筆 = 一個 AI 推薦模型的真實重跑 + 對比)

必備欄位(`pid` / `ai_eval_rerun_uid` / `is_active` / `is_deleted` / `created_at` / `updated_at`,對齊 `04-databases/90-project-database.md`)外:

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| `ai_evaluation_uid` | UUID | 軟引用父評審(來自哪次評審的推薦) |
| `usage_log_uid` | UUID | 軟引用原始 log(同輸入來源;**前端分組鍵**) |
| `ai_candidate_uid` | UUID? | 軟引用是哪個裁判候選推薦的(可追溯;去重合併時取代表者) |
| `original_model` | String(128) | 原模型 key(denormalize,對比顯示) |
| `rerun_model` | String(128) | AI 推薦模型 key(實際重跑) |
| `model_uid` | UUID? | 推薦模型 model_uid(軟引用 models) |
| `request_content` | JSONB? | 重跑輸入快照(可重現;沿用原 log 輸入) |
| `response_summary` | JSONB? | **推薦模型真實輸出**(`{output_text, usage?}`);**§6 並排比較的右側來源** |
| `prompt_tokens`/`completion_tokens`/`total_tokens` | Integer | 推薦模型真實 token |
| `cost_usd` | Numeric(12,6) | 推薦模型真實成本 |
| `original_cost_usd` | Numeric(12,6)? | 原呼叫成本(denormalize,對比) |
| `cost_delta_usd` | Numeric(12,6)? | 推薦模型 − 原(客觀指標) |
| `latency_ms` | Integer | 推薦模型延遲 |
| `status` | String(16) | success / error |
| `error_code` | String(64)? | NULL=無錯誤 |
| `openrouter_generation_id` | String(64)? | OpenRouter 生成 ID |
| `compare_winner` | String(16)? | 對比裁決:original / challenger / tie(prose:原模型 / 推薦模型 / 平手) |
| `compare_score` | Numeric(4,3)? | **信心分數**(0–1):裁決對「原推薦是否合理」的信心。(B) 啟用時必填;停用時 NULL。 |
| `compare_reason` | Text? | 裁決理由 |
| `compare_judge_model` | String(128)? | 擔任裁決的模型 key(=**推薦該模型的評審本人**,自我裁決;去重取代表者) |
| `triggered_at` | TIMESTAMPTZ | 重跑執行時間(UTC+8) |

- **冪等**:`UNIQUE(ai_evaluation_uid, rerun_model)`(不分軟刪),避免同推薦模型重複重跑。
- **索引**:`(usage_log_uid)`、`(ai_evaluation_uid)` partial(`is_deleted=false`),供前端/查詢。

### 4.2 父表 `ai_model_evaluations` 增重跑游標(已建)

- `ai_reran_at TIMESTAMPTZ NULL`:最新一次重跑執行時間;NULL=待重跑(派發掃描鍵)。
- `ai_rerun_status SMALLINT NULL`:NULL=未重跑 / 0=失敗 / 1=成功(成敗皆標,終局不重派)。

> 設計對齊 v2.0.1:用「父表游標 + IS NULL 掃待派 + 終局化(成敗皆標)」,而非搶佔鎖;冪等靠新表 UNIQUE。

## 後端

> §5.1 / §5.2 / §5.3(觸發、重跑 service、對比裁決)於 v2.1.0 已實作,本次重做**核心邏輯不變**,僅 §5.4 查詢層(schema / API)需配合前端改版調整。下列保留供查照。

### 5.1 觸發排程(taskiq beat)

- `dispatch_unrerun`(對齊 `dispatch_unevaluated`,**沿用其 beat 排程與批量常數,不新增 env**):`AI_RERUN_ENABLED=false` → return 0;否則掃父表 `ai_reran_at IS NULL 且 status='evaluated'` 前 N 筆,逐筆 `rerun_evaluation_task.kiq`。
- **跳過條件**(標終局、不重跑):無任何「推薦 ≠ 原模型」的裁判(全員建議維持)→ `ai_reran_at=now(), ai_rerun_status=1`,推薦模型 0 筆。

### 5.2 rerun service(純業務核心,可獨立測)

- 取父評審 + 候選(含裁判推薦)→ 算「待重跑推薦模型集合」=`{裁判推薦模型} − {原模型}`(去重)。
- **執行序(定案)**:單一 task 內各推薦模型**順序處理(串行)**,非併發——逐一 `真實重跑 → 對比裁決 → 寫一筆`。背景管線、非即時阻塞使用者,以串行換取「不瞬時打爆 OpenRouter 速率 + 每日預算閘逐筆累加好控管」。
- 對每個推薦模型:組原輸入快照 payload → `chat_completion`(非串流,`DEFAULT_OPENROUTER_KEY`,**不**寫 usage_logs)→ 解析輸出 / usage → 反查 models 算 `cost_usd` → `cost_delta`。
- **AI 對比裁決**(§5.3)→ winner / reason。
- 單一推薦模型一筆 `ai_model_eval_reruns`(原子);全完成標父游標。**單一推薦模型失敗不阻斷其他**;全失敗 → `ai_rerun_status=0`。
- 錯誤對外收斂 `AppError`,細節進結構化 log(不洩金鑰)。

### 5.3 AI 對比裁決(prompt + service)

- **子開關 `AI_RERUN_DISCRIMINATOR_ENABLED`(§7)**:false → 跳過本環節,該推薦模型仍寫一筆(含真實重跑客觀指標),但 `compare_*` 留 NULL;前端對應顯示「已重跑·未裁決」。true(預設)→ 執行完整對比。
- **誰推薦、誰自我裁決**(定案):裁決者 = **推薦該模型的那個評審本人**。例:評審 `claude-opus-4-8` 推薦 `gemini-2.5` → 打 `gemini-2.5` 取真實輸出 → 再用 `claude-opus-4-8` 裁決「自己推薦的 `gemini-2.5` vs 使用者實際用的原模型,哪個對任務較好」。去重時由代表者裁判擔任。
- **盲化裁決**(定案):prompt **不揭露兩側模型名**,只給「輸出 A / 輸出 B + 任務」讓裁判盲選,事後映射回原模型 / 推薦模型。避免自我偏好偏差。
- prompt builder 輸出結構化 JSON `{winner, reason, score}`:`winner`=A/B(映射回 建議改用/維持/平手);`score`=信心分數 0–1;`temperature=0`(對齊 v2.0 fixed §2)。

### 5.4 查詢 API(唯讀,admin)·本次重做重點

- **單一端點** `GET /api/v1/ai-eval/reruns`(`AdminDep`,分頁);**依用量紀錄分組**回傳;無資料 → `200 + {items: [], total: 0, ...}`。
- **Response schema(改版,Pydantic;Decimal → 字串,對齊既有慣例)**——分組結構:
  - `RerunGroup`(一組 = 一筆用量紀錄):
    - `usage_log_uid`、`original_model`、`original_output_text`(原模型真實輸出原文,取自 `usage_logs.response_summary.output_text`)、`original_cost_usd`、`evaluated_at?`。
    - `recommendations: list[RerunRecommendation]`(去重後的推薦模型1/2/3)。
  - `RerunRecommendation`(逐推薦模型):`rerun_model`、`model_uid`、**`output_text`(推薦模型真實輸出原文,取自 `ai_model_eval_reruns.response_summary.output_text`)**、`prompt/completion/total_tokens`、`cost_usd`、`cost_delta_usd`、`latency_ms`、`status`、`error_code`、`compare_winner`、`compare_score`(信心)、`compare_reason`、`compare_judge_model`、`triggered_at`。
  - `RerunOverviewPage`:`items: list[RerunGroup]`、`total`、`page`、`size`、**`stats`(跨 log 裁決分布,§6.1)**:`{total_recommendations, keep_count, swap_count, tie_count, unjudged_count, failed_count}`。
- **移除** 原 `RerunResult` / `RerunListResponse` / `RerunOverviewItem`(扁平、無輸出原文)及 by-usage-log 端點。
- 落點:沿用 `app/api/v1/ai_eval_reruns.py`(讀寫分檔,對齊 v2.0.3);schema `app/schemas/ai_model_eval_rerun_result.py` 改版。

## 前端(AI 判決總覽 · 獨立 admin 頁)

> **落點(本次重做定案)**:AI 推薦模型真實重跑對比**集中到獨立 admin 頁** `/ai-analysis/verdicts`「AI 判決總覽」(sidebar「AI 分析」section,admin 限定;v2.1.1 已掛入口,本版重做為「詳細並排比較」頁)。
>
> **此頁即詳細頁本身**——直接並排呈現「原模型 vs 推薦模型1/2/3 真實輸出比較」,**禁止** link 回用量紀錄、不在 usage-log 明細卡內嵌重跑區塊。
>
> **usage-log 明細頁回退**:移除 v2.1.0 初版加在 `/usage-logs/[uid]` AI 分析卡內的 `AiRerunSection`,**只保留 v2.0.3 版 AI 分析區塊(`AiAnalysisSection`)樣式**;重跑對比一律到總覽頁看。

### 6.1 AI 判決總覽頁(`/ai-analysis/verdicts`,admin)

- 落點:`frontend/src/app/(main)/ai-analysis/verdicts/page.tsx`(已存在,本版**重做**為「依用量紀錄分組 + 真實輸出並排比較」)。
- **以用量紀錄(usage_log)為單位分組**:每組 = 一筆原始呼叫 + 其底下去重後的 1–N 個 AI 推薦模型。最新優先、分頁。
- **核心區塊**:
  1. **真實輸出並排比較**(主角):同一組內,呈現「**原模型輸出** vs **推薦模型1 / 推薦模型2 / 推薦模型3 輸出**」並排比較;每欄標模型 key + tier。admin 直接讀真實文字判斷 AI 裁決是否合理。**(必須能看到三個推薦模型的真實輸出原文,這是本頁存在的核心目的)**
  2. **成本效益**:每個推薦模型標真實成本 + 成本Δ(綠=更省 / 紅=更貴)+ 延遲;原模型標原成本。
  3. **裁決**:每個推薦模型的 winner Badge(建議改用 / 維持 / 平手)+ 信心分數 + 理由 + 裁決模型。
  4. **裁決分布統計**(輕量彙總,頁頂):跨 log 的 `stats`——建議維持 vs 改用 vs 平手筆數、未裁決 / 失敗筆數。
- **禁止連回用量紀錄**:組 / 列 / 任何元素**不可點擊跳轉** `/usage-logs/*`;所需明細(含原模型與推薦模型真實輸出原文)全由本頁 API(§5.4)一次帶足。
- 狀態:未重跑 / 重跑中 / 重跑失敗 / 已重跑 / 已重跑·未裁決(子開關關,`compare_*` NULL)。
- 型別 / 端點常數 / label 集中(對齊 v2.0.3 `ai-eval-labels.ts` 慣例;沿用既有 `aiRerunsOverview` 端點常數)。

### 6.2 視覺形式(user 授權 agent 決策,2026-06-26)

> user「視覺形式我先讓你決策」→ 定案如下;功能需求為地板,視覺實作以此為準。

- **頁頂統計列**:`stats` 渲染為一排小指標卡——總筆數 / 建議維持 / 建議改用 / 平手 / 未裁決 / 失敗。
- **主體=分組 Card 列表**:每組(一筆用量紀錄)一張可展開 / 收合 Card。
  - **收合**:`原模型 key → 推薦模型數` + 彙總裁決 Badge(如「2/3 建議維持」)+ 執行時間。
  - **展開=並排欄位比較**:第一欄固定「**原模型(原始)**」,後接「**推薦模型1 / 2 / 3**」欄。
    - 每欄頂:模型 key + tier badge(原模型欄標「原始」)。
    - 每欄主體:**真實輸出原文**(`max-h` + 內部捲動,避免撐爆版面)。
    - 推薦欄底:真實成本 + **成本Δ**(綠=更省 / 紅=更貴)+ 延遲 + **裁決 Badge** + 信心分數 + 理由。
    - 任務輸入(該組共用)置於 Card header 可折疊區。
  - **RWD**:桌機多欄 grid 並排;手機垂直堆疊(原模型置頂,推薦模型依序)。
- **功能需求(不可妥協)**:① 依用量紀錄分組;② 同組內看得到原模型 + 推薦模型1/2/3 的**真實輸出原文**並排比較;③ 帶成本Δ + 裁決 + 信心;④ 頁頂裁決分布統計;⑤ **不跳轉用量紀錄**。

### 6.3 usage-log 明細頁回退

- 落點:`frontend/src/app/(main)/usage-logs/[uid]/page.tsx`。
- **移除** `AiRerunSection`(import、render、檔案)。
- **保留** `AiAnalysisSection`(v2.0.3 版 AI 分析區塊樣式)不動。
- 連帶清理:該頁不再消費 by-usage-log 端點(該端點已於 §5.4 移除)。

## 設定(環境變數)·v2.1.0 已建,本次不動

| 變數 | 預設 | 說明 |
| --- | --- | --- |
| `AI_RERUN_ENABLED` | `false` | **總開關**:管整個第二層。false 時完全不觸發真實重跑與對比裁決,零成本。對齊 `AI_EVAL_ENABLED`。 |
| `AI_RERUN_DISCRIMINATOR_ENABLED` | `true` | **對比裁決子開關**(須 `AI_RERUN_ENABLED=true` 才生效):true → 真實重跑後再讓 AI 裁決;false → 只做真實重跑取客觀指標(cost/tokens/延遲 delta),跳過 AI 裁決,`compare_*` 留 NULL。 |

> 派發批量 / 排程間隔不另立 env(沿用 `dispatch_unevaluated`)。每日預算閘不導入(已決議 #1)。推薦模型與裁決呼叫沿用 `DEFAULT_OPENROUTER_KEY`(內部呼叫,不經 SDK proxy、不寫 usage_logs)。

## 風險與相依

- **成本風險(高)**:自動 + 三裁判各跑 + 對比裁決 = 每筆最多 **3×(真實重跑)+ 3×(裁決)** 真實呼叫。控管靠 `AI_RERUN_ENABLED` **預設關** + **去重** + **維持原模型跳過** + 裁決子開關可省。**不導入每日預算閘**(已決議 #1)。
- **輸出原文外露(本次新增)**:總覽頁把原模型 + 推薦模型真實輸出原文呈現給 admin。資料原已存於 DB,本版僅新增「對外吐欄 + 前端顯示」;**admin 限定**(`AdminDep` + 前端角色守衛),非 admin 403 / 不顯示。
- **PII**:重跑會把原輸入(可能含 PII)再次外送 + 輸出原文呈現於頁面;對齊 v2.0.1「本版不遮罩、保留 mask hook」現況。
- **第三方**:OpenRouter 真實計費 + 速率;對齊 `90-third-party-service/50-openrouter.md`、`02-rate-and-cost.md`。
- **資料正確性**:`original_cost_usd` 對歷史 log 可能為近似;無原成本時 `cost_delta` 留 NULL。原模型輸出原文若歷史 log 未存 `response_summary.output_text`,該組原側顯示「無原始輸出快照」。

## 驗收標準

- `AI_RERUN_ENABLED=false` → `dispatch_unrerun` 回 0、無任何重跑、無新表寫入。
- `=true` 且推薦 ≠ 原模型 → 對去重推薦模型各寫一筆 `ai_model_eval_reruns`,含真實 cost / cost_delta / winner / 輸出原文;父游標標終局。
- `AI_RERUN_DISCRIMINATOR_ENABLED=false` → 仍寫真實重跑列(客觀指標 + 輸出原文齊全),但 `compare_*` 全 NULL、無裁決呼叫;`=true`(預設)→ `compare_winner`/`reason` 有值。
- 單一推薦模型失敗不阻斷其他;全失敗 → 父 `ai_rerun_status=0`。
- 推薦模型呼叫**不**出現在 `usage_logs`(SQL 驗證不新增 usage_logs 列)。
- `GET /api/v1/ai-eval/reruns` admin 可取、非 admin 403、無資料回 `200 + items:[]`;回傳**依用量紀錄分組**,每組帶原模型輸出原文 + 各推薦模型輸出原文 + 成本Δ + 裁決 + `stats`。
- **AI 判決總覽頁**:依用量紀錄分組,看得到原模型 vs 推薦模型1/2/3 真實輸出並排、成本Δ、裁決、頁頂分布統計;**全頁無任何連回 `/usage-logs/*` 的連結**。
- **usage-log 明細頁**:`AiRerunSection` 已移除、`AiAnalysisSection` 保留、頁面回到 v2.0.3 樣式;不再呼叫 by-usage-log 端點。
- 後端單元/整合測試(respx 攔截重跑 + 裁決);`/api/docs` 可查改版後 API;by-usage-log 端點與舊扁平 schema 已移除、無殘留引用。

## 設計取捨 / 已決議(user 拍板)

> **核心機制**:自動觸發、客觀指標 + AI 對比裁決、三裁判推薦各跑(去重)、獨立新表(不混 usage_logs)、env flag 控管、單一 task 內串行處理。

| # | 決議 | 落點 |
| --- | --- | --- |
| 1 | **不導入每日成本閘**;控管靠總開關預設關 + 去重 + 維持原模型跳過 | §7、風險 |
| 2 | 裁決者 =**推薦該模型的評審本人**(自我裁決);去重取代表者 | §5.3、§4.1 |
| 3 | **不加**抽樣門檻 / 吻合度門檻(初版) | §5.1 |
| 4 | 去重:三裁判推薦同模型 → 合併一筆,`ai_candidate_uid` 取代表者 | §4.1 |
| 5 | PII 再送:**沿用 v2.0.1 不遮罩**現況(保留 mask hook) | 風險 |
| 6 | discriminator/裁決 **盲化**:不揭露兩側模型名 | §5.3 |
| 7 | **不新增** batch / interval env;沿用 `dispatch_unevaluated` | §5.1、§7 |
| 8 | 版號定案 **v2.1.0**(新表+新 endpoint=minor) | 開頭 slot |
| **9** | **(2026-06-26 重做)移除黑話**:challenger→AI 推薦模型、discriminator/GAN→對比裁決、champion→原模型 | 全文 |
| **10** | **(重做)前端落點改獨立 admin 頁** `/ai-analysis/verdicts`「AI 判決總覽」,**即詳細頁本身**;移除 usage-log 明細卡內 `AiRerunSection`,該頁回退 v2.0.3 樣式 | §6 |
| **11** | **(重做)總覽頁依用量紀錄分組**,並排顯示原模型 vs 推薦模型1/2/3 **真實輸出原文** | §6.1、§5.4 |
| **12** | **(重做)禁止連回用量紀錄**:總覽頁不得有任何跳轉 `/usage-logs/*` 的連結 | §6.1 |
| **13** | **(重做)DB 不動**:表/游標/migration v2.1.0 已建,輸出原文已存 `response_summary.output_text`;只改 schema 對外吐欄 + API + 前端 | §4、§5.4 |
| **14** | **(重做)API 收斂**:移除 by-usage-log 端點與舊扁平 schema,讀取全走分組總覽端點(帶輸出原文 + stats) | §5.4、對外承諾 |

## 變更紀錄

| 日期 | 改動 | 理由 |
| --- | --- | --- |
| 2026-06-26 | 初版(真實重跑 + 對比裁決;升為 v2.1.0) | 把「只憑文字判斷」升級為有真憑據的閉環 |
| 2026-06-26 | 明定串行執行序;新增對比裁決子開關;`compare_score` 正名信心分數;前端摘要層+詳細層 | 拍板細節 |
| 2026-06-26 | **重做:全文移除黑話(challenger/GAN/discriminator→白話);前端改獨立 admin「AI 判決總覽」頁(依用量紀錄分組、原 vs 推薦1/2/3 真實輸出並排、禁連回用量紀錄、頁頂裁決分布);usage-log 明細頁回退 v2.0.3(移除 AiRerunSection);API 收斂為單一分組總覽端點並吐輸出原文 + stats;DB 不動** | user 拍板:初版 UI 過於陽春且術語難懂;詳細比較應集中於專屬 admin 頁、看得到三個推薦模型真實輸出;DB 已建妥不需重建 |
