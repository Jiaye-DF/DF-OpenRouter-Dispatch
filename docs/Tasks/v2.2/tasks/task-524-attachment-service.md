---
id: task-524
title: 附件落地層 attachment.py(deterministic key / best-effort / 失敗標記)
status: pending
parallel: true
depends_on: [task-523]
affected_files:
  - backend/app/services/attachment.py
  - backend/tests/services/test_attachment.py
estimated_hours: 3
---

## 目標

新增附件落地層,把「請求中的 base64 附件 → S3 物件路徑」這件事收斂成一個純粹、可獨立測試的模組,不把 S3 細節灌進 `proxy.py`(propose §B.2)。本模組是 525(寫入端接線)與 530/531(遷移)共用 key 生成規則的**單一真相來源**。

## 範圍(只做這些)

### 1. data URI 解析

- 解析 `^data:([^;]+);base64,(.*)$` → `(mime, bytes)`;推導副檔名。
- **畸形值**(解不開 / base64 解碼失敗 / 空內容)→ 視同上傳失敗走 best-effort 路徑(記標記 + log),**禁**拋例外中斷主流程。
- 輸入已是 `http(s)://` 遠端 URL → **原樣保留、不代抓**(D.2,避免 SSRF 面)。

### 2. Deterministic key 生成(**本版關鍵設計**)

- 新請求:`<S3_KEY_PREFIX>/chat/<YYYY>/<MM>/<DD>/<request_uid>/<idx>-<sha256(bytes)[:16]>.<ext>`
- 歷史遷移:`<S3_KEY_PREFIX>/legacy/<usage_log_uid>/<idx>-<sha256(bytes)[:16]>.<ext>`
- **必須是純函式**:相同輸入 → 相同 key。530(上傳)與 531(改寫)靠重算取得同一把 key,因此**不需要 mapping 表 / 暫存欄位 / migration**(D.6)。此函式**必須**匯出供 530 / 531 直接引用,**禁**各自複製一份實作。
- 日期取 Asia/Taipei(對齊 [`00-overview/05-timezone.md`](../../../Design-Base/00-overview/05-timezone.md))。

### 3. best-effort 上傳語意(D.5)

- 逐附件獨立處理:成功 → 回傳 key;失敗 → 回傳失敗標記,**繼續處理下一個**,絕不中斷。
- 失敗標記形狀:`{"type": "image_url", "upload_failed": True, "mime": "...", "bytes": N, "sha256": "..."}`(檔案則 `{"type": "file", "file": {"filename": ..., "upload_failed": True, ...}}`)。
- 失敗落**結構化 log**(含附件 index / mime / bytes / sha256 / 錯誤原因),供 Seq 查詢與告警;**禁**把 base64 內容或 AWS 憑證寫進 log。
- **硬規則**:本模組回傳的快照值**永遠不含 base64**;`file_data` 的 base64 任何情況下不得出現在輸出中。

### 4. 開關短路

- `S3_STORAGE_ENABLED=false` → 本模組直接回「原樣不動」的結果,**不呼叫 S3**(525 據此維持 v2.2.0 行為)。

### 5. 兩種內容模式的走訪

- 單輪:`images: list[str]` + `files: list[dict]`。
- messages 直傳:走訪 `messages[].content[]` 的 `image_url` part 與 `file` part。
- 兩者共用同一組解析 / key / 上傳邏輯,**禁**寫成兩份。

## 不做

- **不**動 `proxy.py`(525 的事)、**不**動 `request_snapshot.py`(526 的事)。
- **不**產生下游 payload 用的值 —— 下游吃的是**原始輸入**,本模組**只**輸出快照用值(D.4)。

## Acceptance

- [ ] `cd backend && uv run pytest tests/services/test_attachment.py` 全綠,且測試涵蓋:
  - [ ] data URI 解析成功 / 畸形值(非 base64、空內容、無 mime)三種
  - [ ] key 為 deterministic:同一 bytes 呼叫兩次得到**完全相同**的 key
  - [ ] 遠端 `http(s)://` 輸入原樣保留、**未呼叫** S3(以 mock 斷言 `put_object` 未被呼叫)
  - [ ] S3 失敗(注入 `S3UploadError`)→ 回失敗標記、**不拋例外**、有 log
  - [ ] 部分成功部分失敗:三張圖第二張失敗 → 輸出為 `[key, upload_failed標記, key]`,順序與索引正確
  - [ ] `S3_STORAGE_ENABLED=false` → 完全不呼叫 S3,輸出等同輸入
  - [ ] 單輪與 messages 兩模式皆走同一路徑並產出等價結果
- [ ] **快照零 base64 回歸**:對含 `files`(帶 `file_data`)的輸入,斷言輸出 JSON 序列化後 `"base64" not in dumped and "file_data" not in dumped`
- [ ] `cd backend && uv run ruff check app/services/attachment.py && uv run mypy app/services/attachment.py` 全綠
- [ ] key 生成函式為公開匯出(`grep -q "^def build_object_key\|^def object_key" backend/app/services/attachment.py`,名稱自訂但須可被 530 / 531 import)

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/03-async-and-tx.md`
- `docs/Design-Base/03-backend/05-exceptions-and-logging.md`
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/90-third-party-service/09-object-storage.md`(task-521 建立)
- `docs/Design-Base/00-overview/05-timezone.md`
- `docs/Design-Base/04-databases/03-passwords-and-pii.md`(附件屬使用者內容,log 過濾底線)
