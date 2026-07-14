---
id: task-431
title: 後端:ChatMessage/ChatContentPart schema + ChatRequest.messages + 生成參數三欄 + 互斥/白名單驗證 + 單元測試
status: done
parallel: true
depends_on: [task-430]
affected_files:
  - backend/app/schemas/model.py
  - backend/tests/schemas/test_chat_request_messages.py
estimated_hours: 3
---

## 目標

`ChatRequest`(`backend/app/schemas/model.py` 現 L21-40)新增 optional `messages` 欄位與配套 `ChatMessage` / `ChatContentPart` schema、新增 `temperature` / `max_tokens` / `response_format` 三個生成參數欄位,實作互斥/白名單/值域驗證;舊欄位(text/images/files/videos/tools)定義不動。

## 實作要點(對齊 propose §B.1 / §D.1 / §D.2 / §D.7)

- `ChatMessage`:`role: Literal["system", "user", "assistant"]`;`content: str | list[ChatContentPart]`。
- `ChatContentPart`:discriminated union,`type` 只收 `text` / `image_url` / `file`;`file` part 形狀對齊既有 `ChatFile`(filename + file_data)。未知 `type` → 驗證失敗。
- `ChatRequest.messages: list[ChatMessage] | None = None`;model validator:
  - `messages` 與 `text` / `images` / `files` 任一同時非空 → 驗證錯誤(對外 400)。
  - `messages == []`(空陣列)→ 驗證錯誤。
  - **不設筆數上限**(user 拍板;模型 context window 為自然上限)。
- **生成參數三欄**(§D.7):
  - `temperature: float | None = None`(`ge=0, le=2`)。
  - `max_tokens: int | None = None`(`ge=1`;不設應用層上限)。
  - `response_format: ResponseFormat | None = None`:新增 `ResponseFormat` schema,`type: Literal["json_object", "json_schema"]`;`type="json_schema"` 時必帶 `json_schema: dict`(validator 檢查),`json_object` 時不得帶。
  - 三欄與 messages / 單輪模式**正交**(兩模式皆可帶),不參與互斥驗證。
- Pydantic BaseModel 明確定義,**禁** `dict` 型別(`90-project-task-spec.md §4.1`;`response_format` 必為型別化 schema,禁 raw dict 欄位)。

## 錯誤處理對照表

| 情境 | HTTP | 說明 |
| --- | --- | --- |
| `messages` 與 `text`/`images`/`files` 同時帶 | 400 | model validator;錯誤訊息明示互斥 |
| `messages: []` | 400 | 空陣列無語意 |
| role 非 `system/user/assistant` | 400 | Literal 白名單 |
| content part `type` 非 `text/image_url/file` | 400 | union 驗證失敗 |
| `temperature` < 0 或 > 2 | 400 | 值域驗證 |
| `max_tokens` < 1 或非整數 | 400 | 值域驗證 |
| `response_format.type` 非 `json_object/json_schema`;或 `json_schema` 型別缺 `json_schema` 物件 | 400 | 型別化白名單 |
| 只帶 `text`/`images`/`files`(舊模式,無生成參數) | 不變 | 行為與 v2.1.1 完全一致 |

> 驗證錯誤統一走既有 422→400 包裝慣例(對齊 `03-backend/90-project-backend.md §2` 現行 ChatRequest 處理方式,以現況為準)。

## Acceptance

- [ ] `uv run pytest backend/tests/schemas/test_chat_request_messages.py` 全綠;案例至少涵蓋:合法多輪(system+user+assistant)/ str 與 parts 兩種 content / 互斥(messages+text、messages+images、messages+files)/ 空陣列 / 非法 role / 非法 part type / 舊模式(只帶 text)不受影響 / 生成參數合法值(邊界 0、2、1)/ temperature 越界 / max_tokens 0 / response_format 非法 type 與 json_schema 缺物件 / 生成參數搭配單輪與 messages 兩模式皆合法
- [ ] `uv run mypy backend/app/schemas/model.py` 與 `uv run ruff check backend/app/schemas/model.py` 零錯誤零 warning
- [ ] `ChatRequest` 舊欄位定義 diff 為零(`git diff` 僅新增,無修改既有欄位)

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`(風格地板)
- `docs/Design-Base/03-backend/01-routing.md`(Pydantic schema 規範)
- `docs/Design-Base/03-backend/90-project-backend.md`(統一 Response / 錯誤訊息)
- `docs/Design-Base/03-backend/07-testing.md`(測試慣例)
- `docs/Design-Base/90-third-party-service/50-openrouter.md`(430 修訂後版本)
- `docs/Tasks/v2.1/propose-v2.1.2.md` §B.1/§D.1/§D.2
