[//]: # (此檔為 v2.0.1 任務提案,實作前先由使用者確認範圍與設計取捨。)

# Propose v2.0.1 · 模型適配評審【判別管線:taskiq + Redis + 三評審打分】

> 此為 **proposal**(規劃草案),確認後即轉為正式 `tasks-v2.0.1.md`。
>
> 對應母本:[v2.0.0 地基(資料表 + 判別模型設定)](./propose-v2.0.0.md)。
> 沿用 v1.9.1「內部 LLM 呼叫走 `DEFAULT_OPENROUTER_KEY`、不經 SDK proxy、不寫 usage_logs」模式。

## 1. 目標(本版)

讓 v2.0.0 設定好的 **3 個判別模型**,實際對 `usage_logs` 的 input + output 跑評審打分,結果回寫 DB:

1. **導入 taskiq + Redis**:asyncio 原生任務佇列,作為本功能與後續背景任務的排程基建。
2. **判別 prompt 設計**:依設定的 3 個判別模型,各自對同一筆 I/O 輸出結構化判別(§ 5 四方向)。
3. **回寫 DB**:評審結果寫入 `ai_model_evaluations` / `ai_model_eval_candidates`(v2.0.0 已建表)。

> **本版仍不做**:不重跑推薦模型(真成本留 v2.0.2)、無人類裁決(v2.0.3)、無成本 delta / 儀表板(v2.0.4)。

## 2. 範圍(本版)

### In Scope

- **taskiq + Redis 基建**(§ 4):TaskiqScheduler 派發 + taskiq worker 執行,Redis 為 broker + result backend。
- **`usage_logs` 旗標欄**(§ 4):新增 `ai_evaluated_at`(NULL=未評審),作派發游標。
- **判別 prompt + 三評審執行**(§ 5):對設定的 3 個判別模型各內部呼叫一次(`DEFAULT_OPENROUTER_KEY`,**不寫 usage_logs**),輸出 dim1–4。
- **輸出格式 + 回寫**(§ 6):結構化 JSON → 寫父表 dim1/2 + 三子表候選(dim3/4)。
- **設定**(§ 7):taskiq/Redis 連線、派發間隔等 env。

### Out of Scope

- **真實重跑推薦模型 / 真成本** → v2.0.2。
- **人類裁決 / 複審佇列** → v2.0.3。
- **成本 delta / 部門彙總 / 儀表板** → v2.0.4。
- **抽樣 / 去重 / 學習窗口快取 / broker 換 RabbitMQ** → v2.1。

## 3. 資料流

```
usage_logs(既有,唯讀來源)
   │  TaskiqScheduler 定期掃未評審筆(ai_evaluated_at IS NULL)→ Redis broker → taskiq worker
   ▼
讀 ai_eval_judge_settings(3 個判別模型)
   │  對同一份 request_content(input)+ response_summary(原 output)
   │  → 3 個判別模型各內部呼叫一次(DEFAULT_OPENROUTER_KEY)
   ▼
ai_model_evaluations(父:dim1 摘要 / dim2 意圖+複雜度)
ai_model_eval_candidates(子 ×3:dim3 fit_score / dim4 推薦模型+理由)
   │  寫畢 → usage_logs.ai_evaluated_at = now()
   ▼
(v2.0.2+)重跑真成本 → 人類裁決 → 成本彙總
```

## 4. 排程基建(taskiq + Redis,broker 未來換 RabbitMQ)

> taskiq 為 **asyncio 原生** 任務佇列,貼合既有 async FastAPI 後端(評審的 OpenRouter 呼叫可直接 `await`,免 sync 包裝),與未來其他背景任務共用基建。

- 落點:`tasks/ai_model_eval.py`(taskiq task)+ TaskiqScheduler 排程設定。
- 機制:
  - **TaskiqScheduler**(`taskiq scheduler`)定期(`AI_EVAL_BEAT_INTERVAL_SECONDS`)觸發 dispatcher,掃 `usage_logs` 未評審筆,逐筆 `.kiq(usage_log_uid)` 派任務進 **Redis broker**(`ListQueueBroker`)。
  - **taskiq worker**(`taskiq worker`)消費任務:讀設定 → 跑 3 評審 → 寫結果 → 標 `ai_evaluated_at`。
  - **broker**:本版 **Redis**;未來換 RabbitMQ(`taskiq-aio-pika`,task 不動);**result backend / cache 續用 Redis**(`RedisAsyncResultBackend`)。
- **`usage_logs` 加旗標欄 `ai_evaluated_at`**(migration `0019`):NULL=未評審;dispatcher 以此撈待派,派發時上「派發中」標記防重複派發。
- **冪等**:task 以 `usage_log_uid` 為鍵,`ai_model_evaluations.usage_log_uid` **UNIQUE**;重複投遞 / 重試不產生重複評審。
- **延遲語意**:「可接受延遲」**僅指結果晚點出現可接受**,**不等於排程可間歇**。scheduler 與 worker 必須 **24/7 常駐**。
- **持續運行保證**:
  - **常駐服務**:docker-compose 新增 `taskiq-worker`、`taskiq-scheduler`(`restart: unless-stopped`),`redis` 開 AOF 持久化。
  - **重試**:task 失敗走 taskiq 重試(`retry_on_error` + backoff);超限標 `status='error'`,不卡整批。
  - **停機補件**:離線期間累積的未評審 log 仍在,恢復後自動補派;**真相源在 Postgres,broker 僅作傳輸,訊息遺失可由 DB 重建**。
- **Redis 一機多用**:本版 broker + result backend;未來熱快取 / proxy 共享限流共用同座 Redis。

## 5. 判別 prompt 設計(四方向)

每個判別模型看「該筆 `request_content`(input)+ `response_summary`(原模型 output)+ 系統候選模型清單」,獨立輸出。

| # | 方向 | 角色 | 落點 |
| --- | --- | --- | --- |
| 1 | 使用者輸入摘要 | 鋪墊(讀懂任務) | `ai_task_summary`(父,不計分) |
| 2 | 任務意圖 | 鋪墊 | `ai_task_intent` + `ai_task_complexity`(父,不計分) |
| 3 | 輸出是否吻合任務意圖 | **錨點**(唯一可觀察) | `ai_fit_score`(子,0–1) |
| 4 | 更適合的模型 | **推薦**(先驗) | `ai_recommend_model` + `ai_recommend_tier` + `ai_recommend_reason`(子) |

**約束**:
- **盲化**:prompt 不揭露「原 output 出自哪個模型」,降自我偏好偏差;`ai_self_vote` 事後判定(比對「該判別模型自己 vs 其推薦模型」是否同廠商,非「原模型 vs 推薦」)。
- **候選限白名單**:dim4 推薦只能從 `models` active 清單選(prompt 餵入 model_key + tier),`ai_recommend_tier` 由所選 model 反查,保證一致。
- **內部呼叫**:`chat_completion(payload, api_key=DEFAULT_OPENROUTER_KEY)`,要求 JSON 結構化輸出;某評審失敗該筆標記、不阻斷其他評審,三方全失敗 → 父 `status='error'`。

## 6. 輸出格式(待討論)

各判別模型回傳結構化 JSON,**草案如下,格式可調**:

```jsonc
{
  "task_summary":   "使用者想做 X(dim1)",
  "task_intent":    "code_generation",          // dim2 意圖標籤(枚舉待定)
  "task_complexity":"medium",                   // low | medium | high
  "output_fit": {                               // dim3
    "score":  0.86,                             // 0–1,原 output 對意圖的吻合度
    "reason": "原回覆涵蓋…但缺…"
  },
  "recommend": {                                // dim4
    "model":  "anthropic/claude-opus-4.8",      // 限白名單
    "reason": "此任務為多步推理,建議用…"
  }
}
```

- 寫回:`task_summary` / `task_intent` / `task_complexity` → 父表(三評審取一致或首個;**待討論**是否各存);`output_fit.score` / `recommend.*` → 各自子表候選。
- **待討論點**:(a) dim2 意圖標籤要不要固定枚舉(便於日後彙總)?(b) 父表的 summary/intent 三評審不一致時取誰?(c) JSON 是否要附 raw 全文存檔供稽核?

## 7. 設定(環境變數)

| 變數 | 預設 | 說明 |
| --- | --- | --- |
| `AI_EVAL_ENABLED` | `false` | 評審排程總開關 |
| `TASKIQ_BROKER_URL` | `redis://redis:6379/0` | taskiq broker(未來換 RabbitMQ `amqp://...`) |
| `TASKIQ_RESULT_BACKEND_URL` | `redis://redis:6379/1` | taskiq result backend |
| `REDIS_URL` | `redis://redis:6379/2` | 應用快取 / 未來共享限流用 |
| `AI_EVAL_BEAT_INTERVAL_SECONDS` | `300` | 派發掃描間隔(結果可接受延遲) |
| `AI_EVAL_DISPATCH_BATCH_SIZE` | `100` | 每次掃描派發上限 |
| `AI_EVAL_TASK_MAX_RETRIES` | `3` | 單筆評審 task 重試上限 |
| `DEFAULT_OPENROUTER_KEY` | (既有) | 三評審內部呼叫金鑰 |

## 8. 設計取捨 / 待使用者確認

### 已決議(2026-06-25)

- **排程技術**:**taskiq + Redis**(broker 未來換 RabbitMQ),見 [[taskiq-redis-harness-direction]]。
- **評審語意**:dim B(模型適配)為主、dim3 吻合度為錨點;成本與重跑留後續版本。
- **判別模型**:讀 v2.0.0 設定的 3 個;內部呼叫走 `DEFAULT_OPENROUTER_KEY`、不寫 usage_logs。

### 待使用者確認

1. **資料治理**:評審把 input + output 外送 3 個判別模型 provider。是否需先對 `request_content.text` 做 **PII 遮罩**?
2. **輸出格式**:§ 6 草案是否採用?dim2 意圖標籤是否固定枚舉?父表 summary/intent 多評審不一致時取誰?是否存 raw JSON 供稽核?
3. **派發範圍**:本版全量評審(逐筆未評審 log 都跑 3 評審)。先全量、抽樣留 v2.1,可接受嗎?
