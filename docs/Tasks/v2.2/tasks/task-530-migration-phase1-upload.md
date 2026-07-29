---
id: task-530
title: 遷移 script Phase 1(只上傳,DB 零變更)
status: pending
parallel: true
depends_on: [task-523, task-524]
affected_files:
  - backend/scripts/migrate_base64_to_s3.py
  - backend/tests/services/test_migrate_base64_to_s3.py
estimated_hours: 3
---

## 目標

把 `usage_logs.request_content` 內既有的 base64 圖片全數上傳 S3,**但一個 byte 都不改 DB**。跑完後系統行為完全等同現況,隨時可中止、零副作用(propose §D.6 Phase 1,✅ user 定案:「base64 先暫時不動,等確定移轉成功後再棄用」)。

## 範圍(只做這些)

- 新增 `backend/scripts/migrate_base64_to_s3.py`,CLI 參數:`--phase upload`(本 task 只實作這個 phase)、`--batch-size` / `--limit` / `--dry-run`。
- 掃描:`SELECT pid, uid, request_content FROM usage_logs WHERE request_content::text LIKE '%data:%base64,%'`,以 `pid` 游標分批。**禁字串拼接 SQL**(對齊 [`04-databases/04-sql-safety.md`](../../../Design-Base/04-databases/04-sql-safety.md),用 `text(...).bindparams(...)`)。
- 逐列走訪兩種快照形狀:單輪 `images[]` + messages 模式 `messages[].content[].image_url.url`。
- 對每個 data URI:decode → **以 524 匯出的 key 生成函式**算出 legacy key(`<prefix>/legacy/<usage_log_uid>/<idx>-<sha256[:16]>.<ext>`)→ `head_object` 已存在則跳過、否則 `put_object`。
  **禁**在本 script 內複製一份 key 生成邏輯 —— 必須 import 524 的函式,否則 Phase 2 重算會對不上。
- **DB 唯讀**:本 phase **不得**出現任何 `UPDATE` / `INSERT` / `DELETE`。
- 報表輸出:應上傳 N / 實際上傳 M / 已存在 K / 失敗清單(含 `pid`)。
- 失敗列不擋整批:記錄後繼續下一列,結束時彙總。
- 併發:預設單執行緒循序(安全優先);若加小幅併發須可由參數關閉。

## 不做

- **不**改寫 JSONB(531 的事)。
- **不**走 alembic(propose §D.6:migration 內做大量外部網路 I/O 不可控,且會綁架 CI 的 `alembic upgrade head` round-trip)。
- **不**動 `updated_at`(本 phase 根本不寫 DB)。

## Acceptance

- [ ] `[ -f backend/scripts/migrate_base64_to_s3.py ]` 為真
- [ ] `cd backend && uv run pytest tests/services/test_migrate_base64_to_s3.py` 全綠,且測試涵蓋:
  - [ ] **DB 零變更(必測)**:對測試 DB 跑完 `--phase upload` 後,所有 `usage_logs` 列的 `request_content` 與 `updated_at` **與跑之前完全相同**
  - [ ] `--dry-run` **不上傳、不寫入**,但報表數字正確(以 mock 斷言 `put_object` 未被呼叫)
  - [ ] 冪等:連跑兩次 → 第二次 `put_object` 呼叫數為 0(全部 `head_object` 命中)
  - [ ] 兩種快照形狀(單輪 / messages)皆被掃到並上傳
  - [ ] 單列上傳失敗 → 記入失敗清單、**不中斷**、其餘列照跑
  - [ ] key 與 524 的函式一致:斷言 script 產出的 key == 直接呼叫 524 函式的結果
- [ ] **未複製 key 邏輯**:`grep -q "from app.services.attachment import" backend/scripts/migrate_base64_to_s3.py` 為真
- [ ] **無寫入語句**:`grep -niE "\b(update|insert|delete)\b" backend/scripts/migrate_base64_to_s3.py` 僅出現在註解 / 字串說明中(無實際執行語句;以 code review 佐證並於 PR 描述說明)
- [ ] `cd backend && uv run ruff check scripts/migrate_base64_to_s3.py && uv run mypy scripts/migrate_base64_to_s3.py` 全綠
- [ ] `cd backend && uv run python scripts/migrate_base64_to_s3.py --phase upload --dry-run --limit 1` 可執行且印出報表(對本機 dev DB;無資料時印出 0 列亦算通過)

## 必讀檔(Just-in-time)

- `docs/Design-Base/04-databases/00-overview.md`
- `docs/Design-Base/04-databases/04-sql-safety.md`
- `docs/Design-Base/04-databases/07-connection.md`
- `docs/Design-Base/04-databases/09-indexes-and-perf.md`
- `docs/Design-Base/04-databases/08-alembic.md`(理解「為何本遷移不走 alembic」)
- `docs/Design-Base/03-backend/03-async-and-tx.md`
- `docs/Design-Base/03-backend/05-exceptions-and-logging.md`
- `docs/Design-Base/90-third-party-service/09-object-storage.md`(task-521 建立)
