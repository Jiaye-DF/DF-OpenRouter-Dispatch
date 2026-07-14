[//]: # (此檔為 v2.1.2 任務提案,實作前先由使用者確認範圍與設計取捨。Agent 草擬、User 拍板。)

# Propose v2.1.2 · Chat API 開放 OpenRouter `messages[]` 串接參數 + 使用者停用/啟用開關(停用即全 Token 撤銷)

> 此為 **proposal**(詳設母本),確認後即據以拆 `workflow/` + `tasks/`。
>
> 對應母本鏈:[v1.6.1 tools 透傳](../v1.6/v1.6.1/propose-v1.6.1.md)、[v1.8 files 上傳](../v1.8/propose-v1.8.0.md)(ChatRequest 逐欄位擴充前例) → 本版。功能二與 v1.9.x User-Token 生命週期(浮水印撤銷)銜接。
>
> **狀態**:皆為**定案**(user 2026-07-14 拍板)。版號落 v2.1.2;messages 互斥、**不設應用層筆數上限**(模型 context window 為自然上限);快照原樣入 JSONB;功能二三細節(不復活 token / 不可停用自己 / Switch 元件)全採建議。**同日增補**:功能一加開三個生成參數 `temperature` / `max_tokens` / `response_format`(user 拍板);其餘生成參數(top_p / stop / penalties 等)維持不開放。

---

## ⚠️ 版號判定註記(需 user 確認)

依 [`01-propose/05-version-bump.md`](../../Design-Base/01-propose/05-version-bump.md) 判準:

- 功能一為 **API request optional 欄位新增**(`messages`;舊 client 不帶行為完全不變)→ 屬 **minor**。
- 功能二後端 `PATCH /users/{uid}` **已可**收 `is_active`(schema 早已存在),主要是前端 UI + 停用時主動撤銷 token 的行為補強;「停用即撤銷」對被停用者屬權限收緊,但停用本為管理動作、且驗證鏈**現況已**擋停用者,不視為 breaking → 屬 minor / patch 邊界。

綜合(尤其功能一)按判準應為 **minor(→ v2.2.0)**,非 patch。前例:v2.1.1 同樣按判準屬 minor、依 user 指示落 v2.1.x。**本檔依 user 指示暫以 v2.1.2 落檔**;若希望對外開新 API 版,建議改置於 `docs/Tasks/v2.2/propose-v2.2.0.md`。**版號最終由 user 決定**。

## ⚠️ Design-Base 前置修訂(規範優先序)

功能一與 [`90-third-party-service/50-openrouter.md`](../../Design-Base/90-third-party-service/50-openrouter.md) 現行**收斂原則**衝突:該文件(及 `proxy.py:101-110` docstring)明定「SDK 使用者只給 text/images/files/tools,其餘 OpenAI 欄位一律不開放、平台從頭建構 messages」。依規範優先序(Design-Base 為不可違反的地板),**實作前須先修訂 `50-openrouter.md`**,把「開放呼叫端自帶 `messages[]`(白名單驗證後透傳)」納入規範,再據以動工(對齊 [`01-propose/07-rule-evolution.md`](../../Design-Base/01-propose/07-rule-evolution.md))。

---

## 版本目標

兩件對「串接彈性 / 帳號治理」有價值的補強:

1. **Chat API 開放 `messages[]` 與生成參數**:對外 `POST /api/v1/model/chat`(含 `/chat/stream`)目前只接受單輪 `text/images/files`,由平台自建單一 user 訊息;新增 OpenRouter 風格的 `messages[]` 參數,讓串接端可直接傳**多輪對話 / system prompt / assistant 歷史**,並開放 `temperature` / `max_tokens` / `response_format` 三個生成參數(控制隨機性 / 回覆長度 / JSON 模式),支撐進階串接情境(對話記憶、角色設定、結構化輸出、成本控制),為日後 session 記憶鋪路。
2. **使用者停用/啟用開關**:使用者管理頁面目前只有唯讀狀態 Badge,無法從 UI 停用帳號;新增停用/啟用切換,且**停用 = 該使用者全部 UserToken 即刻撤銷**(落地 token 標記撤銷 + 浮水印,SDK 呼叫、登入、既有 session 全面失效),讓 admin 對離職/異動帳號一鍵斷權。

## In Scope

### 功能一 · Chat API `messages[]` 參數 + 生成參數

- **`ChatRequest` 新增 optional `messages` 欄位**(§B.1):OpenRouter/OpenAI 風格 `list[{role, content}]`;`role` 白名單(`system` / `user` / `assistant`),`content` 支援字串或 parts 陣列(`text` / `image_url` / `file`,與現有單輪能力對齊)。
- **與既有欄位的互斥規則**(§B.1 / §D.1):`messages` 與 `text` / `images` / `files` **擇一**;同時帶 → `400` 驗證錯誤(不做隱式合併,避免語意歧義)。`tools` 兩種模式皆可搭配。
- **開放三個生成參數**(§B.1 / §D.7,user 2026-07-14 增補拍板):`temperature`(float,0–2)、`max_tokens`(int,≥1)、`response_format`(型別化白名單:`json_object` / `json_schema`);**單輪與 messages 兩種模式皆可帶**;未帶 → 不注入 payload,走模型預設值。其餘生成參數(top_p / stop / penalties 等)維持不開放。
- **payload 組裝**(§B.2):`_rewrite_request` 增加 messages 分支——驗證通過後**透傳**進 OpenRouter payload(不重組);單輪舊路徑組裝邏輯**不動**。
- **雙端點同步**(§B.2):`/model/chat` 與 `/model/chat/stream` 的 request body 保持一致(串流僅多 `stream` 注入,現況不變);internal provider 路徑同步支援(payload 結構相同)。
- **usage_logs 快照**(§B.3):`_build_request_log` 支援 messages 模式的 `request_content` 快照;前端用量記錄明細頁相容渲染多輪內容。
- **文件同步**(§E):`docs/INTEGRATION.md` §5 request body 欄位表 + 範例 + 串流章節、`examples/sdk_example.py`、README 端點說明、Design-Base `50-openrouter.md`(前置修訂)。
- **測試**(§F):chat proxy 鏈路目前**零測試**;本版補上 `_rewrite_request` / `ChatRequest` 驗證 / messages 透傳 / 生成參數注入的單元測試護欄。

### 功能二 · 使用者停用/啟用(停用即全 Token 撤銷)

- **前端切換開關**(§C.1):使用者管理頁(`/users`)每列狀態由唯讀 Badge 改為**可切換開關**(新增 `components/ui/switch.tsx`),切換前彈確認對話框(停用時明示「將撤銷該使用者全部 Token」),打既有 `PATCH /api/v1/users/{uid}` 送 `{is_active}`。
- **停用即主動撤銷**(§B.4):`update_user` 偵測 `is_active` 由 `true → false` 時,呼叫既有 `user_token_service.revoke_tokens(reason="user_disabled")`——落地 token 標記 `revoked_at` + 寫 `UserTokenRevocation` 浮水印(未落地舊 token 一併失效),與 v1.9.x 撤銷語意一致。
- **重新啟用語意**(§D.3):啟用**不**自動復活已撤銷 token;需 admin 重新「產生 Token」(既有功能)。
- **稽核**(§B.4):沿用 `update_user` 稽核(`extra` 已含變更欄位 + `tokens_revoked` 旗標);停用/啟用即自然留痕。
- **測試**(§F):停用後 SDK 驗證 401、停用後擋登入/session、PATCH `is_active=false` 觸發 revoke、重新啟用不復活 token。

## Out of Scope

- **其餘 OpenRouter 生成參數**:`top_p` / `stop` / `frequency_penalty` / `presence_penalty` / `seed` / `logit_bias` 等**本版不開放**(只開 user 拍板的 `temperature` / `max_tokens` / `response_format` 三項;若日後需要另立 propose)。
- **伺服器端 session 記憶**:本版只讓呼叫端**自帶**多輪 messages,平台不儲存/管理對話歷史(session 記憶為日後方向,見 roadmap)。
- **response 格式改動**:回應維持 `success_response(data=<純文字>)`,不因 messages 模式改回完整 OpenRouter response(不外露內部欄位原則不變)。
- **細粒度 token 撤銷**:維持 per-user 全撤(一人一把設計),不做單一 token 撤銷。
- **使用者刪除功能**:不新增 delete endpoint;停用 ≠ 刪除(`is_deleted` 軟刪除機制不動)。
- **批次停用 / 到期自動停用**:單筆手動切換為限。

## 對外承諾

- **API request 欄位新增**(`/api/docs` 可查):
  - `POST /api/v1/model/chat`、`POST /api/v1/model/chat/stream`(及 deprecated `/model/openrouter/chat`)request body 新增 **optional `messages`** 欄位;與 `text/images/files` 同時帶 → `400`;舊 client(只帶 text/images/files)**行為完全不變**。
  - 同批新增 **optional `temperature` / `max_tokens` / `response_format`** 三個生成參數(兩種模式皆可帶;未帶走模型預設;超出範圍 / 非白名單格式 → `400`)。
- **行為承諾**(功能二):
  - admin 於使用者管理頁切換停用 → 該使用者:❶ 全部 UserToken 即刻撤銷(SDK 呼叫 401);❷ 無法登入(本地/SSO);❸ 既有 session 下一請求即被踢(401)。其中 ❷❸ 為現況已成立,本版把 ❶ 從「驗證時被動失效」補強為「主動撤銷 + 留痕」。
  - 重新啟用後可再登入,但 token 需重新產生。
- **文件承諾**:`INTEGRATION.md` 同步 `messages` 契約與範例(改對外 API 鏈路必同步使用者文件)。

## 資料流

### 功能一(messages 模式)

```
[串接端] POST /api/v1/model/chat
   body: { model, messages: [{role:"system",...},{role:"user",...},...], tools?,
           temperature?, max_tokens?, response_format? }
   ▼
ChatRequest 驗證:role 白名單 / content 形狀 / 與 text·images·files 互斥 /
                 temperature 0–2 / max_tokens ≥1 / response_format 白名單(違反 → 400)
   ▼
run_chat → _rewrite_request:
   ├─ 有 messages → 驗證後透傳:payload = { model, messages, tools? }
   └─ 無 messages → 現況單輪組裝(不動)
   └─ 生成參數(兩模式共用):有帶才注入 payload(temperature / max_tokens / response_format)
   ▼
OpenRouterClient.chat_completion(payload)   ← client 純 pass-through,不需改
   ▼
回應抽純文字 → success_response(data=<text>)
   └─ 背景 schedule_usage_log:request_content 快照 messages(§B.3 策略)
```

### 功能二(停用)

```
[admin] 使用者管理頁切換開關(停用)→ 確認對話框
   ▼
PATCH /api/v1/users/{uid}  body: { is_active: false }   (AdminDep)
   ▼
update_user:
   ├─ setattr 寫入 is_active=False
   ├─ 偵測 true→false → user_token_service.revoke_tokens(reason="user_disabled")
   │     ├─ 落地 token:revoked_at + revoked_reason
   │     └─ UserTokenRevocation 浮水印(未落地舊 token 失效)
   └─ 稽核 update_user(extra: is_active 變更 + tokens_revoked)
   ▼
效果:SDK x-user-token → 401;登入(本地/SSO)→ 401;既有 session 下一請求 → 401
```

## 後端(§B)

### B.1 `ChatRequest` 新增 `messages`

- 落點:`backend/app/schemas/model.py`(`ChatRequest`,現 L21-40)。
- 新增 `messages: list[ChatMessage] | None = None`;新增 `ChatMessage` schema:
  - `role: Literal["system", "user", "assistant"]`(白名單,`tool` role 本版不開放,§D.2)。
  - `content: str | list[ChatContentPart]`;parts 支援 `text` / `image_url` / `file`(與現有單輪能力集對齊;`video` 維持 400 拒收)。
- **互斥驗證**(model validator):`messages` 與 `text` / `images` / `files` 任一同時非空 → `400`(§D.1);`messages` 為空陣列 → `400`。
- **不設應用層筆數上限**(§D.2 定案):模型 context window 為自然上限,超過由 OpenRouter 回錯誤(沿既有錯誤處理鏈轉為失敗回應);request body 大小沿用平台既有限制。
- **生成參數三欄**(§D.7 定案):
  - `temperature: float | None`(`ge=0, le=2`,對齊 OpenAI/OpenRouter 值域)。
  - `max_tokens: int | None`(`ge=1`;上限交由模型/OpenRouter 把關,不設應用層上限——與 §D.2 同理)。
  - `response_format: ResponseFormat | None`:型別化 schema(**禁** raw dict),`type: Literal["json_object", "json_schema"]`;`json_schema` 型別時帶 `json_schema` 物件透傳。
  - 三欄未帶(None)→ **不注入 payload**,走模型預設值;單輪與 messages 模式皆可帶。

### B.2 payload 組裝與雙端點打通

- 落點:`backend/app/services/proxy.py`:
  - `_rewrite_request`(L94-128)增加 messages 分支:驗證後 `payload = {"model": model, "messages": [m.model_dump(...) for m in messages]}` 透傳;`tools` 附掛邏輯共用;單輪路徑不動。
  - **生成參數注入**(兩模式共用,§D.7):`temperature` / `max_tokens` / `response_format` 有帶(非 None)才 `payload[key] = value`;None 一律不出現在 payload。
  - `run_chat`(L377-446)/ `run_chat_stream`(L851-917)簽章增加 `messages` 參數(沿 v1.6.1 tools、v1.8 files 的逐欄位擴充模式)。
- 落點:`backend/app/api/v1/model_chat.py` `_chat_handler`(L27-60)與 `chat_stream`(L77-134)把 `body.messages` 傳入 service。
- client 層(`backend/app/clients/openrouter/client.py`、`internal/client.py`)為純 pass-through,**不需改動**。
- internal provider 路徑(`_run_chat_internal`)payload 結構相同,messages 模式自然支援;白名單 / failover 邏輯不動。

### B.3 usage_logs 快照策略

- 落點:`backend/app/services/proxy.py` `_build_request_log`(L131-151)。
- messages 模式:`request_content = {"model": model, "messages": <快照>}`;快照策略見 §D.4(定案:messages 原樣入 JSONB,與現況 `images` 存 base64 一致;檔案 part 仿現況只記 `filename` 不記 `file_data`)。
- **生成參數入快照**:有帶的 `temperature` / `max_tokens` / `response_format` 一併記入 `request_content`(兩模式皆同),供用量明細追溯呼叫條件。
- **不動 DB schema**(`request_content` 本為 JSONB);`used_tools` 推導不受影響。
- 明細 schema(`backend/app/schemas/usage_log.py` `UsageLogDetail`)欄位不變;前端明細頁相容渲染(§C.2)。

### B.4 停用即撤銷 + 稽核

- 落點:`backend/app/api/v1/users.py` `update_user`(L154-203)。
- 現況缺口:token 撤銷 snapshot(L169)只含 `username/employee_id/email/department_uid`,**不含 `is_active`** → 停用不會主動撤銷。
- 補強:偵測 `is_active` 由 `true → false` → `await user_token_service.revoke_tokens(db, user_uid=..., reason="user_disabled")`(service 現成:`backend/app/services/user_token.py` L75-103,雙表處理);`false → true` **不**觸發任何 token 動作。
- 稽核:沿用既有 `update_user` 稽核(L183-195,`extra` 含變更欄位 + `tokens_revoked`);不另立 action(§D.5 可拍板改為獨立 `disable_user` action)。
- 驗證鏈**不需改**:`sdk_auth.py:86`、`deps.py:49`、`auth.py:82/140`、`sso.py:125` 均已檢查 `is_active`。
- `generate_token`(`user_token.py:26`)已擋停用者 → 停用中無法產生新 token,現況即正確。

## 前端(§C)

### C.1 使用者管理頁停用/啟用開關

- 落點:`frontend/src/app/(main)/users/page.tsx`。
- 狀態欄(現 L581-585 唯讀 Badge)改為 **Switch 開關 + 狀態文字**;切換時走既有 `useConfirm` 確認流程(參考撤銷 Token 流程 L381-414),停用文案明示「停用後將撤銷其全部 Token,SDK 呼叫與登入即刻失效」。
- 呼叫:`PATCH API_ENDPOINTS.userById(uid)` 送 `{ is_active }`(endpoints 現成);成功後刷新列表 + toast。
- 新增 UI 元件:`frontend/src/components/ui/switch.tsx`(現無 Switch;風格對齊既有 ui 元件,§D.6 可改用 Button toggle)。
- 防呆:admin **不可停用自己**(前端 disable 自己那列的開關;後端同步擋 `actor.user_uid == target` 停用自己 → 400,§D.5)。
- 型別:`frontend/src/types/api.ts` `User.is_active` 已存在,不需改。

### C.2 用量記錄明細頁 messages 相容

- 落點:`frontend/src/app/(main)/usage-logs/[uid]/page.tsx`(明細頁 `request_content` 渲染區)。
- 現況假設 `request_content` 為 `{text, images, ...}` 單輪結構;新增 messages 模式渲染:依 role 分段顯示(system / user / assistant),content parts 依型別呈現(text 文字、image 縮圖、file 檔名)。
- 舊紀錄(單輪結構)渲染**不變**(以形狀判別,不做資料遷移)。

## 設定(環境變數)

- 功能一 / 功能二:**皆無新增 env、無 migration、不動 DB schema**(功能一為 optional 欄位 + 透傳;功能二用既有欄位 + 既有撤銷 service)。

## D. 已決議細節(user 2026-07-14 拍板)

### D.1 `messages` 與既有欄位的關係 — 採「互斥、同時帶 400」

`messages` 與 `text/images/files` 同時帶 → 400。語意最清晰、無合併歧義,舊 client 零影響。(已捨棄「messages 優先隱式忽略」與「合併為最後一則 user 訊息」兩案。)

### D.2 `messages` 驗證嚴格度 — 採「role/parts 白名單、**不設筆數上限**」

- `role` 只收 `system/user/assistant`(`tool` role 與 `tool_calls` 回傳鏈本版不開放——工具結果回傳屬進階多輪工具流,留待日後);content parts 只收 `text/image_url/file`。
- **不設應用層筆數上限**(user 拍板):模型本身的 context window 即自然上限(多輪 messages 全數計入 token),超限由 OpenRouter 回錯誤、沿既有錯誤處理鏈轉為失敗回應;不另設 ≤ N 則的人為限制。

### D.3 重新啟用語意 — 採「不自動復活 token」

停用時已寫浮水印 + 標記撤銷,屬**不可逆**撤銷動作;重新啟用後由 admin 用既有「產生 Token」重發(冪等 `get_or_create_token` 會發新 token)。

### D.4 `request_content` 快照策略 — 採「messages 原樣入 JSONB(file 僅記檔名)」

與現況一致(`images` 本就存 base64 原樣);多輪歷史含多張 base64 圖片時 JSONB 體積較大——對齊既有圖片儲存 roadmap(2026-06 起規劃搬 S3),本版不特別處理,僅 file part 仿現況只記 `filename`。(已捨棄「image part 截斷為佔位字串」案。)

### D.5 停用防呆與稽核粒度 — 採「不可停用自己 + 稽核沿用 update_user」

- **不可停用自己**:後端擋 `actor == target` 的停用(400),前端同步 disable 自己那列的開關——避免 admin 把自己鎖死。
- 稽核 action:沿用 `update_user`(extra 含 `is_active` 變更 + `tokens_revoked` 可辨識),不另立獨立 action。

### D.6 開關 UI 形式 — 採「新增 Switch 元件」

新增 `frontend/src/components/ui/switch.tsx`(Switch 語意最直覺,風格對齊既有 ui 元件)。

### D.7 生成參數三欄(user 2026-07-14 增補拍板)

- **開放名單 = `temperature` / `max_tokens` / `response_format` 三項**(user 點名);top_p / stop / penalties 等其餘生成參數維持不開放(Out of Scope)。
- 值域與形狀(Agent 細部設計,對齊 OpenAI/OpenRouter 慣例):`temperature` 0–2;`max_tokens` ≥ 1(上限交模型把關,同 §D.2 精神);`response_format` 型別化白名單 `json_object` / `json_schema`(禁 raw dict 透傳,防夾帶)。
- **兩模式皆可帶**(生成參數與內容模式正交);未帶不注入 payload,走模型預設。
- 有帶即記入 `request_content` 快照(§B.3),供追溯。

## 風險與相依

- **收斂原則突破(功能一)**:`messages` 與生成參數透傳打開了原本封閉的輸入面——驗證務必走 **schema 白名單**(role / parts 型別 / response_format 型別化),**禁止** dict 原樣透傳未知欄位(防呼叫端夾帶 `top_p` 等未開放參數與 prompt-injection 面擴大);Design-Base `50-openrouter.md` 須**先修訂**再實作(見開頭註記)。
- **成本面(max_tokens / temperature)**:生成參數影響回覆長度與品質,但成本記帳走既有 usage_logs 實際 token 計量,不受影響;快照記錄參數供事後追溯,本版不做參數級配額。
- **無測試護欄**:chat proxy 鏈路與 users/token 鏈路目前**皆零測試**;本版兩功能都動到關鍵路徑,測試列為交付項而非選配(§F)。
- **request_content 體積**:多輪 base64 圖片使 JSONB 快照變大(D.4);與 S3 roadmap 相依,本版接受現狀。
- **明細頁相容**:messages 模式的 `request_content` 形狀改變,若前端未同步相容渲染,用量明細頁會壞——功能一的前後端須同版上線。
- **停用即斷權的爆炸半徑(功能二)**:撤銷不可逆 + 既有 session 即刻失效,誤觸成本高 → 確認對話框 + 不可停用自己為必要防呆;撤銷語意沿用 v1.9.x 現成 service,風險低。
- **文件同步**:`INTEGRATION.md` / SDK 範例 / 使用者教學 HTML 未同步會造成串接端誤用(對外 API 鏈路變更必同步文件)。
- **版號**:見開頭「版號判定註記」——按判準屬 minor;user 已拍板落 **v2.1.2**(2026-07-14)。

## 驗收標準

### 功能一

- `POST /api/v1/model/chat` 帶 `messages`(含 system + 多輪 user/assistant)→ 正常回覆;`/model/chat/stream` 同 body 串流正常;internal provider 模型同樣支援。
- 舊 client 行為不變:只帶 `text/images/files` 的請求,payload 組裝與回應與 v2.1.1 完全一致。
- `messages` 與 `text/images/files` 同時帶 → 400;`messages=[]` → 400;role 非白名單 / parts 型別非白名單 → 400(422 統一包裝依現況);超長對話(超過模型 context window)由 OpenRouter 回錯 → 沿既有錯誤鏈轉失敗回應。
- 生成參數:帶 `temperature`(0–2)/ `max_tokens`(≥1)/ `response_format`(json_object / json_schema)→ payload 正確注入且回應正常(json_object 模式回覆為合法 JSON 字串);超出值域 / 非白名單 format → 400;未帶 → payload 不含該鍵(模型預設);單輪與 messages 模式皆可帶。
- `tools` 在 messages 模式可用(payload 正確附掛,`used_tools` 正確推導)。
- usage_logs:messages 模式的 `request_content` 依 §D.4 策略快照;明細頁能分角色渲染多輪內容;舊紀錄渲染不變。
- `/api/docs` 可查 `messages` 欄位;`INTEGRATION.md` §5 + 串流章節 + `examples/sdk_example.py` 已同步(含多輪範例)。
- 新增後端單元測試:`_rewrite_request` messages 分支、互斥驗證、白名單驗證、快照策略。

### 功能二

- 使用者管理頁每列有停用/啟用開關;切換彈確認對話框(停用文案含撤銷警告);成功後狀態即時更新。
- admin 停用某使用者後:❶ 該使用者 `x-user-token` SDK 呼叫 → 401;❷ 本地/SSO 登入 → 401(擋下);❸ 既有 session 下一請求 → 401;❹ `user_tokens` 該使用者有效 token 已標 `revoked_at` + `revoked_reason="user_disabled"`,`user_token_revocations` 有對應浮水印。
- 重新啟用後:可登入;原 token 仍失效;「產生 Token」可重發新 token 並正常呼叫。
- admin 無法停用自己(前端 disable + 後端 400)(若 §D.5 拍板採納)。
- 稽核:停用/啟用各留一筆 `update_user`(extra 含 `is_active` 變更與 `tokens_revoked`)。
- 新增後端測試:停用觸發 revoke(雙表)、停用後 sdk_auth 401、擋登入、重新啟用不復活 token、停用中 `generate_token` 拒發。

## 設計取捨 / 已決議(user 拍板)

| # | 決議 | 落點 |
| --- | --- | --- |
| 1 | 功能一開 `messages` + 三生成參數(`temperature` / `max_tokens` / `response_format`);其餘生成參數(top_p / stop 等)不開 | In Scope / §D.7 / Out of Scope |
| 2 | `messages` 與 `text/images/files` 互斥(同時帶 400) | §D.1 |
| 3 | role/parts 白名單;**不設應用層筆數上限**(模型 context window 為自然上限) | §D.2 |
| 4 | `request_content` 快照:messages **原樣**入 JSONB(file 僅記檔名) | §D.4 |
| 5 | 停用 = 主動 `revoke_tokens(reason="user_disabled")` + 浮水印 | §B.4(user 需求敘述即定案) |
| 6 | 重新啟用不自動復活 token,需重新產生 | §D.3 |
| 7 | 不可停用自己(前後端防呆);稽核沿用 `update_user` | §D.5 |
| 8 | 開關 UI:新增 Switch 元件 | §D.6 |
| 9 | Design-Base `50-openrouter.md` 先修訂再實作 | 規範要求(必做,見開頭註記) |
| 10 | **版號定案 v2.1.2**(user 知悉按判準屬 minor,仍指示落 v2.1.x) | 開頭註記 |

## 變更紀錄

| 日期 | 改動 | 理由 |
| --- | --- | --- |
| 2026-07-14 | 初版草擬:功能一(chat `messages[]` 參數)+ 功能二(使用者停用/啟用開關、停用即全 Token 撤銷);§D 設計取捨待拍板 | user 提出兩需求,Agent 依現況調查(chat 封閉輸入 / is_active 骨架已就緒)草擬詳設 |
| 2026-07-14 | 全數定案:版號 v2.1.2;互斥 400;白名單但**不設筆數上限**(模型 context window 自然限制);快照原樣;不復活 token / 不可停用自己 / Switch 元件 | user 拍板(問答確認);其中筆數上限 user 裁示交由模型本身上限把關 |
| 2026-07-14 | **拆解後增補**(§D.7):功能一加開 `temperature` / `max_tokens` / `response_format` 三生成參數(值域 0–2 / ≥1 / 型別化白名單,兩模式皆可帶,未帶不注入,快照記錄);Out of Scope 改為「其餘生成參數不開」。受影響 tasks:430/431/432/433/435/438(orchestrator 已重跑拆解) | user 拍板加開三參數(原列 Out of Scope) |
