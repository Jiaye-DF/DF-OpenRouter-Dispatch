---
id: task-438
title: e2e:兩功能端到端驗證 + e2e_smoke.py 擴充(多輪 curl / stream / 明細渲染 / 停用斷權鏈)
status: done
parallel: true
depends_on: [task-433, task-434, task-437]
affected_files:
  - backend/scripts/e2e_smoke.py
estimated_hours: 2
---

## 目標

以真實 dev 環境(`/dev-up`)端到端驗證兩功能,並把可自動化的斷言擴充進 `backend/scripts/e2e_smoke.py`:功能一(messages 多輪 / stream / 互斥 400 / 用量明細)、功能二(停用斷權鏈:SDK 401 → 登入 401 → 啟用後重發 token 可用)。

## 實作要點

- `e2e_smoke.py` 新增兩組 scenario(風格對齊既有 smoke 結構):
  - **messages + 生成參數**:multi-turn(system + 2 輪 user/assistant)打 `/api/v1/model/chat` 斷言 200 + 純文字;同 body 打 `/model/chat/stream` 斷言 SSE 有內容;`messages`+`text` 同時帶斷言 400;`temperature=0` + `max_tokens` + `response_format={"type":"json_object"}` 斷言 200 且回覆可 `json.loads`;`temperature=3` 斷言 400;舊模式(只帶 text、無生成參數)斷言 200(回歸)。
  - **disable**:建測試使用者 + 產 token → token 呼叫 200 → admin PATCH `is_active=false` → 同 token 呼叫 401 → 該使用者登入 401 → PATCH `is_active=true` → 原 token 仍 401 → 重發 token → 新 token 200。收尾清理測試資料。
- 手測(無法自動化的部分):用量明細頁 messages 分角色渲染(434)、使用者頁 Switch 流程(437)——逐條照 propose 驗收標準走並在本 task 勾記。
- 發現缺陷:能歸因單一 task → 回該 task 修;跨 task 根因 → 寫 `docs/Tasks/v2.1/fixed.md`(§N 格式)。

## Acceptance

- [ ] `uv run python backend/scripts/e2e_smoke.py`(dev 環境啟動下)全 scenario PASS,含新增 messages 與 disable 兩組
- [ ] 手測勾記:434 三 case(messages 渲染 / 舊紀錄回歸 / null 佔位)+ 437 四 case(停用 / 啟用 / 自己 disabled / 取消)全過
- [ ] propose v2.1.2「驗收標準」功能一 / 功能二逐條核對通過(缺項列出並開 fixed.md)
- [ ] `uv run ruff check backend/scripts/e2e_smoke.py` 零錯誤零 warning

## 必讀檔(Just-in-time)

- `docs/Design-Base/99-code-review/00-overview.md`(Acceptance gate)
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/01-propose/04-fixed-format.md`(缺陷寫入 fixed.md)
- `docs/Design-Base/90-third-party-service/50-openrouter.md`(430 修訂後版本)
- `docs/Tasks/v2.1/propose-v2.1.2.md` 驗收標準(逐條核對來源)
