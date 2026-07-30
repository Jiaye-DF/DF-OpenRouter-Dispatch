---
id: task-531
title: 遷移 script Phase 2(改寫 JSONB)+ 執行 runbook
status: pending
parallel: false
depends_on: [task-530]
affected_files:
  - backend/scripts/migrate_base64_to_s3.py
  - backend/tests/services/test_migrate_base64_to_s3.py
  - docs/Tasks/v2.2/runbook-v2.2.1-migration.md
estimated_hours: 3
---

> **已改為單一流程(2026-07-30)**:原本的兩階段(530 上傳 / 531 改寫)已合併,mode 參數
> 全部移除,直接 `python -m scripts.migrate_base64_to_s3` 就是「掃描 → 上傳 → 就地改寫」。
> 「上傳與改寫之間卡人工驗收」這道關卡由「**上傳成功才改寫該值、同列有任何附件沒搬成功就
> 整列不改**」接手。本文件保留原始拆解內容作為歷史紀錄,實際執行請以
> [`runbook-v2.2.1-migration.md`](../runbook-v2.2.1-migration.md) 為準。

## 目標

在 Phase 1 上傳完成**且通過人工驗收**後,把 `usage_logs.request_content` 內的 base64 改寫成 S3 路徑 —— base64 於此刻才退場。**這是本版唯一不可逆的操作**(propose §D.6 Phase 2)。

> **`parallel: false`**:本 task 與 530 同動 `migrate_base64_to_s3.py` 與其測試檔,**禁**同時認領。

## ⚠️ 前置驗收(開跑正式遷移前必須完成,證據附在 PR / runbook)

1. Phase 1 報表:應上傳數 == S3 實際物件數。
2. 抽樣 **≥ 10 筆** byte-for-byte 比對(涵蓋單輪 / messages、單圖 / 多圖):S3 物件 == 原 base64 decode 結果。
3. 抽樣以 presigned URL 實際開得起來,圖片正常。
4. `pg_dump` 備份完成,且**實際驗證過可還原**(不是「有跑過 dump」而已)。

> 這四條是 propose §風險明列的三層保護。**跳過任一條,保護等於沒有。**

## 範圍(只做這些)

### 1. `--phase rewrite`

- 重掃同一 WHERE 條件,以 `pid` 游標分批,**每批一個 transaction**。
- 對每個 data URI:**重算**出同一把 legacy key(import 524 的函式,不重新實作)→ `head_object` 確認物件存在 → **才**把該值改寫成路徑。
- **物件不存在 → 跳過該列**,記入待處理清單,**絕不**寫出指向不存在物件的路徑(安全網)。
- 冪等:已是路徑者跳過;`--dry-run` 只報統計不寫入。
- **不動 `updated_at`**(D.7):UPDATE 須顯式保留原值;若 ORM 有 `onupdate` 自動覆寫則改走 raw SQL(仍**禁**字串拼接,用 `text(...).bindparams(...)`)。
- **只動附件**:`text` / `messages` 文字 / `tools` / 生成參數 / 記帳欄位一律不改。
- 失敗列不擋整批;中斷後重跑只處理未完成列。

### 2. `docs/Tasks/v2.2/runbook-v2.2.1-migration.md`

可照著執行的操作手冊,至少含:

- 前置檢查清單(上述四條驗收 + `S3_STORAGE_ENABLED` 狀態確認)
- `pg_dump` 備份與**還原驗證**的具體指令
- Phase 1 → 驗收 → Phase 2 的完整指令序列(含 `--dry-run` 先跑)
- 中斷 / 失敗時的處置與重跑方式
- 回退程序(**只能靠備份還原**,無其他退路 —— 須在 runbook 開頭以警語標明)
- 完成判準與收尾驗證指令

## 不做

- **不**改 Phase 1 的上傳邏輯(530 已完成;本 task 只新增 rewrite phase)。
- **不**加暫存欄位 / 新表 / migration(deterministic key 設計正是為了免除這些;且本專案 `AGENTS.md § 毀滅性操作禁止` 禁 `DROP COLUMN`,加了就沒有乾淨退場路徑)。
- **不**在 script 內執行 `pg_dump`(備份是人工前置,寫在 runbook)。

## Acceptance

- [ ] `cd backend && uv run pytest tests/services/test_migrate_base64_to_s3.py` 全綠,且**新增**測試涵蓋:
  - [ ] rewrite 後,該列 `request_content` 內無 `data:` base64,值為 S3 路徑
  - [ ] **安全網(必測)**:刻意讓 `head_object` 回 `False` → 該列**未被改寫**,並列入待處理清單
  - [ ] **`updated_at` 未變(必測)**:rewrite 前後比對該欄位完全相同
  - [ ] **其他欄位未變(必測)**:`text` / `tools` / 生成參數 / 記帳欄位逐欄比對無差異
  - [ ] 冪等:連跑兩次 → 第二次處理 0 列
  - [ ] 中斷後重跑:已改寫列不重做、未改寫列補完
  - [ ] `--dry-run` 不寫入
  - [ ] 兩種快照形狀(單輪 / messages)皆正確改寫
- [ ] **完成判準(對測試 DB 執行後)**:`SELECT count(*) FROM usage_logs WHERE request_content::text LIKE '%data:%base64,%'` 回 **0**
- [ ] `[ -f docs/Tasks/v2.2/runbook-v2.2.1-migration.md ]` 為真,且含全部六個章節:`for k in "前置檢查" "pg_dump" "dry-run" "重跑" "回退" "完成判準"; do grep -q "$k" docs/Tasks/v2.2/runbook-v2.2.1-migration.md || echo "MISSING: $k"; done` **無任何輸出**
- [ ] **未複製 key 邏輯**:`grep -q "from app.services.attachment import" backend/scripts/migrate_base64_to_s3.py` 為真
- [ ] **禁字串拼接 SQL**:`grep -nE "f\"(SELECT|UPDATE)|\+ *\"(SELECT|UPDATE)" backend/scripts/migrate_base64_to_s3.py` **無輸出**
- [ ] `cd backend && uv run ruff check scripts/migrate_base64_to_s3.py && uv run mypy scripts/migrate_base64_to_s3.py` 全綠
- [ ] PR 描述附上 Phase 1 四條前置驗收的**實際證據**(報表數字 / 抽樣比對結果 / 備份還原確認)

## 必讀檔(Just-in-time)

- `docs/Design-Base/04-databases/00-overview.md`
- `docs/Design-Base/04-databases/04-sql-safety.md`
- `docs/Design-Base/04-databases/06-timezone.md`
- `docs/Design-Base/04-databases/07-connection.md`
- `docs/Design-Base/04-databases/08-alembic.md`
- `docs/Design-Base/03-backend/03-async-and-tx.md`
- `docs/Design-Base/03-backend/05-exceptions-and-logging.md`
- `docs/Design-Base/06-Coolify-CD/06-rollback.md`(回退章節寫法)
- `AGENTS.md`(§ 毀滅性操作禁止)
