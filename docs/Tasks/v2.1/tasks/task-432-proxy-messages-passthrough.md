---
id: task-432
title: 後端:proxy service messages 透傳 + 生成參數注入(_rewrite_request + run_chat/run_chat_stream 簽章 + _build_request_log 快照)+ 單元測試
status: done
parallel: true
depends_on: [task-431]
affected_files:
  - backend/app/services/proxy.py
  - backend/tests/services/test_proxy_messages.py
estimated_hours: 3
---

## 目標

`backend/app/services/proxy.py` 打通 messages 模式與生成參數:`_rewrite_request`(現 L94-128)新增 messages 分支透傳進 payload、`temperature` / `max_tokens` / `response_format` 有帶才注入(兩模式共用);`run_chat`(L377-446)/ `run_chat_stream`(L851-917)簽章新增 `messages` 與三生成參數(沿 v1.6.1 tools / v1.8 files 逐欄位擴充模式);`_build_request_log`(L131-151)支援 messages 快照 + 生成參數記錄。單輪舊路徑組裝邏輯**不動**。

## 實作要點(對齊 propose §B.2 / §B.3 / §D.4 / §D.7)

- `_rewrite_request`:有 `messages` → `payload = {"model": model, "messages": [m.model_dump(exclude_none=True) for m in messages]}`;`tools` 附掛邏輯共用;無 `messages` → 走現況單輪組裝。docstring 同步改寫(引用 430 修訂後的 `50-openrouter.md` 雙模式)。
- **生成參數注入**(兩模式共用):`temperature` / `max_tokens` / `response_format` 非 None 才 `payload[key] = value`(`response_format` 以 `model_dump(exclude_none=True)` 展開);None 一律不出現在 payload(帶 `temperature=None` 的 payload 必須與完全不帶位元級一致)。
- **禁** dict 原樣透傳未知欄位:messages 與 response_format 內容以 431 的 schema 驗證結果為源(型別化物件 dump),防呼叫端夾帶未開放參數(top_p / stop 等)。
- `run_chat` / `run_chat_stream` / `_run_chat_openrouter` / `_run_chat_internal` 傳遞 messages 與三生成參數;internal provider payload 結構相同,自然支援;白名單 / key failover / 串流 `stream`+`stream_options` 注入邏輯**不動**。
- client 層(`clients/openrouter/client.py`、`clients/internal/client.py`)為 pass-through,**不在本 task 範圍**(不列 affected_files、不得改動)。

## usage_logs 寫入說明(`90-project-task-spec.md §4.5`)

- messages 模式:`_build_request_log` 產 `{"model": model, "messages": <原樣快照>}`;file part 仿現況**僅記 `filename` 不記 `file_data`**;image_url part 原樣保留(與現況 `images` 存 base64 一致,對齊 §D.4 定案)。
- **生成參數入快照**(兩模式皆同):有帶的 `temperature` / `max_tokens` / `response_format` 記入 `request_content`;未帶不出現(不記 None)。
- `tools` 頂層附掛與 `used_tools` 推導邏輯不變;單輪模式 request_log 既有結構不變(僅可能多生成參數鍵)。
- 寫入鏈(`schedule_usage_log`)不動。

## 錯誤處理對照表

| 情境 | 行為 | 說明 |
| --- | --- | --- |
| 超長對話(超過模型 context window) | OpenRouter 回錯 → 沿既有錯誤鏈轉失敗回應 | 不新增攔截;不設應用層上限 |
| OpenRouter 4xx/5xx / key failover | 現況邏輯不變 | messages 模式共用同一條錯誤鏈 |
| videos 非空 | 400(現況) | 不受本 task 影響 |

## Acceptance

- [ ] `uv run pytest backend/tests/services/test_proxy_messages.py` 全綠;案例至少涵蓋:messages 分支 payload 形狀(role/content 原樣、tools 附掛)/ 單輪路徑(無生成參數)payload 與 v2.1.1 位元級一致(回歸)/ 生成參數注入(三欄有帶才出現;None 不出現;response_format 兩種 type 展開正確;單輪與 messages 模式皆注入)/ `_build_request_log` messages 快照(file 僅 filename、image_url 原樣)+ 生成參數入快照 / internal provider payload 相同
- [ ] `uv run pytest backend/tests` 全綠(既有測試不退步)
- [ ] `uv run mypy backend/app/services/proxy.py` 與 `uv run ruff check backend/app/services/proxy.py` 零錯誤零 warning
- [ ] `git diff backend/app/clients/` 為空(client 層零改動)

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`(風格地板)
- `docs/Design-Base/03-backend/05-exceptions-and-logging.md`(錯誤鏈 / 機密過濾)
- `docs/Design-Base/03-backend/06-clients.md` + `90-third-party-service/01-client-design.md`(串第三方)
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/90-third-party-service/50-openrouter.md`(430 修訂後版本;§ 錯誤對應 / § 用量紀錄)
- `docs/Tasks/v2.1/propose-v2.1.2.md` §B.2/§B.3/§D.4
