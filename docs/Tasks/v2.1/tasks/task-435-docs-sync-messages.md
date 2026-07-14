---
id: task-435
title: 文件:INTEGRATION.md §5/串流章節 + examples/sdk_example.py + README.md 同步 messages 契約
status: done
parallel: true
depends_on: [task-433]
affected_files:
  - docs/INTEGRATION.md
  - examples/sdk_example.py
  - README.md
estimated_hours: 2
---

## 目標

對外串接文件同步 `messages` 契約(改對外 API 鏈路必同步使用者文件):`docs/INTEGRATION.md` §5 request body 欄位表 + 範例 + 串流章節、`examples/sdk_example.py` 加多輪範例、`README.md` API 端點說明補註。

## 實作要點(對齊 propose §E / 對外承諾)

- `INTEGRATION.md`:
  - §5 欄位表(現 L64-77)新增四列:`messages`(型別、optional、role/parts 白名單、與 `text/images/files` 互斥、不設筆數上限)+ `temperature`(0–2)/ `max_tokens`(≥1)/ `response_format`(json_object / json_schema;兩模式皆可帶、未帶走模型預設)。
  - §7 完整範例區新增:messages 多輪範例(curl + Python 各一;含 system prompt + 兩輪對話)+ 生成參數範例(至少一個 json_object 結構化輸出範例)。
  - 串流章節(現 L377-440)確認「Request Body 欄位與 §4/§5 完全相同」敘述仍成立(messages 與生成參數適用於 stream)。
- `examples/sdk_example.py`:新增 messages 多輪呼叫範例函式 + 帶生成參數的範例(與既有範例風格一致)。
- `README.md`:端點總表(現 L165 附近)`/model/chat` 說明補「支援 messages 多輪與 temperature/max_tokens/response_format」。
- 內容以 433 完成後的實際契約為準(欄位名 / 錯誤碼與 `/api/docs` 一致);**禁**寫入未開放的參數(top_p / stop 等 Out of Scope)。

## Acceptance

- [ ] `grep -n "messages" docs/INTEGRATION.md` 命中 §5 欄位表、範例、串流章節三處以上;`grep -nE "temperature|max_tokens|response_format" docs/INTEGRATION.md` 命中欄位表與範例
- [ ] `grep -nE "messages|temperature" examples/sdk_example.py` 命中新增範例;`uv run python -m py_compile examples/sdk_example.py` 通過
- [ ] `grep -n "messages" README.md` 命中端點說明
- [ ] 文件中的欄位名 / 互斥規則 / 值域 / 錯誤碼與 433 整合測試斷言一致(人工比對 `/api/docs`)
- [ ] 未出現 top_p / stop / penalties 等未開放參數的教學內容

## 必讀檔(Just-in-time)

- `docs/Design-Base/00-overview/00-overview.md`(輸出語言)
- `docs/Design-Base/00-overview/04-api-docs.md`
- `docs/Design-Base/90-third-party-service/50-openrouter.md`(430 修訂後版本,契約敘述對齊)
- `docs/Tasks/v2.1/propose-v2.1.2.md` 對外承諾/§B.1
