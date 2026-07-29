---
id: task-525
title: proxy 接線 — 快照改吃 S3 路徑、_rewrite_request 零 diff、串流 + 非串流
status: pending
parallel: true
depends_on: [task-524]
affected_files:
  - backend/app/services/proxy.py
  - backend/tests/services/test_proxy_s3_snapshot.py
estimated_hours: 3
---

## 目標

把 524 的附件落地層接進代理寫入端,讓 `usage_logs.request_content` 只留 S3 路徑。**這是本版唯一改動點**(propose §D.4 定調:改的只是平台後端 log 儲存路徑)。

## 範圍(只做這些)

- 在 `run_chat` 與 `run_chat_stream` **兩條路徑**中呼叫 524 的附件落地層(漏一條 → 串流請求仍寫 base64,遷移完又長回來,見 propose §風險)。
- `_build_request_log` 改吃落地層產出的**快照用值**:
  - 單輪:`images[]` 存路徑;`files[]` 由「只有 `filename`」升級為 `filename` + 路徑(D.3,**推翻 v2.1.2 的「僅記檔名」法務決策** —— commit message 須明寫此推翻)。
  - messages 直傳:`_snapshot_message` 內 `image_url.url` 改存路徑;`file` part 加路徑。
  - 上傳失敗者寫 `upload_failed` 標記(D.5)。
- **`_rewrite_request` 零 diff**:下游 payload 完全不動,照現行送 base64 / 原始 URL 給 OpenRouter / internal(D.4)。**這是本 task 的 review 判準——PR 若動到 `_rewrite_request`,就是走偏了。**
- 上傳失敗**不中斷主流程**:照常呼叫下游、照常回應、照常寫 `usage_logs`(D.5)。
- `S3_STORAGE_ENABLED=false` → 走既有路徑,行為與 v2.2.0 **完全一致**。

## 不做

- **不**動 `_rewrite_request`、**不**動記帳 / 配額 / 速率限制邏輯、**不**動 `_extract_content` 與回應處理。
- **不**動 `request_snapshot.py`(526 的事)。

## 用量紀錄寫入(對齊 `90-project-task-spec.md § 4.5`)

`usage_logs` 寫入時機與欄位**完全不變**,僅 `request_content` 內附件值的形態由 base64 改為 S3 路徑 / `upload_failed` 標記。記帳欄位(token / cost / provider / 狀態)零影響。

## 錯誤處理對照表

| 情境 | 對外行為 | `request_content` | log |
| --- | --- | --- | --- |
| 上傳全成功 | 200,同現行 | 附件為 S3 路徑 | info(可選) |
| 部分附件上傳失敗 | **200,同現行** | 成功者路徑 / 失敗者 `upload_failed` 標記 | warning(含 index / mime / bytes / sha256 / 原因) |
| S3 完全不可用 / 逾時 | **200,同現行** | 全部為 `upload_failed` 標記 | warning ×N |
| `S3_STORAGE_ENABLED=false` | 200,同現行 | base64(v2.2.0 行為) | — |

> **無新增 5xx 情境** —— 附件落地失敗不產生任何對外錯誤(D.5)。

## Acceptance

- [ ] `cd backend && uv run pytest tests/services/test_proxy_s3_snapshot.py` 全綠,且測試涵蓋:
  - [ ] 單輪模式含 data URI 圖 → `request_content["images"]` 為 S3 路徑,**不含** `data:`
  - [ ] messages 模式含 `image_url` data URI → 快照 part 的 `url` 為 S3 路徑
  - [ ] `files` 快照含 `filename` **與**路徑
  - [ ] S3 失敗注入 → **回應仍成功**、下游**仍被呼叫**、`usage_logs` **仍寫入**、附件為 `upload_failed` 標記
  - [ ] `S3_STORAGE_ENABLED=false` → 快照與 v2.2.0 完全一致(含 `files` 只記檔名)
  - [ ] **串流路徑** `run_chat_stream` 與非串流 `run_chat` 行為一致(兩者各一條測試)
- [ ] **下游 payload 零變更(必測)**:以 `respx` 攔截下游請求,斷言送出 body 與開關關閉時**逐欄相同** —— `images` 仍是 base64 / 原始 URL、`file_data` 照舊存在
- [ ] **`_rewrite_request` 零 diff(必驗)**:`git diff -- backend/app/services/proxy.py | grep -A200 "def _rewrite_request"` 中該函式主體**無變更行**;或以 `git diff --function-context` 人工確認並於 PR 描述附上
- [ ] **快照零 base64 回歸**:含 `files` 的請求在成功 / S3 失敗 / 開關開啟三種路徑下,斷言序列化後的 `request_content` 皆 **不含** `file_data` 與 `;base64,`
- [ ] `cd backend && uv run ruff check app/services/proxy.py && uv run mypy app/services/proxy.py` 全綠
- [ ] 既有 proxy 測試全數仍綠:`cd backend && uv run pytest tests/services/test_proxy_messages.py tests/services/test_proxy_strip_nul.py tests/api/test_model_chat_messages.py`

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/03-async-and-tx.md`
- `docs/Design-Base/03-backend/05-exceptions-and-logging.md`
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/03-backend/90-project-backend.md`
- `docs/Design-Base/90-third-party-service/50-openrouter.md`(§ 6 輸入白名單 / § 10 用量紀錄)
- `docs/Design-Base/90-third-party-service/09-object-storage.md`(task-521 建立)
