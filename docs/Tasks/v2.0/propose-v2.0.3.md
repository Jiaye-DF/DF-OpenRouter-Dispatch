[//]: # (此檔為 v2.0.3 任務提案,實作前先由使用者確認範圍與設計取捨。)

# Propose v2.0.3 · 評審結果顯示【usage-log 明細頁內嵌「AI 分析」區塊】

> 此為 **proposal**(規劃草案),確認後即轉為正式 `tasks-v2.0.3.md`。
>
> 對應母本:[v2.0.0 地基](./propose-v2.0.0.md) → [v2.0.1 判別管線](./propose-v2.0.1.md)。
> 本版為**唯讀展示層**:把 v2.0.1 已落地、目前只存在 DB 裡「沒人看得到」的評審結果,呈現到前端。**不打 OpenRouter、不改評審邏輯、不動既有欄位**。
>
> **版號 slot 調整**:propose-v2.0.0 藍圖與 propose-v2.0.2 § 8.1 原把 v2.0.3 暫定給「真實重跑」。本版把 v2.0.3 改為「評審結果顯示(基礎摘要)」(先讓管線產出在用量詳情頁可見、收斂一階段),評審線後續版號順延:**AI 分析細看專頁 → v2.0.4、真實重跑 → v2.0.5、人類裁決 → v2.0.6、成本 delta / 儀表板 → v2.0.7**(已於 § 8 確認)。

## 1. 目標(本版)

v2.0.1 的判別管線已會對 `usage_logs` 跑三評審並回寫 `ai_model_evaluations`(父)+ `ai_model_eval_candidates`(子 ×3),但**目前無任何對外 API、前端也看不到**。本版補上「看得到」這一段:

1. **後端唯讀 API**:依 `usage_log_uid` 取該筆的評審結果(父 + 子,含彙總),admin 限定。API **仍回傳完整結果(含各裁判候選)**,供 v2.0.4 細看專頁重用,免重工;本版前端只渲染其中的「基礎摘要」子集。
2. **彙總邏輯**:把三評審收斂成單一「判決結果」(平均吻合度、推薦共識、自我偏好警示)。
3. **前端內嵌(基礎摘要)**:在 **usage-logs 明細頁**(`/usage-logs/[uid]`)新增「AI 分析」**基礎摘要**區塊,一眼看完判決結果;**不放三評審逐筆明細**(逐筆細看留 v2.0.4 專頁)。涵蓋未評審 / 評審中 / 評審失敗 / 已評審四狀態。

> **本版仍不做**:**不做三評審逐筆細看 / 獨立「AI 分析」專頁(→ v2.0.4)**、不重跑真成本(v2.0.5)、無人類裁決(v2.0.6)、無成本 delta / 部門彙總儀表板(v2.0.7)。用量詳情頁維持精簡(基礎用量資訊 + 基礎評審摘要)。

## 2. 範圍(本版)

### In Scope

- **唯讀查詢 API**(§ 4):`GET /api/v1/ai-eval/evaluations/by-usage-log/{usage_log_uid}`,回傳父 + 彙總 + 三子(候選),admin 限定。
- **Response schema**(§ 4):新增 `schemas/ai_model_eval_result.py`(評審結果對外結構;Decimal 以字串傳輸,對齊既有慣例)。
- **彙總服務 + repository 查詢**(§ 5):service 組裝彙總;repository 補「依評審取候選並 join 判別模型 key/name」查詢。
- **前端「AI 分析」基礎摘要區塊**(§ 6):usage-logs 明細頁內嵌,**僅彙總卡(基礎摘要)+ 四種狀態**;不含三評審逐筆明細。

### Out of Scope

- **三評審逐筆細看 / 獨立「AI 分析」專頁**(可跨筆瀏覽、篩選、偏差統計總表)→ **v2.0.4**(本版只做明細頁內嵌的基礎摘要)。
- **真實重跑推薦模型 / 真成本** → v2.0.5。
- **人類裁決 / 複審佇列** → v2.0.6。
- **成本 delta / 部門彙總 / 儀表板** → v2.0.7。
- **部門隔離權限**:本版對齊現有 usage-logs 明細頁(admin-only),不做一般使用者部門隔離(未來才開放 User,§ 8.1)。
- **評審結果的編輯 / 刪除 / 重派 UI** → 不做(唯讀展示)。

## 3. 資料流 / 顯示位置

```
usage-logs 明細頁(/usage-logs/[uid],既有,admin-only)
   │  既有:GET /api/v1/usage-logs/{uid} → 顯示 input / output / metadata
   │  本版新增:同頁再打一支
   ▼
GET /api/v1/ai-eval/evaluations/by-usage-log/{usage_log_uid}   (admin)
   │  service 組裝:
   │    父表(dim1/2 任務分析)+ 子表 ×3(dim3/4)+ join models 補裁判 key/name
   │    → 計算彙總(平均 fit / 推薦共識 / 自我偏好計數 / 評審完成度)
   ▼
前端「AI 分析」區塊(明細頁內,既有 metadata 下方)
   ├─ 彙總卡(判決結果):任務分析 + 平均吻合度 + 推薦共識 + 自我偏好警示
   └─ 可展開:三評審明細(各裁判的推薦 / 理由 / fit / self_vote)
```

**顯示狀態機**(評審非同步,須涵蓋):

| 狀態 | 觸發條件 | 前端呈現 |
| --- | --- | --- |
| 未評審 | 無父表列(API 回 `evaluation: null`) | 灰底提示「尚未評審」(可能 `AI_EVAL_ENABLED=false` 或尚未輪到) |
| 評審失敗 | 父 `status='error'`(三評審全失敗) | 紅底提示「評審失敗」,不顯示彙總 |
| 已評審 | 父 `status='evaluated'`(≥1 評審成功) | 顯示彙總卡 + 可展開明細(部分成功時標示缺漏裁判) |
| (評審中) | 父 `status='pending'`(罕見,父列僅完成時建立) | 提示「評審中」 |

## 4. 後端 API(唯讀)

### 4.1 端點

```
GET /api/v1/ai-eval/evaluations/by-usage-log/{usage_log_uid}
權限:AdminDep(對齊 usage-logs 明細頁)
```

- **以 `usage_log_uid` 為鍵**(非 `ai_evaluation_uid`):前端明細頁手上只有 `usage_log_uid`,1:1 關係下直接以它查最自然,免先查 evaluation_uid。
- **無評審列時**:回 `200` + `{ "evaluation": null }`(不以 404,避免與「log 不存在」混淆;明細頁此時已知 log 存在)。
- 落點:擴充既有 `app/api/v1/ai_eval.py`(判別模型設定已在此),或新增 `app/api/v1/ai_eval_results.py`(§ 8.3 擇一)。

### 4.2 Response schema(新增 `schemas/ai_model_eval_result.py`)

```jsonc
{
  "evaluation": {                          // 無評審時為 null
    "ai_evaluation_uid": "…",
    "usage_log_uid": "…",
    "ai_original_model": "openai/gpt-4o-mini",
    "status": "evaluated",                 // pending / evaluated / error
    "ai_evaluated_at": "2026-06-26T10:00:00+08:00",
    "task_analysis": {                     // 來自父表 dim1/2(已是單一值)
      "summary": "使用者想…",
      "intent": "CODE_GENERATION",         // 固定枚舉(原始值;中文對照前端維護)
      "complexity": "medium"               // low / medium / high
    },
    "summary": {                           // 本版計算的彙總(§ 5)
      "judge_count": 3,
      "succeeded_count": 3,
      "avg_fit_score": "0.733",            // Decimal → 字串;null 不計入
      "min_fit_score": "0.600",
      "max_fit_score": "0.900",
      "recommend_consensus": {
        "model": "openai/gpt-4o-mini",     // 多數推薦;分歧時為票數最高者
        "tier": "fast",
        "votes": 2,                        // 該推薦得票數
        "is_split": false                  // true=無過半共識(分歧)
      },
      "self_vote_count": 0                 // 三裁判中「推薦自家廠商」的筆數(偏差警示)
    },
    "candidates": [                        // 三評審明細(失敗裁判 AI 欄位為 null)
      {
        "ai_candidate_uid": "…",
        "judge_model_uid": "…",
        "judge_model_key": "anthropic/claude-opus-4.6",  // join models 補上,供顯示
        "judge_model_name": "Claude Opus 4.6",
        "ai_recommend_model": "openai/gpt-4o-mini",
        "ai_recommend_tier": "fast",
        "ai_recommend_reason": "…",
        "ai_fit_score": "0.700",           // Decimal → 字串
        "ai_self_vote": false
      }
      // … 最多 3 筆
    ]
  }
}
```

> `judge_model_key` / `judge_model_name`:子表只有 `model_uid`,需 join `models` 補出 key 與顯示名(否則前端只看到 UUID)。判別模型若已被軟刪,仍盡量以 `model_uid` 取既有 models 列補名;取不到則 key/name 留 null,前端顯示 UUID 尾碼。

### 4.3 Repository / Service

- **Repository**(`repositories/ai_model_evaluation.py`):
  - 沿用既有 `find_by_usage_log_uid(usage_log_uid)` 取父列。
  - 新增 `list_candidates_with_judge(ai_evaluation_uid)`:`list_candidates` 基礎上 join `models`(`candidate.model_uid = models.model_uid`)取 `model_key` / `name`,一次查回(避免 N+1)。
- **Service**(`services/ai_model_eval_result.py`,新檔或併入既有):
  - `build_evaluation_result(usage_log_uid) -> EvaluationResultRead | None`:取父 → 取候選(含裁判)→ 算彙總(§ 5)→ 組 schema。
  - 純讀、無副作用、不打 OpenRouter。
- **權限**:`AdminDep`,與 usage-logs 明細一致;不做部門過濾(§ 8.1)。

## 5. 彙總邏輯(三評審 → 單一判決)

父表 dim1/2(任務摘要 / 意圖 / 複雜度)在 v2.0.1 已取「首個成功評審值」存為單一值 → **直接顯示**。
子表 dim3/4 為三裁判各自值,本版計算彙總(**在後端 service 算,單一真相源、可測**):

| 彙總欄 | 規則 | 邊界處理 |
| --- | --- | --- |
| `avg_fit_score` | 非 null `ai_fit_score` 平均(Decimal,四捨五入到 3 位) | 全 null → null |
| `min/max_fit_score` | 非 null 值的極值 | 全 null → null |
| `recommend_consensus.model` | 非 null `ai_recommend_model` 取眾數(多數決) | 平票 → 取任一最高票並 `is_split=true`;全 null → model=null |
| `recommend_consensus.votes` | 眾數模型的得票數 | — |
| `recommend_consensus.is_split` | **無嚴格過半即分歧**:`is_split = (top_votes*2 <= succeeded) and succeeded>1`(2:1→false、1:1:1→true、1:1→true) | 只有 1 個成功評審 → 不分歧 |
| `recommend_consensus.tier` | 眾數模型對應的 `ai_recommend_tier`(同模型應一致) | null 安全 |
| `self_vote_count` | `ai_self_vote = true` 的候選數(已於 0024/0025 更正為「裁判 vs 推薦」語意) | null 不計入 |
| `judge_count` / `succeeded_count` | 候選總數 / 其中 AI 欄位非 null(評審成功)數 | 用於「部分成功」標示 |

> **自我偏好警示**:`self_vote_count > 0` 時前端顯示警示標籤(某裁判推薦了自家廠商,可能偏袒)。此為 v2.0 已修正欄位的**第一個實際消費點**,讓偏差監控真正可見。

## 6. 前端「AI 分析」基礎摘要區塊(usage-logs 明細頁內嵌)

落點:`frontend/src/app/(main)/usage-logs/[uid]/page.tsx`,於既有 metadata 區塊**下方**新增一張「AI 分析」`Card`。資料以 `apiClient` 另打 §4 端點(獨立 loading / 狀態,評審缺漏不影響 log 本體顯示)。**本版只做基礎摘要,不放三評審逐筆明細**(逐筆細看 → v2.0.4 專頁)。

### 6.1 基礎摘要卡(判決結果一眼看完)

- **任務分析**:`summary`(文字)+ `intent` / `complexity` 兩個 `Badge`(枚舉→中文,§ 6.2)。
- **平均吻合度**:`avg_fit_score` 以百分比 + 進度條 / 色階呈現(高綠中黃低紅),旁標 min–max 範圍。
- **推薦共識**:推薦模型 + tier `Badge`;`is_split=true` 時加「分歧」灰標 + 票數(如「2/3」)。
- **自我偏好警示**:`self_vote_count > 0` → 橘色警示 `Badge`「N 位裁判推薦自家廠商」;為 0 不顯示或顯示綠色「無自我偏好」。
- **評審完成度**:`succeeded_count < judge_count` 時標「部分成功(2/3)」。
- **四狀態**:未評審(`evaluation === null`)/ 評審中(`pending`)/ 評審失敗(`error`)/ 已評審(`evaluated`,顯示上述摘要)。
- **通往細看(預留)**:v2.0.4 細看專頁上線後,本卡可加「查看完整評審」連結;本版不做。

> **不在本版**:三評審逐筆明細(各裁判推薦 / 理由 / fit / self_vote 並列)→ v2.0.4 專頁。API 已回傳 `candidates`,屆時直接消費,本版不渲染。

### 6.2 前端型別 / 端點 / 中文對照

- `src/lib/api/endpoints.ts` 新增:`aiEvaluationByUsageLog: (uid) => \`/api/v1/ai-eval/evaluations/by-usage-log/${uid}\``。
- `src/types/api.ts` 新增:`EvaluationResult` / `EvaluationSummary` / `EvalCandidate` / `TaskAnalysis`(對齊 §4.2;Decimal 欄位為 `string | null`)。
- **intent / complexity 中文對照**:前端維護一份 label map(如 `CODE_GENERATION → 程式生成`、`medium → 中等`)。enum 來源以後端 `schemas/ai_model_eval.py` 的 `TaskIntent` / `TaskComplexity` 為準;新增枚舉時兩邊同步(§ 8.4)。

## 7. 設定(環境變數)

- 本版**無新增 env**(純唯讀 API + 前端展示)。

## 8. 設計取捨 / 待使用者確認

### 已決議(2026-06-26,user 拍板)

- **顯示位置**:**usage-logs 明細頁內嵌**「AI 分析」區塊(非獨立列表頁)。
- **呈現方式**:**僅基礎摘要卡**(判決結果一眼看完);**不放三評審逐筆明細**(逐筆細看 → v2.0.4 專頁)。usage 詳情頁維持精簡。
- **權限(#1)**:**僅 admin**,對齊現有 usage-logs 明細頁;**未來才開放 User 也看得見**(屆時另開部門隔離,對齊 stats.py)。
- **細看專頁(#2)**:在側欄「AI 分析」下做獨立專頁細看三評審 → **順延 v2.0.4**。
- **API 落點(#3)**:**新開 `ai_eval_results.py`**(讀寫分檔,與 judge-settings 的 `ai_eval.py` 區隔)。
- **intent / complexity 中文對照(#4)**:**前端維護 label map**;日後可改後端供應(或接 `table_catalog` 字典)。
- **分歧判定(#5)**:**無嚴格過半即分歧** → `is_split = (top_votes*2 <= succeeded) and succeeded>1`(2:1→不分歧、1:1:1→分歧、1:1→分歧);顯示仍標票數讓使用者看到未全員一致。
- **無評審回應(#6)**:**`200 + data.evaluation=null`**(非 404)。
- **版號 slot**:v2.0.3 = 評審結果顯示(基礎摘要);細看專頁 v2.0.4、真實重跑 v2.0.5、人類裁決 v2.0.6、儀表板 v2.0.7。
- **彙總算在後端**:單一真相源、可單元測試;前端只渲染。
- **Decimal 字串傳輸**:`fit_score` 等沿用專案既有「Decimal → string」慣例,避免 JS 浮點誤差。
- **API 仍回完整結果**:即使本版前端只渲染摘要,API 仍回 `candidates`,供 v2.0.4 細看專頁直接重用,免重工。

## 9. 變更紀錄

| 日期 | 改動 | 理由 |
| --- | --- | --- |
| 2026-06-26 | 初版(評審結果顯示:明細頁內嵌彙總 + 可展開三評審明細) | 讓 v2.0.1 管線產出可見 |
| 2026-06-26 | **縮範圍**:明細頁只放**基礎摘要卡**,移除可展開三評審明細;三評審逐筆細看改做**獨立「AI 分析」專頁順延 v2.0.4**;後續版號順移(真實重跑→v2.0.5…) | user 決議「用量詳情只看基礎資訊」、細看另立專頁;§8 #1–#6 一併拍板。影響 task-306(縮)、tasks-v2.0.3 阻塞點轉已決議;後端 task 301–305 不變 |
