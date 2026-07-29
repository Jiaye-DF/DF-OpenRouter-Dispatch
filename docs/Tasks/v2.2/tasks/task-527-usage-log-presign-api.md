---
id: task-527
title: 用量明細 API 回吐 presigned URL
status: pending
parallel: true
depends_on: [task-523, task-526]
affected_files:
  - backend/app/api/v1/usage_logs.py
  - backend/app/schemas/usage_log.py
  - backend/tests/api/test_usage_logs_presign.py
estimated_hours: 3
---

## 目標

`GET /api/v1/usage-logs/{uid}` 回吐 `request_content` 時,把其中的 S3 物件路徑換成**短期 presigned URL**,讓前端可直接顯示(D.9:回吐時直接換,不另開 302 導轉端點)。

## 範圍(只做這些)

- 於 `get_usage_log`(單筆詳情)回應組裝時,走訪 `request_content` 內附件值:
  - **S3 路徑** → 以 `S3Client.presign_get(key, ttl=S3_PRESIGN_TTL_SECONDS)` 換成 URL。
  - **舊 data URI** → **原樣回吐**(遷移期新舊並存;前端既有渲染路徑保底)。
  - **遠端 http(s) URL** → 原樣回吐。
  - **`upload_failed` 標記** → 原樣回吐(前端據此顯示「內容未留存」)。
- 列表端點 `list_usage_logs` **不動** —— `UsageLogListItem` 刻意不含 `request_content`(見 `schemas/usage_log.py:10` 註解),不要為了本版把它加回去。
- presign 失敗(S3 不可用)→ **best-effort**:該附件退回原樣值(路徑字串)+ log warning,**不**讓整支 API 回 5xx。理由與 D.5 一致 —— 記帳輔助層不該擋掉讀取。
- `S3_STORAGE_ENABLED=false` → 不做任何 presign,行為與 v2.2.0 一致。

## Response Schema(對齊 `90-project-task-spec.md § 4.1`)

- `UsageLogDetail` 為既有 Pydantic model,`request_content: dict[str, Any] | None` **型別不變**(值語意變 —— 本版屬**管理端可見的資料層變更**,已列入 propose 對外承諾)。
- **禁**改成 `dict` 當 response type;**禁**在回應中暴露 `pid`、bucket 名稱、AWS 憑證或完整 S3 key 之外的內部資訊。

## 敏感欄位過濾表

| 欄位 | 是否可回吐 | 說明 |
| --- | --- | --- |
| presigned URL | ✅ | 短期(預設 15 分鐘)、bucket private;URL 內含簽章但不含長期憑證 |
| S3 物件 key | ⚠️ presign 失敗時才會外露 | 僅路徑字串,無存取能力 |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | ❌ | **禁**出現於 Response / Log |
| bucket 名稱 | ⚠️ | presigned URL 的 host 天然含 bucket;不另行單獨回吐 |
| `file_data` base64 | ❌ | 本版起 DB 內根本不存在 |

## 錯誤處理對照表

| 情境 | HTTP | 行為 |
| --- | --- | --- |
| 正常 | 200 | 附件為 presigned URL |
| presign 失敗 / S3 不可用 | **200** | 該附件退回原樣值 + log warning(不擋讀取) |
| 紀錄不存在 | 404 | 沿用既有行為 |
| 無權限(跨部門) | 沿用既有 `_scope_filters` 行為 | 不因本版改變 |

## 不做

- **不**開新端點(D.9 已定「回吐時直接換」)。
- **不**動列表端點、**不**動權限 / scope 過濾邏輯。
- **不**在 `request_snapshot.py` 內做 presign(該層須維持純函式)。

## Acceptance

- [ ] `cd backend && uv run pytest tests/api/test_usage_logs_presign.py` 全綠,且測試涵蓋:
  - [ ] 紀錄含 S3 路徑 → 回應該附件值為 `https://` 開頭且含簽章 query(`X-Amz-Signature` 或等價)
  - [ ] 紀錄含舊 data URI → **原樣回吐**,未被改動
  - [ ] 紀錄含 `upload_failed` 標記 → 原樣回吐
  - [ ] presign 拋錯注入 → **回應仍 200**,該附件為原樣值,有 log warning
  - [ ] `S3_STORAGE_ENABLED=false` → 完全不呼叫 presign
  - [ ] messages 模式與單輪模式**兩種形狀**皆正確處理
- [ ] 列表端點未受影響:`cd backend && uv run pytest tests/api/ -k usage_log` 全綠
- [ ] response 殼為 ApiResponse(`{ success, code, data, detail }`,對齊 `03-backend/01-routing.md`)
- [ ] `cd backend && uv run ruff check app/api/v1/usage_logs.py app/schemas/usage_log.py && uv run mypy app/api/v1/usage_logs.py app/schemas/usage_log.py` 全綠
- [ ] Swagger 於 `/api/docs` 可查閱該端點且 schema 無破壞

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/01-routing.md`
- `docs/Design-Base/03-backend/02-auth.md`
- `docs/Design-Base/03-backend/05-exceptions-and-logging.md`
- `docs/Design-Base/03-backend/90-project-backend.md`
- `docs/Design-Base/03-backend/92-project-permission.md`
- `docs/Design-Base/90-third-party-service/09-object-storage.md`(task-521 建立)
- `docs/Design-Base/04-databases/90-project-database.md`(pid / uid 對外規則)
