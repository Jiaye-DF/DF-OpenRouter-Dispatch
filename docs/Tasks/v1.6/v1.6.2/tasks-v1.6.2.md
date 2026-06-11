# Tasks v1.6.2

## 版本資訊

- 前置依賴:v1.6.1(Chat 代理透傳 tools)
- 本版本範圍:用量紀錄加 `used_tools` 標記與篩選;單筆 Input/Output 詳情頁(base64 圖片前端轉檔)
- 對齊的 Design-Base 章節:
  - [50-openrouter.md](../../../Design-Base/50-openrouter.md)(§6 請求改寫 / Response 記帳)
- 母本 propose:[`propose-v1.6.2.md`](./propose-v1.6.2.md)(包含設計推導與決議過程)

> 本 Tasks 為**實作契約**;設計理由與替代方案請參考母本 propose。內容若與 propose 衝突,以本檔為準。

## Definition of Done

### 後端

#### DB / Migration

- [x] `alembic/versions/0011_usage_log_used_tools.py`(head 為 0010,本支 revises 0010):
  - `usage_logs` 加 `used_tools BOOLEAN NOT NULL DEFAULT FALSE`(server_default false → 舊紀錄自動回填)
  - partial index `idx_usage_logs_used_tools_time ON usage_logs (created_at DESC) WHERE used_tools = TRUE AND is_deleted = FALSE`
  - downgrade 對稱 drop index + drop column
- [x] `app/models/usage_log.py`:加 `used_tools` Mapped 欄(server_default "false")

#### 寫入

- [x] `app/services/proxy.py`:
  - `schedule_usage_log` 由 `request_log.tools` 推導 `used_tools = bool(...)` 寫入(只改一處)
  - `_summarize_response` 改存完整 `output_text`(沿用 `_extract_content`),取代原截斷 500 字的 `first_text`

#### Schema / 端點

- [x] `app/schemas/usage_log.py`:
  - `UsageLogListItem`(列表;加 `used_tools`;**不含** request_content/response_summary)
  - `UsageLogDetail`(繼承 ListItem;補回 request_content/response_summary)
  - 移除舊 `UsageLogResponse`(無其他引用)
- [x] `app/api/v1/usage_logs.py`:列表用 `UsageLogListItem` + 加 `used_tools` query;詳情用 `UsageLogDetail`
- [x] `app/repositories/usage_log.py`:`_apply_filters` / `list` 加 `used_tools` 參數

### 前端

- [x] `src/types/api.ts`:`UsageLog` 加 `used_tools` / `openrouter_generation_id`;新增 `UsageLogDetail` / `UsageRequestContent` / `UsageResponseSummary`
- [x] `src/app/(main)/usage-logs/page.tsx`:
  - 加「工具」欄(Badge「工具」/「—」)
  - 加「是否用工具」篩選 chip(全部 / 有用工具 / 未用工具 → query `used_tools`)
  - 每列可點 → `router.push('/usage-logs/{uid}')`,hover cursor
- [x] `src/app/(main)/usage-logs/[uid]/page.tsx`(新):
  - 打 `usageLogById` 取單筆;Metadata 區 + Input 區 + Output 區
  - Input:text / tools(JSON 美化)/ images;base64 圖 → `URL.createObjectURL` blob 顯示 + 開新分頁/下載,卸載 `revokeObjectURL`;一般 URL 直接顯示
  - Output:`output_text` ?? `first_text`(舊紀錄標註「僅前 500 字」)
  - 返回用量紀錄按鈕

### 文件

- [x] `src/app/(main)/admin-guide/page.tsx`:「管理頁速查」用量紀錄列補述工具篩選與詳情頁
- [x] `docs/Design-Base/50-openrouter.md`:§6 Response 記帳補 `output_text` / `used_tools`
- [x] `docs/Tasks/v1.6.2/propose-v1.6.2.md` + `tasks-v1.6.2.md`(本檔)
- [N/A] INTEGRATION.md / user-guide 頁:SDK 對外呼叫行為未變,不需更新

### 驗證

- [x] `python -m py_compile`(model / proxy / schema / api / repository / migration)通過
- [x] `npm run type-check` 通過
- [ ] `alembic upgrade head` 套用 0011(待開發環境執行確認)
- [ ] 手動驗證(待使用者執行):
  - 發一筆帶 `tools` 的呼叫 → 列表「工具」欄顯示、「有用工具」篩選可篩出
  - 點入詳情頁:Input 顯示 text/tools/圖片(base64 可預覽+下載)、Output 顯示完整回覆
  - 舊紀錄詳情:Output 標註「僅前 500 字」
  - 列表 payload 不再含 base64(改 ListItem schema)

## 備註

- per-caller 速率限制 / 預算配額仍為 Out of Scope(現有限流僅 per-Provider-Key,設定於各 Key 的 `rpm_limit` / `min_request_interval_ms`,且僅單 worker 進程內生效)。
