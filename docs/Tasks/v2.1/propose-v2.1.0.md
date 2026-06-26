[//]: # (此檔為 v2.1.0 任務提案,實作前先由使用者確認範圍與設計取捨。Agent 草擬、User 拍板。)

# Propose v2.1.0 · 推薦模型「真實重跑 + 對比裁決」(champion / challenger,GAN 閉環)

> 此為 **proposal**(詳設母本),確認後即據以拆 `workflow/` + `tasks/`。
>
> 對應母本鏈:[v2.0.0 地基](../v2.0/propose-v2.0.0.md) → [v2.0.1 判別管線](../v2.0/propose-v2.0.1.md) → [v2.0.3 評審結果顯示](../v2.0/propose-v2.0.3.md)。
>
> **版號**:本功能原暫定 v2.0.5「真實重跑」(見 propose-v2.0.3 開頭 slot)。因其**需新表 + 新 endpoint + 新管線**,依 [`01-propose/05-version-bump.md`](../../Design-Base/01-propose/05-version-bump.md) 判準(「新表 / 新 endpoint = minor」、「patch 不寫 propose、禁開 API 路徑」),**必為 minor bump → v2.1.0**(原藍圖排進 v2.0.x patch 槽與規則打架,本版修正)。
>
> **原 v2.0.4「AI 分析細看專頁」slot 取消**:該細看 UI 已吸收為本版 §6 的 inline 詳細區塊(落在現有 `/usage-logs/[uid]` AI 分析卡),不另立 v2.0.4 專頁;後續 slot(人類裁決 / 儀表板)版號順移由各自 propose 重判。

## 版本目標

把 v2.0.1 判別管線「只憑文字判斷」的推薦,升級為**有真憑據的閉環**:依評審推薦的模型**實際打一次 API**,拿真實輸出與成本,再由 AI **裁決原輸出 vs challenger 輸出何者較佳**(GAN/champion-challenger 概念),讓「該不該換模型」從主觀建議變成**可驗證的決策依據**。對 admin / 成本決策者有價值。

## In Scope

- **新表**(§4):`ai_model_eval_reruns`(與 `usage_logs` 結構相似,但**獨立**——標記「因 AI 推薦而觸發」,不混入正常用量/計費統計),記錄每個 challenger 的真實呼叫 + 對比結果;父表 `ai_model_evaluations` 增重跑游標欄。
- **自動觸發管線**(§5):評審完成、推薦 ≠ 原模型時,**自動**對**三裁判各自推薦的模型(去重)**各打一次真實 API;以 env flag 控管(§7)。
- **對比裁決**(§5):**客觀指標**(成本 / tokens / 延遲 delta)+ **AI discriminator**(比對「原輸出 vs challenger 輸出」何者較適合任務,GAN)。
- **唯讀查詢 API**(§6):依 `usage_log_uid` / `ai_evaluation_uid` 取該筆所有 challenger 重跑 + 對比,admin 限定。
- **前端展示**(§6,落點 `/usage-logs/[uid]` 既有 AI 分析卡,**不依賴未建的 v2.0.4**):**摘要層**——新增「AI 判決結果」欄位(每 usage_log 一筆,顯示 原始→模型1/2/3 對應,點開 inline 展開);**詳細層**——同卡 inline 展開 challenger 對比區塊。
- **環境變數控管**(§7):新增 `AI_RERUN_ENABLED` 等;`.env.example` / `.env` 同步。
- **Migration**(§4):新表 + 父表游標欄。

## Out of Scope

- **人類裁決 / 複審佇列**(採納/駁回 challenger 結果的人工流程)→ 後續版本(原 v2.0.6 slot)。
- **成本 delta / 部門彙總儀表板**(跨筆 challenger 統計)→ 後續版本(原 v2.0.7 slot)。
- **自動「換模型」**:本版只產出證據與裁決,**不**自動改派工 / 不改使用者實際用的模型。
- **串流 challenger**:重跑一律非串流(只需最終文字供對比),不做 SSE。
- **多輪對話 / messages[] challenger**:沿用單輪 text/images 輸入快照(對齊現況)。

## 對外承諾

- **新增 API**(admin,`/api/docs` 可查):
  - `GET /api/v1/ai-eval/reruns/by-usage-log/{usage_log_uid}` → 該筆所有 challenger 重跑 + 對比(無則 `200 + data.reruns=[]`)。
- **行為**:`AI_RERUN_ENABLED=false`(預設)時**完全不觸發**任何真實重跑(零額外成本)。
- **資料隔離**:challenger 真實呼叫**不**寫入 `usage_logs`、**不**計入部門用量/成本報表(獨立新表),避免污染計費。

## 資料流 / 觸發與對比流程

```
[v2.0.1 評審完成] ai_model_evaluations.status='evaluated'(≥1 推薦)
   │  條件:AI_RERUN_ENABLED=true 且 至少一裁判推薦 ≠ 原模型
   ▼
[排程派發] dispatch_unrerun(taskiq beat,掃父表游標 ai_reran_at IS NULL 的待重跑筆)
   │  逐筆 → rerun task
   ▼
[rerun task] 對「三裁判推薦模型去重後、且 ≠ 原模型」的每個 challenger:
   ├─ 1) 真實呼叫 challenger(同原輸入快照,非串流,走 DEFAULT_OPENROUTER_KEY,不寫 usage_logs)
   │     → 取 challenger 輸出 / tokens / cost / latency / status
   ├─ 2) 客觀指標:cost_delta = challenger_cost − original_cost(tokens / latency 同記)
   ├─ 3) AI discriminator:比對「原輸出 vs challenger 輸出」對任務何者較佳
   │     → winner(original/challenger/tie)+ reason(+ 可選 score)
   └─ 4) 寫一筆 ai_model_eval_reruns(原子);全部 challenger 完成 → 標父表游標 ai_reran_at/status
   ▼
[前端] AI 判決詳細資訊頁(v2.0.4)內嵌:逐 challenger 列「模型 / 成本Δ / 延遲 / 裁決 winner / 理由」
```

**狀態機**(父表 `ai_model_evaluations` 重跑游標,對齊 v2.0.1 評審游標設計):

| 狀態 | 條件 | 說明 |
| --- | --- | --- |
| 未重跑 | `ai_reran_at IS NULL` | 尚未輪到 / `AI_RERUN_ENABLED=false` / 無 ≠ 原模型的推薦(跳過也標終局) |
| 重跑成功 | `ai_rerun_status=1` | ≥1 challenger 跑完(含 discriminator) |
| 重跑失敗 | `ai_rerun_status=0` | 全 challenger 失敗(終局,不重派) |

## 資料模型(新表 + 父表游標)

### 4.1 新表 `ai_model_eval_reruns`(一筆 = 一個 challenger 的真實重跑 + 對比)

必備欄位(`pid` / `ai_eval_rerun_uid` / `is_active` / `is_deleted` / `created_at` / `updated_at`,對齊 `04-databases/90-project-database.md`)外:

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| `ai_evaluation_uid` | UUID | 軟引用父評審(來自哪次評審的推薦) |
| `usage_log_uid` | UUID | 軟引用原始 log(同輸入來源) |
| `ai_candidate_uid` | UUID? | 軟引用是哪個裁判候選推薦的(可追溯;去重合併時取代表者) |
| `original_model` | String(128) | 原模型 key(denormalize,對比顯示) |
| `rerun_model` | String(128) | challenger 模型 key(實際重跑) |
| `model_uid` | UUID? | challenger model_uid(軟引用 models) |
| `request_content` | JSONB? | 重跑輸入快照(可重現;沿用原 log 輸入) |
| `response_summary` | JSONB? | challenger 真實輸出(`{output_text, usage?}`) |
| `prompt_tokens`/`completion_tokens`/`total_tokens` | Integer | challenger 真實 token |
| `cost_usd` | Numeric(12,6) | challenger 真實成本 |
| `original_cost_usd` | Numeric(12,6)? | 原呼叫成本(denormalize,對比) |
| `cost_delta_usd` | Numeric(12,6)? | challenger − original(客觀指標) |
| `latency_ms` | Integer | challenger 延遲 |
| `status` | String(16) | success / error |
| `error_code` | String(64)? | NULL=無錯誤 |
| `openrouter_generation_id` | String(64)? | OpenRouter 生成 ID |
| `compare_winner` | String(16)? | discriminator 判決:original / challenger / tie |
| `compare_score` | Numeric(4,3)? | **信心分數**(0–1):discriminator 依真實輸出對比,評「原 AI 推薦(該換成 challenger)是否合理」的信心。高=真憑據支持原推薦(challenger 確實較好);低=原推薦站不住(維持原模型較好)。(B) 啟用時必填;停用時 NULL。 |
| `compare_reason` | Text? | 裁決理由 |
| `compare_judge_model` | String(128)? | 擔任 discriminator 的模型 key(=**推薦該 challenger 的評審模型本人**,自我裁決;去重取代表者) |
| `triggered_at` | TIMESTAMPTZ | 重跑執行時間(UTC+8) |

- **冪等**:`UNIQUE(ai_evaluation_uid, rerun_model)`(不分軟刪),避免同 challenger 重複重跑。
- **索引**:`(usage_log_uid)`、`(ai_evaluation_uid)` partial(`is_deleted=false`),供前端/查詢。

### 4.2 父表 `ai_model_evaluations` 增重跑游標(migration)

- `ai_reran_at TIMESTAMPTZ NULL`:最新一次重跑執行時間;NULL=待重跑(派發掃描鍵)。
- `ai_rerun_status SMALLINT NULL`:NULL=未重跑 / 0=失敗 / 1=成功(成敗皆標,終局不重派)。

> 設計對齊 v2.0.1:用「父表游標 + IS NULL 掃待派 + 終局化(成敗皆標)」,而非搶佔鎖;冪等靠新表 UNIQUE。

## 後端

### 5.1 觸發排程(taskiq beat)

- `dispatch_unrerun`(對齊 `dispatch_unevaluated`,**沿用其 beat 排程與批量常數,不新增 env**):`AI_RERUN_ENABLED=false` → return 0;否則掃父表 `ai_reran_at IS NULL 且 status='evaluated'` 前 N 筆(N=既有評審派發批量),逐筆 `rerun_evaluation_task.kiq`。
- **跳過條件**(標終局、不重跑):無任何「推薦 ≠ 原模型」的裁判(全員建議維持)→ `ai_reran_at=now(), ai_rerun_status=1`,challenger 0 筆。

### 5.2 rerun service(純業務核心,可獨立測)

- 取父評審 + 候選(含裁判推薦)→ 算「待重跑 challenger 集合」=`{裁判推薦模型} − {原模型}`(去重)。
- **執行序(定案)**:單一 task 內各 challenger **順序處理(串行)**,非併發——逐一 `challenger → discriminator → 寫一筆`。單筆等待時間 `T = Σ(t_i + m_i)`(challenger 呼叫 + 對應 discriminator 之和);最壞 3 challenger + 3 discriminator,但去重 / 維持原模型跳過下通常更少。背景管線、非即時阻塞使用者,以串行換取「不瞬時打爆 OpenRouter 速率 + 每日預算閘逐筆累加好控管」。
- 對每個 challenger:組原輸入快照 payload → `chat_completion`(非串流,`DEFAULT_OPENROUTER_KEY`,**不**寫 usage_logs)→ 解析輸出 / usage → 反查 models 算 `cost_usd`(沿用既有計費算法)→ `cost_delta`。
- **AI discriminator**(§5.3)→ winner / reason。
- 單一 challenger 一筆 `ai_model_eval_reruns`(原子);全完成標父游標。**單一 challenger 失敗不阻斷其他**;全失敗 → `ai_rerun_status=0`。
- 錯誤對外收斂 `AppError`,細節進結構化 log(不洩金鑰)。

### 5.3 AI discriminator(對比裁決 prompt + service)

- **子開關 `AI_RERUN_DISCRIMINATOR_ENABLED`(§7)**:false → service 跳過本環節,該 challenger 仍寫一筆(含 (A) 真實重跑客觀指標),但 `compare_winner` / `compare_score` / `compare_reason` / `compare_judge_model` 留 NULL;前端對應顯示「未裁決」。true(預設)→ 執行下列完整對比。
- **誰推薦、誰自我裁決**(定案):discriminator **不是固定單一裁判**,而是**推薦該 challenger 的那個評審模型本人**。例:評審 `claude-opus-4-8` 推薦 `gemini-2.5` → 打 `gemini-2.5` API 取真實輸出 → **再用 `claude-opus-4-8`** 裁決「自己推薦的 `gemini-2.5` vs user 實際用的原模型,哪個對任務較好」。去重時(§4)由代表者裁判擔任。`compare_judge_model` = 該裁判模型 key。
- **盲化裁決**(定案,§11 #7):prompt **不揭露兩側模型名**,只給「輸出 A / 輸出 B + 任務」讓裁判盲選,事後映射回 original / challenger。避免裁判對自己推薦的模型有自我偏好偏差(self-preference)。
- 新 prompt builder:輸入「使用者原輸入 + 輸出 A + 輸出 B(原模型/challenger 隨機匿名化)+ 任務」,要求輸出結構化 JSON `{winner, reason, score}`:`winner`=A/B(映射回 建議改用/維持/平手);`score`=**信心分數 0–1**(對原推薦合理度的信心);`temperature=0`(對齊 v2.0 fixed §2)。

### 5.4 查詢 API(唯讀,admin)

- `GET /api/v1/ai-eval/reruns/by-usage-log/{usage_log_uid}`(`AdminDep`);回該 log 對應評審的所有 challenger 重跑 + 對比;無 → `200 + {reruns: []}`。
- Response schema(Pydantic;Decimal→字串,對齊既有慣例):`RerunResult`(逐 challenger:模型 / tokens / cost / cost_delta / latency / status / winner / **score 信心分數** / reason)。
- 落點:新檔 `app/api/v1/ai_eval_reruns.py`(讀寫分檔,對齊 v2.0.3 `ai_eval_results.py`)。

## 前端(摘要層 + 詳細層)

> **落點(定案)**:v2.0.4 細看專頁未建,本版**不依賴它**;摘要層與詳細層**都放在現有 `/usage-logs/[uid]` 的 AI 分析卡**(v2.0.3 已建),詳細採 **inline 展開**。未來 v2.0.4 上線可平移。

### 6.1 摘要層 · AI 分析卡「AI 判決結果」欄位(每 usage_log 一筆)

- 落點:`/usage-logs/[uid]/page.tsx` 既有 **AI 分析卡** 內新增「**AI 判決結果**」欄位。
- **每條 usage_log 對應一筆**:讀父表 `ai_model_evaluations` + 彙總其底下(去重後)的 challenger 子列 `ai_model_eval_reruns`。
- **緊湊顯示**:`原始(原模型) → 模型1 / 模型2 / 模型3 …`(去重後 challenger)的對應;每個 challenger 附極簡指示(裁決 Badge 建議改用/維持/平手 + 信心分數),整體可給一個彙總結論(如「2/3 建議維持」)。
- **點開** → 同卡 **inline 展開** §6.2 詳細區塊(對齊既有「點開看詳細」互動)。
- 狀態:未重跑 / 重跑中 / 重跑失敗 / 已重跑 / **已重跑·未裁決**((B) 關閉,`compare_*` NULL)。

### 6.2 詳細層 · 同卡 inline 展開「真實重跑對比」

- 落點:AI 分析卡內 inline 展開區塊(非獨立路由;v2.0.4 上線後可遷該專頁)。
- 內容:逐 challenger 卡/列——challenger 模型 + tier、真實成本與 **成本Δ**(綠=更省/紅=更貴)、延遲、**裁決 Badge**(建議改用/維持/平手)+ **信心分數**(對原推薦合理度,如 0–1 或 %)+ 理由、challenger 輸出(可展開)。
- 狀態:未重跑 / 重跑中 / 重跑失敗 / 已重跑 / 已重跑·未裁決。
- 型別 / 端點常數 / label 集中(對齊 v2.0.3 `ai-eval-labels.ts` 慣例)。

## 設定(環境變數)

> **本版新增 env,須同步 `.env.example` 與 `.env`**(對齊 `00-overview/02-secrets.md`、`03-env-layers.md`;CLAUDE.md 開發前必檢查)。

| 變數 | 預設 | 說明 |
| --- | --- | --- |
| `AI_RERUN_ENABLED` | `false` | **總開關**:管整個第二層。false 時完全不觸發 (A) 真實重跑與 (B) 對比裁決,零成本。對齊 `AI_EVAL_ENABLED`。 |
| `AI_RERUN_DISCRIMINATOR_ENABLED` | `true` | **(B) 對比裁決子開關**(須 `AI_RERUN_ENABLED=true` 才生效):true → 真實重跑後再讓 AI discriminator 裁決(完整 GAN 閉環);false → 只做 (A) 真實重跑取客觀指標(cost/tokens/延遲 delta),**跳過 AI 裁決**,`compare_*` 欄位留 NULL。用於「只想要真實成本對比、暫省較貴的裁判呼叫」。 |
> **本版只新增上面兩顆開關**。派發批量 / 排程間隔**不另立 env**:`dispatch_unrerun` **沿用既有評審派發(`dispatch_unevaluated`)的 beat 排程與批量常數**(已同步,免重複設定)。每日預算閘(`AI_RERUN_DAILY_BUDGET_USD`)**不導入**(§11 #1)——成本控管靠「總開關預設關 + 去重 + 維持原模型跳過」。
>
> challenger 與 discriminator 呼叫沿用 `DEFAULT_OPENROUTER_KEY`(內部呼叫,不經 SDK proxy、不寫 usage_logs)。

## 風險與相依

- **成本風險(高)**:自動 + 三裁判各跑 + discriminator = 每筆最多 **3×(challenger)+ 3×(discriminator)** 真實呼叫。控管靠 `AI_RERUN_ENABLED` **預設關** + **去重**(三裁判推薦同模型只跑一次)+ **維持原模型跳過** + discriminator 子開關可省 (B)。**不導入每日預算閘**(§11 #1,user 決議),啟用前由 admin 自行評估。
- **v2.0.4 未建**:原規劃的「AI 判決詳細資訊」細看專頁(propose-v2.0.3 順延 slot)**至今未實作**。本版**不依賴 v2.0.4**:摘要 + 詳細**都落在現有 `/usage-logs/[uid]` 的 AI 分析卡**(詳細採 inline 展開,§6.2);未來 v2.0.4 上線再遷移。
- **PII**:challenger 重跑會把原輸入(可能含 PII)**再次外送**;對齊 v2.0.1「本版不遮罩、保留 mask hook」現況(§11 確認是否沿用)。
- **第三方**:OpenRouter 真實計費 + 速率;對齊 `90-third-party-service/50-openrouter.md`、`02-rate-and-cost.md`。
- **資料正確性**:`original_cost_usd` 對歷史 log 可能為近似(沿用 usage_logs.cost_usd);無原成本時 `cost_delta` 留 NULL。

## 驗收標準

- `AI_RERUN_ENABLED=false` → `dispatch_unrerun` 回 0、無任何重跑、無新表寫入。
- `=true` 且推薦 ≠ 原模型 → 對去重 challenger 各寫一筆 `ai_model_eval_reruns`,含真實 cost / cost_delta / winner;父游標標終局。
- `AI_RERUN_DISCRIMINATOR_ENABLED=false` → 仍寫 challenger 真實重跑列(客觀指標齊全),但 `compare_*` 全為 NULL、無 discriminator 呼叫;`=true`(預設)→ `compare_winner`/`reason` 有值。
- 單一 challenger 失敗不阻斷其他;全失敗 → 父 `ai_rerun_status=0`。
- challenger 呼叫**不**出現在 `usage_logs`(SQL 驗證不新增 usage_logs 列)。
- `GET .../reruns/by-usage-log/{uid}` admin 可取、非 admin 403、無資料回 `200 + reruns:[]`。
- 後端單元/整合測試(respx 攔截 challenger + discriminator);`/api/docs` 可查新 API;`.env.example` 同步。
- Migration round-trip(up/down)通過。

## 設計取捨 / 已決議(user 拍板,2026-06-26)

> **全數拍板,無待確認項。**

**核心機制**:自動觸發、客觀指標 + AI discriminator(GAN)、三裁判推薦各跑(去重)、獨立新表(不混 usage_logs)、env flag 控管、單一 task 內 challenger 串行處理(非併發,§5.2)。

| # | 決議 | 落點 |
| --- | --- | --- |
| 1 | **不導入每日成本閘**(`AI_RERUN_DAILY_BUDGET_USD` 取消);控管靠總開關預設關 + 去重 + 維持原模型跳過 | §7、§8 |
| 2 | discriminator =**推薦該 challenger 的評審模型本人**(自我裁決,非固定單一裁判);去重取代表者 | §5.3、§4.1 |
| 3 | **不加**抽樣門檻 / 吻合度門檻(初版,先靠總開關控成本) | §5.1 |
| 4 | 去重:三裁判推薦同 challenger → 合併一筆,`ai_candidate_uid` 取代表者 | §4.1 |
| 5 | PII 再送:**沿用 v2.0.1 不遮罩**現況(保留 mask hook) | §8 |
| 6 | 前端落點:**不依賴未建的 v2.0.4**;摘要 + 詳細(inline)都落在現有 `/usage-logs/[uid]` AI 分析卡;原 v2.0.4 slot 取消 | §6 |
| 7 | discriminator **盲化**:不揭露兩側模型名,只比輸出 A/B(避免自我偏好偏差) | §5.3 |
| 8 | **不新增** batch / interval env;`dispatch_unrerun` 沿用 `dispatch_unevaluated` 排程與批量常數 | §5.1、§7 |
| 9 | 版號定案 **v2.1.0**(新表+新 endpoint=minor,規則強制);原 v2.0.4 細看專頁併入本版 §6 | 開頭 slot |

## 變更紀錄

| 日期 | 改動 | 理由 |
| --- | --- | --- |
| 2026-06-26 | 初版(真實重跑 + 對比裁決;升為 v2.1.0) | 把「只憑文字判斷」升級為有真憑據的 GAN 閉環;需新表/管線/前端區塊故 minor bump |
| 2026-06-26 | 明定 challenger 串行執行序(§5.2 + 已決議) | 拍板單一 task 內順序處理,避免拆 tasks 誤解為可併發;背景跑、延遲無感、利於速率/預算控管 |
| 2026-06-26 | 新增 (B) 對比裁決子開關 `AI_RERUN_DISCRIMINATOR_ENABLED`(§5.3/§7) | 拆出 discriminator 獨立開關,可只做真實重跑取客觀成本對比、暫省較貴的 AI 裁決呼叫 |
| 2026-06-26 | `compare_score` 正名為「信心分數」(§4.1/§5.3/§5.4/§6) | (B) 的本質是用真實輸出回頭驗證「原 AI 推薦是否合理」,產出信心分數;一路接到查詢 API 與前端 |
| 2026-06-26 | 前端拆摘要層 + 詳細層(§6.1/§6.2) | AI 分析卡加「AI 判決結果」欄位(每 usage_log 一筆,原始→模型1/2/3 對應,點開展開詳細) |
| 2026-06-26 | §11 全數拍板收斂;v2.0.4 未建→本版不依賴、slot 併入 §6;discriminator 改「推薦者自我裁決 + 盲化」;移除每日預算閘與 batch/interval env | user 逐條決議 #1–#8 + 版號定案 v2.1.0;落點改現有 `/usage-logs/[uid]` AI 分析卡 |
