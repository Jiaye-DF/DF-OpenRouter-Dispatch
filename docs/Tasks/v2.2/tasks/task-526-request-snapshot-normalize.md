---
id: task-526
title: request_snapshot 正規化層認得 S3 路徑與 upload_failed
status: pending
parallel: true
depends_on: [task-524]
affected_files:
  - backend/app/services/request_snapshot.py
  - backend/tests/services/test_request_snapshot_s3.py
estimated_hours: 2
---

## 目標

`request_content` 自本版起出現**第三種附件形態**(S3 路徑 / `upload_failed` 標記)。所有讀取端都經 `request_snapshot.py` 正規化,本 task 讓該層認得新形態,避免重蹈 v2.1.2 的覆轍 —— 當時 messages 形狀沒被正規化,導致 AI 評估與重跑把紀錄當成「空輸入」處理,**判分全失效且不報錯**(見該檔檔頭)。

## 範圍(只做這些)

- 新增附件值判別:`data URI` / `S3 物件路徑` / `遠端 http(s) URL` / `upload_failed 標記` 四態。
- `messages_of` / `as_parts` / `count_parts` 對新形態的處理:
  - S3 路徑 → 視為**有內容的 image part**(統計圖片數量時要算進去)。
  - `upload_failed` 標記 → 視為**有這個附件但內容不可用**(數量算進去、內容不可取)。
  - 兩者皆**不得**被誤判為「無附件」或被 `as_parts` 濾掉。
- `text_of` / `input_text_of` 行為不變(文字路徑不受附件形態影響),但須有回歸測試證明。
- `replay_messages`:**本版不擴大重跑行為**(單輪仍不重放圖片、messages 仍剔除 file part);只確保新形態不會讓它產出畸形 payload 或誤判為空。

## 不做

- **不**在此層做 presign(那是 527 的事,且本層規範為「純函式、無 I/O、無 DB」—— **禁**在此 import S3 client 或任何 service,見該檔檔頭)。
- **不**改 AI 評估 / 重跑的判分邏輯與 prompt(propose Out of Scope)。
- **不**動 `proxy.py`(525 的事)。

## Acceptance

- [ ] `cd backend && uv run pytest tests/services/test_request_snapshot_s3.py` 全綠,且測試涵蓋:
  - [ ] 單輪快照 `images` 為 S3 路徑 → `messages_of` 產出一則 user 訊息且含 1 個 image part
  - [ ] messages 快照 `image_url.url` 為 S3 路徑 → 原樣保留、不被濾掉
  - [ ] `upload_failed` 標記 → `count_parts(..., "image_url")` **仍計數為 1**(附件存在,只是內容不可用)
  - [ ] 舊 data URI 形狀行為**完全不變**(遷移期新舊並存)
  - [ ] `input_text_of` / `text_of` 對三種附件形態皆回相同文字
  - [ ] `replay_messages` 對新形態不產出畸形 payload、不回空
- [ ] **純函式約束仍成立**:`grep -n "^from app\.\|^import app\." backend/app/services/request_snapshot.py` **無任何輸出**(未 import 任何 app 內模組,無循環相依、無 I/O)
- [ ] 既有測試全綠:`cd backend && uv run pytest tests/services/test_request_snapshot.py`
- [ ] `cd backend && uv run ruff check app/services/request_snapshot.py && uv run mypy app/services/request_snapshot.py` 全綠

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/03-backend/90-project-backend.md`
- `docs/Design-Base/90-third-party-service/50-openrouter.md`(§ 6.1 content parts 白名單)
