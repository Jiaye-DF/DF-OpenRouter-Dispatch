---
id: task-533
title: AI 重跑恢復帶圖能力 — 後端下載 S3 物件、重新 inline 成 base64
status: done
parallel: true
depends_on: [task-523, task-526, task-531]
affected_files:
  - backend/app/clients/s3/client.py
  - backend/app/clients/s3/README.md
  - backend/app/services/ai_model_eval_rerun.py
  - backend/tests/clients/test_s3_client.py
  - backend/tests/services/test_rerun_inline_images.py
estimated_hours: 3
---

## 目標

遷移後 `usage_logs.request_content` 內的圖片是 **S3 物件 key**;`request_snapshot.replay_messages` 為避免產出畸形 payload 會把它剔除,導致 **AI 重跑對「messages 模式 + 含圖」的紀錄失去圖片**(v2.2.0 時本來會送 base64 給 challenger)。

本 task 由後端**自行下載 S3 物件、重新 inline 成 base64 data URI** 後送下游,把能力補回 v2.2.0 的水準。

## ⚠️ 為什麼是「下載 + inline」而不是「送 presigned URL」

**這是本 task 最重要的約束,先看懂再動手。**

送 presigned URL 給下游模型是**被明文禁止**的:

- [`09-object-storage.md:137`](../../../Design-Base/90-third-party-service/09-object-storage.md)(**Design-Base 地板**):
  > presigned URL 視同**臨時憑證**:**禁**寫入 log、**禁**存 DB、**禁**送給第三方 / 下游模型;只在 API response 即時產生給已認證的管理端使用者
- `S3Client.presign_get()` 的 docstring 同樣寫死「禁送下游模型」
- propose §D.4 / 決議 #6 / #15 是 **user 於 2026-07-29 明示定案的翻案**:presigned URL 用途**收斂為管理端明細頁顯示**,不用於下游模型

依 `docs/Design-Base/* > docs/Tasks/*` 的優先序,**不得**為了本 task 去鬆動這條地板。

**下載 + inline 才是真正的「恢復 v2.2.0 行為」**:v2.2.0 送給 challenger 的就是 base64,本方案送的也是 base64 —— 下游收到的東西一模一樣、簽章完全不外流、Design-Base 一個字都不用改。

> **✅ user 定案(2026-07-29)**:採方案 B(下載 + inline);方案 A(送 presigned URL)已否決。

## ⚠️ 這是「恢復」不是「擴大」

**單輪模式維持現行行為(不重放圖片)** —— 那是 v2.1.1 起的既有設計,不在本 task 範圍,不要順手改。

## 上一次嘗試留下的關鍵技術結論(直接沿用,不要重踩)

前一版實作(方案 A,已作廢)驗證出一個重要的注入位置結論:

> **替換必須發生在 `replay_messages()` 之前,不能在它之後。**

因為 `replay_messages` 的 `_is_replayable()` **已經把 `object_key` 形態的 image part 剔除了**,payload 產出後再走訪是撿不回來的。正確做法是先把**快照裡**的物件 key 換成 data URI(形態即變 `data_uri`),`replay_messages` 便依既有規則原樣保留 —— **剔除規則仍只有一份、留在純函式層**,本層不重寫。

附帶效果:下載失敗時「剔除該 part」是**免費得到的**(留著物件 key → 下游被 `replay_messages` 剔掉),不需要在 service 層複製剔除邏輯。

## 範圍(只做這些)

### 1. `S3Client` 新增 `get_object`

- `get_object(key: str) -> bytes`(或連同 content-type 一起回,由你判斷哪個對呼叫端更好用)。
- 走 `asyncio.to_thread` 包裹(對齊 `09-object-storage.md` 的同步 SDK 規則)。
- 錯誤一律轉既有 `S3Error` 子類;物件不存在的語意比照既有 `head_object`(不拋或拋 `S3NotFoundError`,擇一並在 docstring 寫明)。
- 沿用既有的短 timeout + 低重試 `Config`。
- `README.md` 補一條能力說明。
- `tests/clients/test_s3_client.py` 補測試(成功 / 404 / 逾時 / 錯誤轉型)。

### 2. `ai_model_eval_rerun.py` 注入 inline

- 在 `replay_messages()` **之前**,走訪快照 messages 的 content parts:
  - part 為 `image_url` 且形態經 `request_snapshot.attachment_form()` 判為 **`object_key`** → `get_object` 下載 → 組成 `data:<mime>;base64,<...>` 取代該 `url`。
  - `data_uri` / `remote_url` → **原樣保留**(既有行為,不動)。
  - `upload_failed` / `empty` → 維持剔除(交給 `replay_messages`)。
- **形態判別一律用 task-526 的公開 API**(`attachment_form` / `attachment_ref_of`),不要自己判斷字串。
- mime 推導:key 的副檔名由 `attachment.extension_for_mime()` 產生,反推可用 `attachment.content_type_for_mime()` 的對照關係,或直接取 `get_object` 回傳的 content-type。**不要**自己寫一份對照表。
- **回新 dict,不就地改 ORM JSONB**。
- **落地與 prompt 一律用原始 `request_content`**:`RerunInput.request_content` 與 `build_discriminator_prompt` 不得碰 inline 後的版本 —— 否則 base64 又會被寫回 DB,直接違反本版「快照零 base64」的硬規則。**這條必須有測試鎖住。**

### 3. best-effort

- 下載失敗(S3 不可用 / 逾時 / 物件不存在)→ 該 part 維持物件 key(下游端由 `replay_messages` 自然剔除)+ log warning,**不擋整個重跑**。
- `S3_STORAGE_ENABLED=false` → 完全不呼叫 S3,行為與現況一致。
- 快照內**沒有**任何 `object_key` 形態的圖片時,**完全不碰 S3**(不取 client、不讀設定)。

## 不做

- **不**動 `request_snapshot.py`(純函式、禁 I/O、禁 import app 模組;task-526 已有機械測試鎖住)。
- **不**動 `attachment.py`、`proxy.py`、`app/api/`。
- **不**改重跑的判分邏輯 / prompt / 派發策略 / 批次大小。
- **不**改單輪模式的重放行為。
- **不**動 `ai_model_eval.py`(第一層評審只做 `count_parts` 數量統計,不取內容)。
- **不**使用 `presign_get`(見上方約束)。

## 錯誤處理對照表

| 情境 | 行為 |
| --- | --- |
| 物件 key + 下載成功 | `url` 換成 `data:<mime>;base64,...`,送下游(= v2.2.0 行為) |
| 物件 key + 下載失敗 / 物件不存在 | 維持物件 key → 由 `replay_messages` 剔除 + log warning,重跑照常完成 |
| data URI(未遷移的舊列) | 原樣送下游(既有行為) |
| 遠端 URL | 原樣送下游(既有行為) |
| `upload_failed` 標記 | 剔除(無內容可送) |
| `S3_STORAGE_ENABLED=false` | 不呼叫 S3,行為同現況 |
| 快照無任何物件 key 圖片 | 完全不碰 S3 |

## Acceptance

- [ ] `cd backend && uv run pytest tests/clients/test_s3_client.py tests/services/test_rerun_inline_images.py` 全綠,且測試涵蓋:
  - [ ] `get_object` 成功 / 物件不存在 / 逾時 / 錯誤轉 `S3Error` 子類
  - [ ] messages 快照含 S3 物件 key → 送下游的 payload 內該 part 為 `data:<mime>;base64,...`(以 mock S3 + respx 攔下游 payload 斷言)
  - [ ] **下游收到的內容與 v2.2.0 等價**:inline 後的 base64 decode 結果 == mock S3 物件的原始 bytes
  - [ ] 舊 data URI 快照 → **原樣送出**,未被改動
  - [ ] 遠端 URL → 原樣送出
  - [ ] `upload_failed` 標記 → 被剔除,不出現在下游 payload
  - [ ] 下載拋錯注入 → 該 part 被剔除、**重跑仍正常完成**、有 log warning
  - [ ] `S3_STORAGE_ENABLED=false` → 完全不呼叫 S3(stub 斷言未被呼叫)
  - [ ] 快照無物件 key 圖片 → 完全不碰 S3
  - [ ] **單輪模式行為未變**:仍不重放圖片(回歸測試)
- [ ] 🔴 **base64 不得回流 DB(必測)**:斷言 `RerunInput.request_content` 與寫入 DB 的任何欄位**皆不含** `;base64,`;`build_discriminator_prompt` 的輸入亦然
- [ ] 🔴 **未使用 presign**:`grep -n "presign" backend/app/services/ai_model_eval_rerun.py` **無輸出**
- [ ] **`request_snapshot.py` 未被修改**:`git diff --stat backend/app/services/request_snapshot.py` 無輸出
- [ ] 既有測試全綠:`cd backend && uv run pytest -k rerun` 與 `uv run pytest tests/clients/`
- [ ] 全庫 `uv run pytest -q` **0 failed**
- [ ] `uv run ruff check` + `uv run mypy` 對本 task 動的檔 green;全庫 ruff 維持 **62**、mypy 維持 **49**(baseline)
- [ ] log 不含 AWS 憑證(對齊 `00-overview/02-secrets.md`)

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/03-async-and-tx.md`
- `docs/Design-Base/03-backend/05-exceptions-and-logging.md`
- `docs/Design-Base/03-backend/06-clients.md`
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/03-backend/08-performance.md`
- `docs/Design-Base/90-third-party-service/00-overview.md`
- `docs/Design-Base/90-third-party-service/09-object-storage.md`
- `docs/Design-Base/90-third-party-service/50-openrouter.md`
- `docs/Design-Base/00-overview/02-secrets.md`
