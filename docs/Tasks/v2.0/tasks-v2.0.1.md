# Tasks v2.0.1 · 判別管線(taskiq + Redis + 三評審打分)

> 狀態:未開始(已完成 0/7)
> 來源:[propose-v2.0.1.md](./propose-v2.0.1.md);母本地基 [v2.0.0](./propose-v2.0.0.md)(三張 `ai_` 表已建)
> 並行:4 / 序列:3 / 預估總時數:20 hr

| # | 標題 | 狀態 | 並行 | 依賴 | 影響檔案 |
| --- | --- | --- | --- | --- | --- |
| 101 | taskiq + Redis broker 基建 + 設定(env/config) | pending | ✓ | — | `backend/pyproject.toml`、`backend/app/tasks/broker.py`、`backend/app/core/config.py`、`.env.example` 等 |
| 102 | `usage_logs.ai_evaluated_at` 旗標欄(migration 0020 + model) | pending | ✓ | — | `backend/alembic/versions/0020_usage_logs_ai_evaluated_at.py`、`backend/app/models/usage_log.py` |
| 103 | 判別 prompt builder + 結構化輸出 schema(dim1–4) | pending | ✓ | — | `backend/app/services/ai_model_eval_prompt.py`、`backend/app/schemas/ai_model_eval.py` |
| 104 | 評審結果 repository(父表 + 三子表寫入 + 標旗標) | pending | ✓ | — | `backend/app/repositories/ai_model_evaluation.py` |
| 105 | 三評審執行 + 回寫 service | pending | ✗ | 103, 104 | `backend/app/services/ai_model_eval.py` |
| 106 | taskiq task + dispatcher/scheduler 接線 | pending | ✗ | 101, 102, 105 | `backend/app/tasks/ai_model_eval.py`、`backend/app/tasks/scheduler.py` |
| 107 | docker-compose 常駐服務(worker / scheduler / redis) | pending | ✗ | 101, 106 | `docker-compose.dev.yml`、`docker-compose-prod.yml` |

## 並行批次

- **批次 1(可同時認領)**:101、102、103、104(`affected_files` 互不重疊)
- **批次 2**:105(待 103 + 104)
- **批次 3**:106(待 101 + 102 + 105)
- **批次 4**:107(待 101 + 106)

## 阻塞點 / 待使用者確認(來自 propose §8,拆解前未決)

> 下列為 propose 明列的「待使用者確認」,worker 開工前 user 須拍板,否則 task-103 / 105 的輸出格式可能返工:

1. **PII 遮罩**:評審把 input+output 外送 3 個判別 provider,`request_content.text` 是否先做遮罩?(影響 103/105)
2. **輸出格式**(§6 草案):是否採用?dim2 意圖標籤是否固定枚舉?父表 summary/intent 三評審不一致取誰?是否存 raw JSON 供稽核?(影響 103/104/105)
3. **派發範圍**:本版全量評審(逐筆 `ai_evaluated_at IS NULL` 都跑 3 評審),抽樣留 v2.1,可接受?(影響 106)

## 拆解註記(orchestrator)— 已決議(2026-06-25)

- **版號**:user 決議**沿用 `v2.0.1`**(不改記 v2.1.0)。
- **migration 編號**:user 決議**採用 `0020`**(`0019` 已被 v2.0.0 foundation 佔用),見 task-102。
