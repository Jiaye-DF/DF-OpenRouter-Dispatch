# Tasks v2.1.2 · Chat API `messages[]` + 生成參數 + 使用者停用/啟用(停用即全 Token 撤銷)

> 狀態:**實作完成(9/9,2026-07-14)**;user 2026-07-14 批准 task-430 Design-Base 修訂 + 整批執行,multi-agent 派工。後端測試 258 passed(新增 94 案例)、前端 lint/tsc 全綠。**待辦**:438 的 `e2e_smoke.py` 需 dev 環境 + 真實 OpenRouter 消費,腳本已備妥待 user 手動實跑;434/437 的 UI 手測勾記待 user 驗收。
> 來源:[propose-v2.1.2.md](./propose-v2.1.2.md)(2026-07-14 全數定案;同日增補三生成參數 §D.7,orchestrator 已重跑拆解);母本鏈 v1.6.1 tools 透傳 / v1.8 files(ChatRequest 擴充前例)、v1.9.x User-Token 生命週期 → 本版
> 並行:9 個 task 中起點 2 並行(批次 A)/ 最長序列鏈 5(430→431→432→433→435)/ 預估總時數:20 hr / 阻塞點:1(**task-430 動 Design-Base 規範檔,需 user 明確批准後才可執行**;批准前功能一鏈全部 blocked,功能二鏈 436→437 不受影響可先行)

## 對齊的 Design-Base 章節

- 拆解:`01-propose/02-task-decomposition.md`、`03-multi-agent-flow.md`、`90-project-task-spec.md §2.3/§4`
- 規範演進:`01-propose/07-rule-evolution.md`(430 修訂 `50-openrouter.md` 收斂原則,先改規範再實作)
- 後端:`03-backend/01-routing.md`(ApiResponse 外殼 / Pydantic schema)、`90-project-backend.md §1/§2`(統一 Response / 錯誤訊息)、`02-auth.md` + `92-project-permission.md`(代理端/管理端分離、§9 稽核)、`07-testing.md`
- 第三方:`90-third-party-service/50-openrouter.md`(payload 組裝 / §9 錯誤對應 / §10 usage_logs)
- 前端:`02-frontend/05-components.md`(Switch 元件必抽共用)、`90-project-frontend.md`、`91-project-ui-ux.md`、`02-api-and-state.md`
- API docs:`00-overview/04-api-docs.md`

## Definition of Done

- [x] `POST /api/v1/model/chat`、`/model/chat/stream` 接受 optional `messages`(role 白名單 system/user/assistant;parts 白名單 text/image_url/file);與 `text/images/files` 同時帶 → 400;`messages=[]` → 400;舊 client(text/images/files)行為與 v2.1.1 完全一致(整合測試斷言 payload 位元級一致)
- [x] 接受 optional `temperature`(0–2)/ `max_tokens`(≥1)/ `response_format`(json_object / json_schema 型別化白名單):兩模式皆可帶、未帶不注入 payload(模型預設)、越界/非白名單 → 400;top_p / stop 等其餘生成參數不開放(schema `extra="forbid"`)
- [x] **不設應用層筆數上限**(模型 context window 為自然上限;超限由 OpenRouter 回錯沿既有錯誤鏈轉失敗回應)
- [x] messages 模式 `request_content` 原樣快照(file part 僅記 filename;有帶的生成參數一併入快照);用量明細頁分角色渲染;舊紀錄渲染不變(UI 手測待 user 勾記)
- [x] 使用者管理頁停用/啟用 Switch + 確認對話框;停用觸發 `revoke_tokens(reason="user_disabled")`(落地 token + 浮水印雙表);admin 不可停用自己(前端 disable + 後端 400 `cannot_disable_self`);重新啟用不復活 token(UI 手測待 user 勾記)
- [x] 停用後:SDK `x-user-token` 401 / 本地與 SSO 登入 401 / 既有 session 下一請求 401(後兩者為現況,測試補護欄)
- [x] `docs/INTEGRATION.md`(§5 + §5.4/§5.5 + 串流章節)+ `examples/sdk_example.py` + `README.md` 同步 `messages` 契約;`/api/docs` 可查(openapi 測試斷言四欄位)
- [x] Design-Base `50-openrouter.md` 已先修訂(§6.1/§6.2,commit e9baa92)再實作
- [x] 後端測試覆蓋:schema 驗證 / payload 透傳 / 快照 / 停用撤銷雙表 / sdk_auth 401 / 擋登入(新增 94 案例);`ruff` / `npm run lint` / `tsc` 本版檔案零錯誤零 warning;`mypy` 本版變更檔零新增錯、全倉維持既有 baseline(見 fixed.md §12)
- [x] 無新增 env、無 migration(本版不動 DB schema)

## 拆解總表

| # | 標題 | 狀態 | 並行 | 依賴 | 影響檔案 |
| --- | --- | --- | --- | --- | --- |
| 430 | 規範前置:修訂 Design-Base `50-openrouter.md` 開放 messages 白名單透傳 + 三生成參數(**需 user 批准**) | done | ✓ | — | `docs/Design-Base/90-third-party-service/50-openrouter.md` |
| 431 | 後端:`ChatMessage`/`ChatContentPart` schema + `ChatRequest.messages` + 生成參數三欄(temperature/max_tokens/response_format)+ 互斥/白名單/值域驗證 + 單元測試 | done | ✓ | 430 | `backend/app/schemas/model.py`、`backend/tests/schemas/test_chat_request_messages.py` |
| 432 | 後端:proxy service messages 透傳 + 生成參數注入(`_rewrite_request` + `run_chat`/`run_chat_stream` 簽章 + `_build_request_log` 快照)+ 單元測試 | done | ✓ | 431 | `backend/app/services/proxy.py`、`backend/tests/services/test_proxy_messages.py` |
| 433 | 後端:`model_chat` 端點打通(chat / chat/stream / deprecated alias)+ 整合測試 + `/api/docs` | done | ✓ | 432 | `backend/app/api/v1/model_chat.py`、`backend/tests/api/test_model_chat_messages.py` |
| 434 | 前端:用量記錄明細頁 messages 模式相容渲染(分角色;舊單輪形狀不變) | done | ✓ | 432 | `frontend/src/app/(main)/usage-logs/[uid]/page.tsx` |
| 435 | 文件:`INTEGRATION.md` §5/串流章節 + `examples/sdk_example.py` + `README.md` 同步 messages 契約 | done | ✓ | 433 | `docs/INTEGRATION.md`、`examples/sdk_example.py`、`README.md` |
| 436 | 後端:`update_user` 停用即 `revoke_tokens("user_disabled")` + 不可停用自己(400)+ 測試(撤銷雙表/sdk_auth 401/擋登入/啟用不復活) | done | ✓ | — | `backend/app/api/v1/users.py`、`backend/tests/api/test_users_disable.py` |
| 437 | 前端:新增 `Switch` 共用元件 + 使用者管理頁停用/啟用開關 + 確認對話框(含撤銷警告)+ 自己那列 disable | done | ✓ | 436 | `frontend/src/components/ui/switch.tsx`、`frontend/src/app/(main)/users/page.tsx`、`frontend/src/types/api.ts` |
| 438 | e2e:兩功能端到端驗證 + `e2e_smoke.py` 擴充(多輪 curl / stream / 明細渲染 / 停用斷權鏈) | done | ✓ | 433, 434, 437 | `backend/scripts/e2e_smoke.py` |

## 執行流程(multi-agent)

- **批次 A(起點)**:430(規範修訂,**等 user 批准**)∥ 436(後端停用即撤銷)。兩者檔案無重疊。
- **批次 B**:431(schema,430 done 後)∥ 437(前端開關,436 done 後取 400 錯誤碼契約)。
- **批次 C**:432(proxy service,431 done 後)。
- **批次 D**:433(端點 + 整合測試)∥ 434(前端明細渲染;快照形狀由 432 落地)。
- **批次 E**:435(文件,433 契約定稿後)∥ 438(e2e,433+434+437 done 後)。

> 跨 area 三段鏈:功能一 後端(431→432→433)→ 前端(434)→ e2e(438);功能二 後端(436)→ 前端(437)→ e2e(438)。
> 功能二鏈(436→437)**不依賴** 430 批准,可先行開工。

## 檔案重疊序列化說明

- 全 9 task `affected_files` **兩兩無重疊**,序列化純由 `depends_on` 表達(契約先行),無同檔互鎖。
- `frontend/src/types/api.ts` 僅 437 動(user 更新 payload 型別);434 的明細渲染以頁面內區域型別判別 `request_content` 形狀,**不**動 `types/api.ts`——若實作中發現必須動,先回報 orchestrator 重排,禁自行擴檔。
- `docs/Design-Base/50-openrouter.md` 為規範底線檔,僅 430 單獨動(對齊 `02-task-decomposition.md § 拆解禁忌`)。

## 拆解註記(orchestrator)

- **scope 守門**:9 task 全映自 propose `In Scope`(功能一:規範 430 / schema 431 / service 432 / 端點 433 / 前端明細 434 / 文件 435;功能二:後端 436 / 前端 437;測試補強折入各 task + e2e 438),無 orphan、無超出 scope。
- **阻塞點唯一 = 430**:動 `docs/Design-Base/*` 屬規範修訂,orchestrator 與 worker 皆**不得**未經 user 批准執行;user 批准(或自行修訂)後 431 才可開工。propose 決議 #9 已載明「先修訂再實作」。
- **驗證鏈不動**:436 只動 `update_user` 觸發撤銷;`sdk_auth.py` / `deps.py` / `auth.py` / `sso.py` 的 `is_active` 檢查為現況已存在,436 的測試僅補護欄**不**改其程式碼(不列入 affected_files)。
- **筆數上限**:user 拍板不設應用層上限(模型 context window 自然限制),431 驗證只做互斥 + 白名單 + 空陣列 + 生成參數值域。
- **拆解後增補重跑**(2026-07-14):user 拍板加開 `temperature` / `max_tokens` / `response_format` 三生成參數(propose §D.7);受影響 tasks = 430(規範修訂範圍)/ 431(schema 三欄 + 值域,2→3 hr)/ 432(payload 注入 + 快照)/ 433(整合測試案例 + openapi 斷言)/ 435(文件欄位表 + 範例;原「禁出現 temperature」驗收反轉為「須出現」)/ 438(e2e json_object + 越界 400 案例)。434/436/437 不受影響;依賴圖與檔案鎖不變。
- **版號**:propose 檔首註記——按判準屬 minor;user 已拍板落 v2.1.2,檔案落於 `docs/Tasks/v2.1/`。
