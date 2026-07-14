[//]: # (此檔為 v2.2.0 任務提案,實作前先由使用者確認範圍與設計取捨。Agent 草擬、User 拍板。)

# Propose v2.2.0 · AI 評審(第一層模型推薦)成本優化——原文截斷、Prompt 重排 + 快取、白名單瘦身、重複輸入去重(附成本量測)

> 此為 **proposal**(詳設母本),確認後即據以拆 `workflow/` + `tasks/`。
>
> 對應母本鏈:[v2.0.1 AI 模型適配評審](../v2.0/propose-v2.0.1.md)(三裁判判別管線,本版優化對象)→ 本版。v2.1.0 真實重跑 / 對比裁決層**不在本版範圍**(見 Out of Scope)。
>
> **狀態**:**草稿,待 user 拍板**(§D 各項)。範圍已依 user 指示(2026-07-14)收斂:主體為截斷 / 重排+快取 / 白名單瘦身 / 去重四項;**三裁判制度與裁判模型配置為不可變約束**(見規範層級註記)。

---

## ⚠️ 版號判定註記

依 [`01-propose/05-version-bump.md`](../../Design-Base/01-propose/05-version-bump.md) 判準:

- 含 DB migration(評審候選子表加量測欄位、usage_logs 加去重雜湊欄)、新增 env、且改變內部評審行為(prompt 結構 / 截斷 / 去重跳評)→ 屬 **minor**,落 **v2.2.0**(user 指定)。
- 對外 API **無**任何變更(全部是內部評審管線),舊 client 零影響。

## ⚠️ 規範層級註記 + 不可變約束

已檢查 `docs/Design-Base/*`:**無**規範觸及評審 prompt 結構 / 裁判數 / 原文外送策略——這些均為 **propose-v2.0.1 層決議**(Tasks 層),非 Design-Base 地板。本版推翻其中三項 v2.0.1 決議,依規範演進精神於此**明列並待 user 拍板**:

1. **「原文 I/O 全文外送」→ 改為「截斷後外送」**(§B.1 / §D.1)。
2. **「prompt 結構:白名單 / enum / schema 置於 user message」→ 改為「靜態內容集中 system prompt」**(§B.2 / §D.2)。
3. **「全量評審(每筆 usage_log 必評)」→ 改為「重複輸入於時間窗內去重跳評」**(§B.4 / §D.5)。

**不動**的 v2.0.1 決議:三裁判、非盲測(面試式評選)、禁推薦 free、temperature=0、首個成功評審拍板父表。

**user 明示不可變約束(2026-07-14)**:❶ **三裁判制度不可變**(不做「單裁判 + 條件升級」,亦不列為後續方向);❷ **裁判模型配置不可變**(不以「換便宜裁判」作為優化手段)。本版優化僅限「不動裁判數、不動裁判模型」前提下的 payload / 快取 / 派發層面。

---

## 版本目標

第一層 AI 評審(`evaluate_usage_log`:每筆 usage_log × 3 裁判推薦最適合模型)是目前 AI 分析的主要成本來源,且 input 高度重複:

- **靜態內容重複**:system prompt + 候選白名單 + intent enum + JSON 範例(合計約 900–1,200 tokens)每筆每裁判重送重算錢,且變動內容(目前模型)排在前面,provider 的前綴快取完全命中不了。
- **原文重複且不設限**:使用者輸入 + 原模型輸出**全文**外送 ×3 裁判;長輸出任務(程式碼生成等)單筆三裁判 input 可達數萬 tokens。
- **重複輸入重複評**:同一使用者對同一模型送高度相同的輸入(重試 / 例行任務),每筆都完整跑三裁判,結論幾乎必然相同。
- **成本盲區**:內部評審呼叫刻意不寫 `usage_logs`,3 裁判呼叫的實際花費**無任何記錄**,無法歸因、無法驗證優化成效。

在「三裁判、裁判模型皆不動」的約束下,本版四刀 + 一支撐,目標把第一層評審 input 成本降至現況的 **40–60%**(去重省幅另計,視實際重複率):

1. **原文截斷**:輸入 / 輸出原文頭尾截斷封頂,砍最大變動 token 塊。
2. **Prompt 重排 + 快取**:靜態內容集中 system prompt 成穩定前綴,吃各 provider 的 prompt caching(OpenAI 自動 / Anthropic `cache_control` 透傳 / Gemini・DeepSeek 自動)。
3. **候選白名單瘦身**:依請求 modality 預過濾,縮 payload 兼提升推薦品質。
4. **重複輸入去重**:同 user + 同模型 + 相同輸入於時間窗內已有成功評審 → 跳評(不打 OpenRouter),整筆 ×3 呼叫直接省下。
5. **(支撐)評審成本量測**:每次裁判呼叫的 tokens / cost / cached_tokens 落子表——功能二的快取命中、功能四的去重省幅都靠它驗收,成本自此可歸因。

## In Scope

### 功能一 · 原文截斷(§B.1)

- `build_judge_prompt` 的 `_render_input` / `_render_output` 增加截斷:超過上限時保留**頭 + 尾**、中間以「(中略 N 字)」標記(判 intent / complexity / fit 頭尾資訊已足)。
- 上限走 env:`AI_EVAL_INPUT_MAX_CHARS` / `AI_EVAL_OUTPUT_MAX_CHARS`(預設值見 §D.1;設 `0` = 不截斷,保留回退路)。
- 實作層級與既有 `text_masker` hook 同層(純函式、可獨立測);**只影響評審 payload,不動 usage_logs 快照**(DB 內仍是全文)。

### 功能二 · Prompt 重排 + Prompt Caching(§B.2)

- **重排**:候選白名單、intent enum、JSON 範例由 user message 搬進 **system prompt**;user message 只剩每筆變動內容(目前模型 + 截斷後 I/O)。system prompt 成為跨 log 的穩定前綴(白名單僅 models 表變動時才變)。
- **Anthropic 裁判**:model_key 前綴為 `anthropic/` 時,system 區塊注入 `cache_control: {type: "ephemeral"}`(OpenRouter 透傳;cache write +25%、read 0.1×,批次派發下必然划算,開關見 §D.3)。
- **其他 provider**(OpenAI / Gemini / DeepSeek 等):前綴快取自動生效,無需 payload 改動;命中與否由功能五的 `cached_tokens` 驗證。
- 快取命中依賴現有派發節奏(batch 100 筆 / 300 秒一輪 / 同裁判連續打,落在各家 ~5 分鐘 TTL 內),**不改派發機制**。

### 功能三 · 候選白名單瘦身(§B.3)

- `evaluate_usage_log` 組候選白名單時,依該筆 `request_content` 的 modality 預過濾:請求含 images → 只列具 vision 能力的模型;純文字 → 全列(規則見 §D.4)。
- 白名單變體數量刻意壓在**兩種**(文字版 / 視覺版),與功能二協同:每種變體各自是穩定快取前綴,不因逐筆過濾打散快取(見風險節)。
- 免費模型過濾(`:free`)不變;裁判端防呆(`_is_free_model` 作廢推薦)不變。

### 功能四 · 重複輸入去重(§B.4)

- **去重鍵**:`user_uid + model + 輸入內容雜湊`(SHA-256,精確比對;不做相似度比對,見 §D.5)。
- `usage_logs` 加 `ai_dedup_hash` 欄(migration;寫入時由 proxy 計算,舊資料 NULL 不參與去重)。
- **worker 端短路**(沿既有冪等短路模式):評審前查「同去重鍵、`AI_EVAL_DEDUP_WINDOW_DAYS` 內、已有**成功**評審(`ai_evaluated_status=1`)的 usage_log」→ 命中則**跳評**:不打 OpenRouter、不建父表,游標標 `ai_evaluated_at=now()` + `ai_evaluated_status=2`(新語意:去重跳過,見 §D.6),dispatcher 不重撈。
- 總開關 env:`AI_EVAL_DEDUP_ENABLED`;關閉 = 現況全量評審。

### 功能五 · 評審呼叫成本量測(支撐項,§B.5)

- `_run_one_judge` 取回應 `usage`(payload 加 `usage: {include: true}`,對齊 rerun / proxy 計費取法),記錄:`prompt_tokens`、`completion_tokens`、`cost_usd`、`cached_tokens`(`prompt_tokens_details.cached_tokens`,provider 支援才有)、`latency_ms`。
- 候選子表 `ai_model_eval_candidates` 加上述五欄(migration),每列 = 該裁判該次呼叫的實測成本;失敗評審留 NULL。
- 結構化 log 同步輸出單次呼叫成本摘要(不含 api key / 原文)。
- 本版僅落庫 + log 回看(SQL 聚合),不做 UI(§D.7)。

## Out of Scope

- **三裁判 → 單裁判 / 條件升級**:user 明示三裁判制度**不可變**,不做、不列後續方向。
- **裁判模型更換**:user 明示裁判模型配置**不可變**,不作為優化手段。
- **隨機抽樣評審**:去重(功能四)是「相同輸入不重評」的確定性語意;隨機抽樣會漏評新輸入、且與全量精神衝突,本版不做。
- **相似度去重(embedding / 模糊比對)**:只做精確雜湊比對;相似度方案複雜度高、誤跳評風險大,不做。
- **真實重跑 / 對比裁決層(v2.1.0)優化**:重跑門檻、裁決 payload 截斷等,另版處理。
- **多筆合批單一 prompt**:與「一筆一父表」冪等設計衝突,解析連坐風險高,不做。
- **前端呈現評審成本 / 去重狀態**:子表新欄位與 `ai_evaluated_status=2` 本版不上前端(評審明細 UI 不動);日後需要另提。
- **usage_logs 快照截斷**:DB 快照維持全文(截斷只作用於評審 payload)。
- **派發機制改動**:不為快取命中率改派發順序 / 分組;若量測顯示命中率低,另提。

## 對外承諾

- **對外 API 零變更**:SDK / chat 端點 / 前端頁面行為完全不變(本版全在內部評審管線;proxy 僅多寫一個內部欄位 `ai_dedup_hash`,對呼叫端不可見)。
- **行為承諾**:
  - 評審 payload 有截斷上限,單筆評審 input 成本封頂;`AI_EVAL_*_MAX_CHARS=0` 可退回全文行為。
  - Anthropic 系裁判在批次派發下穩定命中 prompt cache(`cached_tokens > 0` 可驗)。
  - 時間窗內相同輸入(同 user + 同模型)只完整評審一次,重複者零 OpenRouter 呼叫;`AI_EVAL_DEDUP_ENABLED=false` 可退回全量。
  - 每筆評審的每個裁判呼叫,成本(tokens / USD / 快取命中)可於子表查得、可按模型 / 部門聚合。
- **文件承諾**:`.env.example` 同步新 env;`docs/Tasks/v2.2/` 留決議紀錄。無對外使用者文件需同步(未動對外 API 鏈路)。

## 資料流(優化後)

```
[proxy] 寫 usage_logs 時計算 ai_dedup_hash(user_uid + model + 輸入內容 SHA-256)
   ▼
[dispatch_unevaluated] 每 300s 撈 ≤100 筆 → evaluate_usage_log_task ×N
   ▼
evaluate_usage_log_task(worker):
   ├─ 冪等短路:父表已存在 → skip(現況)
   ├─ 去重短路(功能四):同 hash、窗內已有成功評審
   │     → 不打 OpenRouter、不建父表,游標標 ai_evaluated_status=2,return
   ▼
evaluate_usage_log:
   ├─ 候選白名單:active 非 free + modality 預過濾(功能三;變體 ∈ {text, vision})
   ├─ build_judge_prompt(重排後,功能一二):
   │    system  = 評審規則 + 白名單(變體)+ enum + JSON 範例   ← 穩定前綴(~900–1,200 tok)
   │    user    = 目前模型 + 截斷後輸入 + 截斷後輸出            ← 每筆變動
   │    (裁判為 anthropic/* → system 加 cache_control)
   ▼
×3 裁判 chat_completion(payload + usage:{include:true})       ← 三裁判不變(不可變約束)
   │   同裁判連續呼叫 → 前綴快取命中(OpenAI 自動 / Anthropic ephemeral / Gemini・DeepSeek 自動)
   ▼
解析 JudgeOutput(不變)+ 取 usage(功能五)
   ▼
create_evaluation_with_candidates:父表(不變)+ 子表(原欄位 + 量測五欄)原子落地
```

## 後端(§B)

### B.1 原文截斷

- 落點:`backend/app/services/ai_model_eval_prompt.py`。
- 新增純函式 `truncate_middle(text, max_chars, head_ratio)`:`len(text) <= max_chars` 原樣返回;超過 → `頭 head_ratio 比例 + "\n…(中略 {N} 字)…\n" + 尾段`。`head_ratio` 常數 0.7(頭重尾輕:任務意圖多在開頭,結尾保收束語氣)。
- `_render_input` 對 text 套 `AI_EVAL_INPUT_MAX_CHARS`;`_render_output` 對 output_text 套 `AI_EVAL_OUTPUT_MAX_CHARS`;`0` = 不截斷。
- 截斷發生在 `text_masker` **之後**(先遮罩後截斷,遮罩語意不受影響;本版 masker 仍為 identity)。
- env 由 `build_judge_prompt` 參數注入(保持 prompt 模組純函式、無 config 依賴;caller `evaluate_usage_log` 讀 settings 傳入)。

### B.2 Prompt 重排 + 快取

- 落點:`backend/app/services/ai_model_eval_prompt.py`(結構)、`backend/app/services/ai_model_eval.py`(cache_control 注入判定)。
- system prompt 改為組合式:`評審規則(現 _SYSTEM_PROMPT)+ "## 候選白名單…" + "## task_intent 枚舉…" + "## 回傳 JSON 範例…"`;user message 剩 `## 目前模型` + `## 使用者輸入` + `## 目前模型輸出`。
- **區塊順序即快取前綴**:靜態不變內容(評審規則 / enum / 範例)在前,白名單(三塊中唯一會變者)殿後——白名單變動時前綴命中損失最小。
- Anthropic 注入:裁判 model_key 前綴 `anthropic/` 且 `AI_EVAL_PROMPT_CACHE_ENABLED=true` → system message 改 parts 形式 `[{type:"text", text:…, cache_control:{type:"ephemeral"}}]`(OpenRouter 相容格式);其他 provider 維持純字串 system,不注入。
- 快取命中**不做保證**(多 worker 併發 / 批距拉長會掉),僅以功能五 `ai_cached_tokens` 觀測;不因此改派發機制。

### B.3 白名單瘦身

- 落點:`backend/app/services/ai_model_eval.py`(`evaluate_usage_log` 候選組裝段)。
- 判定:該筆 `request_content.images` 非空 → 白名單過濾為「支援 image 輸入」的模型(依 `models` 的 modality 欄,v1.7 `0007_model_modality_tags` 既有資料);純文字請求 → 不過濾(全列)。
- 過濾後白名單為空 → 回退全列(防呆,寧可多列不可無候選);tier 反查表(`tier_by_model_key`)維持全量 active,不受過濾影響。
- 白名單變體固定兩種(text / vision),與 B.2 快取協同:同裁判同變體 = 同前綴。

### B.4 重複輸入去重

- 落點:`backend/app/services/proxy.py`(hash 寫入)、`backend/app/models/usage_log.py` + migration(`ai_dedup_hash` 欄 + 部分索引)、`backend/app/repositories/usage_log.py`(去重查詢)、`backend/app/tasks/ai_model_eval.py` 或 `services/ai_model_eval.py`(短路判定,落點見 §D.6)。
- **hash 計算**(proxy 寫 log 時):`SHA-256(user_uid + model + canonical(輸入內容))`;輸入內容 = 單輪模式的 `text`(+ images/files 的存在性摘要),messages 模式(v2.1.2)= messages 序列化正規形(§D.5 細則)。計算失敗 → NULL(不參與去重,不影響主鏈路)。
- **欄位與索引**:`usage_logs.ai_dedup_hash: String(64) | NULL`;部分索引 `(ai_dedup_hash, created_at)` where `ai_dedup_hash IS NOT NULL`(去重查詢走索引;舊資料 NULL 零成本)。
- **短路判定**(worker 端,插在既有「父表已存在」短路之後):查同 `ai_dedup_hash`、`created_at >= now() - AI_EVAL_DEDUP_WINDOW_DAYS`、`ai_evaluated_status = 1` 的**他筆** usage_log 存在 → 本筆標 `ai_evaluated_at = now()`、`ai_evaluated_status = 2`,不建父表、不打 OpenRouter,return。
- **游標語意擴充**:`ai_evaluated_status` 由 `NULL/0/1` 擴充為 `NULL(未跑)/0(失敗)/1(成功)/2(去重跳過)`;dispatcher 撈取條件(`ai_evaluated_at IS NULL`)不變,天然相容。
- 只比對到「成功評審(=1)」才跳;比對對象若之後被軟刪 / 資料異動,不回溯(跳過為終局,對齊既有游標終局化精神)。

### B.5 成本量測

- 落點:`backend/app/services/ai_model_eval.py`(`_run_one_judge`、`_build_candidate`)、`backend/app/repositories/ai_model_evaluation.py`(`CandidateInput`)、`backend/app/models/ai_model_eval_candidate.py` + migration。
- 子表新欄(皆 nullable;失敗評審 / provider 未回傳時 NULL):
  - `ai_prompt_tokens: int`、`ai_completion_tokens: int` — 該次裁判呼叫 token 數。
  - `ai_cached_tokens: int` — 命中快取的 prompt tokens(`usage.prompt_tokens_details.cached_tokens`;缺欄 → NULL)。
  - `ai_cost_usd: Numeric(12, 8)` — 該次呼叫實際成本(`usage.cost` / `total_cost`,對齊 rerun 取法)。
  - `ai_latency_ms: int` — 呼叫耗時(client 端量測)。
- `_run_one_judge` 回傳擴充(`_JudgeResult` 加 usage 欄);payload 加 `"usage": {"include": true}`(落點見 §D.8)。
- 欄位 comment 依既有雙語慣例;baseline SQL 不回填(沿 alembic 慣例)。

## 設定(環境變數)

| env | 預設 | 說明 |
| --- | --- | --- |
| `AI_EVAL_INPUT_MAX_CHARS` | `8000`(§D.1 待拍板) | 評審 payload 使用者輸入截斷上限(字元);`0` = 不截斷 |
| `AI_EVAL_OUTPUT_MAX_CHARS` | `8000`(§D.1 待拍板) | 評審 payload 原模型輸出截斷上限(字元);`0` = 不截斷 |
| `AI_EVAL_PROMPT_CACHE_ENABLED` | `true`(§D.3 待拍板) | Anthropic 裁判 system 注入 `cache_control` 開關 |
| `AI_EVAL_DEDUP_ENABLED` | `true`(§D.5 待拍板) | 重複輸入去重跳評總開關;`false` = 全量評審(現況) |
| `AI_EVAL_DEDUP_WINDOW_DAYS` | `7`(§D.5 待拍板) | 去重回看時間窗(天) |

- 皆走既有 `coerce_int_env` / `coerce_bool_env` 容錯;`.env.example` 同步新增。
- migration 兩支:候選子表量測五欄、`usage_logs.ai_dedup_hash` + 部分索引(編號依實作時序)。

## D. 設計取捨(待 user 拍板)

### D.1 截斷預設值 — 建議「輸入 / 輸出各 8,000 字元、頭 70% 尾 30%」

- 8,000 字元 ≈ 中文 ~8k tokens / 英文 ~2k tokens,涵蓋絕大多數日常請求不觸發截斷;觸發者(長程式碼 / 長文)正是成本大戶。
- 替代案:(a) 更激進 4,000(省更多,極端案例 fit 判斷風險升);(b) token 為單位(準確但需 tokenizer 依賴,字元已足夠);(c) 只截輸出不截輸入。
- **推翻 v2.0.1「原文外送」決議,需明確拍板。**

### D.2 靜態內容全搬 system prompt — 建議採納

- 白名單 / enum / JSON 範例語意上本就是「評審規則」的一部分,搬 system 不影響裁判理解;user message 縮為純變動內容。
- 已知影響:prompt 結構改變 → 裁判輸出分佈可能輕微漂移,v2.2.0 前後的 fit_score / 推薦結果**不宜直接跨版比較**(風險節)。
- **推翻 v2.0.1 prompt 結構決議,需明確拍板。**

### D.3 Anthropic `cache_control` 注入 — 建議預設開啟(env 可關)

- cache write +25% / read 0.1×:同裁判 5 分鐘內 ≥2 次呼叫即回本;batch 100 筆場景穩賺。極低流量(單批常只有 0–1 筆)才可能小虧,故留 env 開關而非硬編。
- 替代案:不注入(Anthropic 系裁判吃不到快取,其他 provider 不受影響)。

### D.4 白名單 modality 過濾規則 — 建議「僅 vision 一刀」

- 只做「含圖請求 → 過濾出 vision 模型」一種規則;純文字請求不過濾。規則少 = 白名單變體少 = 快取前綴穩定。
- 替代案:(a) 再加 tier 相鄰過濾(如只列同 tier ±1)——變體爆增、破壞快取,不建議;(b) 不做功能三。

### D.5 去重鍵與時間窗 — 建議「user + model + 輸入精確雜湊、7 天窗、預設開啟」

- **精確比對**(SHA-256):語意最保守——只有「完全相同的輸入」才跳評,零誤跳;重試 / 例行重複任務即可涵蓋。相似度比對(embedding / simhash)召回更高但有誤跳評風險且複雜度高,列 Out of Scope。
- **鍵含 model**:同輸入換了模型仍評(換模型後的適配是新問題);替代案:鍵不含 model(更激進,同輸入任一模型評過就跳)。
- **時間窗 7 天**:模型白名單 / 裁判判準會演進,太長的窗會讓舊結論凍結;替代案 3 天 / 30 天。
- **messages 模式 hash 細則**(v2.1.2 相依):對 `messages` 做正規化序列化(role + text parts;image/file parts 取存在性摘要)後 hash;實作與單輪共用 canonical 函式。
- **推翻 v2.0.1「全量評審」決議,需明確拍板。**

### D.6 去重跳過的落地形式 — 建議「游標標 2、不建父表」

- 最輕量:`ai_evaluated_status = 2` 即終局,dispatcher 不重撈;無父表 = 評審列表自然不出現該筆(前端零改動)。
- 替代案:建父表 `status='skipped_duplicate'` + 參照來源評審 uid——前端可見「同前次評審」,可追溯性較好,但動父表 schema + 前端渲染,重量級;若日後要 UI 呈現再升級。
- 短路判定落點:建議 **task 端**(`evaluate_usage_log_task`,與既有「父表已存在」短路同處,worker 語意集中);替代案 service 端(可獨立測性更好但 service 需碰游標寫入)。

### D.7 量測數據回看方式 — 建議本版僅 SQL / log,不做 UI

- 子表五欄 + 結構化 log 已可聚合分析(按裁判模型 / 日期 / 部門);評審成本儀表板另提。

### D.8 `usage: {include: true}` 注入落點 — 建議 prompt 模組統一組進 base payload

- `build_judge_prompt` 回傳的 payload 直接含 `usage` 鍵(它已負責 response_format / temperature,語意一致);service 不再各自補。
- 替代案:service 端注入(prompt 模組保持「純訊息」職責)。

## 風險與相依

- **裁判輸出漂移(功能一二)**:prompt 結構與內容截斷都會改變裁判輸入 → fit_score / 推薦分佈與 v2.0–v2.1 歷史數據形成**斷點**;上線時間點需記錄,跨版分析須分段。temperature=0 不變,版內一致性不受影響。
- **截斷誤判**:關鍵資訊落在被截斷中段的極端案例,fit / 推薦品質可能下降;頭尾保留 + 「中略 N 字」明示可讓裁判知道有省略;env 可調可關。
- **去重的語意代價(功能四)**:跳評筆數沒有自己的評審資料(依 D.6 建議形式,父表無列)——部門 / 使用者聚合統計的「評審覆蓋率」會下降,屬**設計上接受**(重複輸入的結論本就相同);env 可關。
- **hash 寫入碰 proxy 主鏈路**:計算為純函式且失敗容錯(NULL 降級),不影響 chat 回應;但動到 `_build_request_log` 周邊,需測試護欄(chat 鏈路測試 v2.1.2 已補)。
- **快取命中非保證**:多 worker 併發交錯不同裁判 / 批距 > TTL 都會掉命中率;本版只觀測(`ai_cached_tokens`)不保證,**不**為快取改派發序。若量測顯示命中率低,再議「按裁判分組串行派發」(另提)。
- **cache_control 相容性**:OpenRouter 對 Anthropic 透傳 `cache_control` 為既有能力,但 system parts 形式對**非** Anthropic 模型可能不相容——故僅對 `anthropic/` 前綴注入,其他一律純字串(B.2)。
- **功能二三耦合**:白名單過濾若做成逐筆動態(如按 tier),會打散快取前綴——D.4 規則收斂為兩種變體即為此;拍板 D.4 時需連帶考慮。
- **v2.1.2 相依(功能四)**:messages 模式的 hash 正規化依賴 v2.1.2 的 `request_content` messages 快照形狀;v2.1.2 先行合入後本版才能定 canonical 細則(D.5)。
- **migration**:兩支皆純加欄 / 加索引,無資料回填、可安全上線;`usage_logs` 為大表,索引採部分索引(`IS NOT NULL`)控成本。

## 驗收標準

### 功能一(截斷)

- 輸入 / 輸出超過上限時,payload 內為「頭 + (中略 N 字) + 尾」;未超過原樣;`=0` 不截斷。
- `usage_logs.request_content` / `response_summary` DB 快照仍為全文(截斷不落庫)。
- 單元測試:邊界(恰好等於上限 / 超一字)、head_ratio 切分、中略字數正確、`0` 直通。

### 功能二(重排 + 快取)

- payload:白名單 / enum / JSON 範例在 system,user 只含目前模型 + I/O;`response_format` / `temperature` 不變。
- Anthropic 裁判 + 開關開 → system 為 parts 形式含 `cache_control`;非 Anthropic / 開關關 → 純字串 system。
- 既有評審單元測試全數更新通過(JudgeOutput 解析 / 白名單約束 / free 防呆語意不變)。
- 實測(手動驗收):同裁判連續評 ≥2 筆,第 2 筆起 `ai_cached_tokens > 0`(至少一家 provider 驗證)。

### 功能三(白名單瘦身)

- 含圖請求的候選白名單只含 vision 模型;純文字請求全列;過濾後為空 → 回退全列。
- free 過濾 / tier 反查行為不變;推薦不在白名單的防呆不變。

### 功能四(去重)

- 同 user + 同模型 + 相同輸入、窗內已有成功評審 → 後續筆:零 OpenRouter 呼叫、無父表、`ai_evaluated_status=2`、`ai_evaluated_at` 已標,dispatcher 不重撈。
- 輸入有任何差異 / 窗外 / 前次評審非成功(0)→ 正常評審。
- `AI_EVAL_DEDUP_ENABLED=false` → 行為與現況完全一致;hash 為 NULL 的舊資料不參與去重且不報錯。
- proxy 寫 log 時 `ai_dedup_hash` 正確落庫;hash 計算異常 → NULL 降級、chat 回應不受影響。
- 單元測試:短路命中 / 未命中矩陣(hash 同異 × 窗內外 × 前次狀態)、開關關閉直通、hash canonical(單輪與 messages 模式)。

### 功能五(量測)

- 評審完成後,子表每列(成功裁判)有 `ai_prompt_tokens` / `ai_completion_tokens` / `ai_cost_usd` / `ai_latency_ms`;支援快取的 provider 回傳時 `ai_cached_tokens` 有值;失敗裁判五欄皆 NULL。
- 結構化 log 有單次呼叫成本摘要;不含 api key / 原文。
- migration 升降級皆可執行;既有資料不受影響(新欄 NULL)。

## 設計取捨 / 決議

| # | 議題 | Agent 建議 | 狀態 |
| --- | --- | --- | --- |
| 1 | **三裁判制度不可變**(不做單裁判 / 條件升級) | — | ✅ user 定案(2026-07-14) |
| 2 | **裁判模型配置不可變**(不換便宜裁判) | — | ✅ user 定案(2026-07-14) |
| 3 | 範圍 = 截斷 / 重排+快取 / 白名單瘦身 / 去重(+量測支撐) | — | ✅ user 定案(2026-07-14) |
| 4 | 截斷預設值(輸入 / 輸出 8,000 字元、頭 7 尾 3)——推翻 v2.0.1 原文外送 | 採納 | ⏳ 待拍板 |
| 5 | 靜態內容全搬 system prompt——推翻 v2.0.1 prompt 結構 | 採納 | ⏳ 待拍板 |
| 6 | Anthropic `cache_control` 預設開啟(env 可關) | 採納 | ⏳ 待拍板 |
| 7 | 白名單 modality 過濾:僅「含圖 → vision」一刀 | 採納 | ⏳ 待拍板 |
| 8 | 去重鍵 = user + model + 輸入精確雜湊;窗 7 天;預設開啟——推翻 v2.0.1 全量評審 | 採納 | ⏳ 待拍板 |
| 9 | 去重跳過:游標標 `2`、不建父表 | 採納 | ⏳ 待拍板 |
| 10 | 量測僅 SQL / log 回看,不做 UI | 採納 | ⏳ 待拍板 |
| 11 | `usage:{include:true}` 由 prompt 模組組進 base payload | 採納 | ⏳ 待拍板 |

## 變更紀錄

| 日期 | 改動 | 理由 |
| --- | --- | --- |
| 2026-07-14 | 初版草擬:第一層評審成本優化(量測 / 截斷 / 重排+快取 / 白名單瘦身);單裁判升級原列 Out of Scope 待量測 | user 反映 AI 分析成本偏高、input 高度重複;Agent 依現況調查(靜態內容每呼叫重送、原文全文 ×3 裁判、成本零記錄)草擬詳設 |
| 2026-07-14 | 範圍修訂:❶ 三裁判制度、裁判模型配置改列**不可變約束**(移除「單裁判另立 propose」方向);❷ 新增功能四「重複輸入去重」(usage_logs 雜湊欄 + worker 短路跳評 + 游標語意 2);量測降為支撐項 | user 指示:三裁判與裁判模型不能動;propose 主體針對截斷 / 重排+快取 / 白名單瘦身 / 去重四項 |
