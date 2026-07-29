# Tasks v2.2.1 · 圖片 / 檔案改存 S3,DB 只留物件路徑(base64 兩階段棄用)

> 狀態:**全數完成(12/12)**,待收口提交(2026-07-29;後端 540 passed / 0 failed,前端 lint + type-check + build 全綠,mypy 全庫維持 baseline 49)
> 來源:[propose-v2.2.1.md](./propose-v2.2.1.md)
> 並行:12 個 task,可並行 11 / 序列 1(同檔互鎖)/ 預估總時數:30 hr / 阻塞點:0(propose §D 全數拍板)

## 版本資訊

- 母本 propose:[propose-v2.2.1.md](./propose-v2.2.1.md)
- **一句話邊界(user 定調)**:**「改的只是平台後端 log 儲存路徑而已。」** 送給下游模型的東西、回給 SDK 呼叫端的東西一律不動;任何 task 若觸及下游 payload 或對外回應,即為越界。
- 對齊的 Design-Base 章節:
  - [`90-third-party-service/00-overview.md`](../../Design-Base/90-third-party-service/00-overview.md) § 集中位置 / § 命名 / § 錯誤轉換契約
  - [`90-third-party-service/01-client-design.md`](../../Design-Base/90-third-party-service/01-client-design.md) § timeout / retry
  - [`03-backend/03-async-and-tx.md`](../../Design-Base/03-backend/03-async-and-tx.md) § 阻塞操作 → `asyncio.to_thread`
  - [`03-backend/04-config.md`](../../Design-Base/03-backend/04-config.md) § Settings + fail-fast
  - [`03-backend/05-exceptions-and-logging.md`](../../Design-Base/03-backend/05-exceptions-and-logging.md) § 結構化 log + 機密過濾
  - [`03-backend/08-performance.md`](../../Design-Base/03-backend/08-performance.md) § event loop 阻塞
  - [`00-overview/02-secrets.md`](../../Design-Base/00-overview/02-secrets.md) § 機密 env 注入
  - [`04-databases/04-sql-safety.md`](../../Design-Base/04-databases/04-sql-safety.md) § 禁字串拼接
  - [`02-frontend/05-components.md`](../../Design-Base/02-frontend/05-components.md)、[`91-project-ui-ux.md`](../../Design-Base/02-frontend/91-project-ui-ux.md)
  - [`01-propose/07-rule-evolution.md`](../../Design-Base/01-propose/07-rule-evolution.md) § 要改規則先改 Design-Base(→ task-521)

## Definition of Done

- [ ] `docs/Design-Base/90-third-party-service/09-object-storage.md` 存在,且 `Design-Base/README.md` 與 `AGENTS.md` 兩處對照表皆已同步(521)
- [ ] `S3_STORAGE_ENABLED=true` 時,新請求的圖片 / 檔案落 S3,`usage_logs.request_content` **零 base64**(525)
- [ ] `S3_STORAGE_ENABLED=false` 時,行為與 v2.2.0 **完全一致**(525)
- [ ] **下游 payload 零變更**:`_rewrite_request` 無 diff,`respx` 攔截斷言送出 body 與 v2.2.0 逐欄相同(525)
- [ ] S3 掛掉 / 逾時 → 代理請求**照常成功**,附件記 `upload_failed` 標記 + 結構化 log(524 / 525)
- [ ] `file_data` 的 base64 **任何情況下**不入 `usage_logs.request_content`,有專門回歸測試守住(525)
- [ ] 遷移 Phase 1 跑完 DB **零變更**;Phase 2 跑完全庫 `data:...base64,` 掃描為 0 列(530 / 531)
- [ ] 用量明細頁對「S3 路徑 / 舊 data URI / upload_failed」三種形態皆正常顯示(528)
- [ ] `.env.example` 六鍵齊備、`docker-compose*.yml` 兩份注入到位(522 / 529)
- [ ] `docs/INTEGRATION.md` 與前端 `user-guide` 頁已同步(532)
- [ ] **後端測試全綠**:`cd backend && uv run pytest`(全庫,含既有測試零打壞)
- [ ] **本版新增 / 修改的檔案** lint 與型別全綠:`uv run ruff check <本版檔案清單> && uv run mypy <本版檔案清單>`
- [ ] 前端 `npm run lint && npm run type-check && npm run build`
  > ⚠️ **本條原寫作「CI green:`uv run ruff check . && uv run mypy .`」,那是不可能達成的**——全庫 `ruff check .` 有 **62** 項、`mypy .` 有 **49** 項**既有**錯誤(集中在 `alembic/versions/*` 的 `typing.Sequence`/`Union`、`app/api/v1/stats.py`、`api_key_requests.py`、`core/deps.py`、`core/response.py`、`schemas/common.py`、`services/rate_limit.py`),全數與 v2.2.1 無關。
  > 已於 2026-07-29 由 task-524 worker 回報、orchestrator 複驗確認(本版新檔在兩份輸出中皆**零命中**),故改為「本版檔案 green」。
  > 全庫清理**不屬 v2.2.1 scope**,建議另開 patch 版本處理。
  >
  > **注意**:`uv sync` **不帶 `--extra dev`** 會移除 pytest / ruff / mypy(dev 相依放在 `[project.optional-dependencies].dev`),`AGENTS.md § Build/Test/Lint` 記載的指令因此是壞的。請用 `uv sync --extra dev`。
- [ ] gitleaks 無命中;`git log --all -- .env` 為空

## 任務清單

| # | 標題 | 狀態 | 並行 | 依賴 | 影響檔案 |
| --- | --- | --- | --- | --- | --- |
| 521 | Design-Base 新增物件儲存規範檔 + 兩處對照表同步 | done | ✓ | — | `docs/Design-Base/90-third-party-service/09-object-storage.md`、`docs/Design-Base/README.md`、`AGENTS.md` |
| 522 | S3 六顆 env + Settings 欄位 + fail-fast + `.env.example` | done | ✓ | — | `backend/app/core/config.py`、`.env.example` |
| 523 | S3 client(`app/clients/s3/`)+ boto3 鎖版 + 短 timeout + presign | done | ✓ | 521, 522 | `backend/app/clients/s3/__init__.py`、`client.py`、`errors.py`、`README.md`、`backend/pyproject.toml`、`docs/Design-Base/00-overview/01-versions.md`、`backend/tests/clients/test_s3_client.py` |
| 524 | 附件落地層 `attachment.py`(deterministic key / best-effort / 失敗標記) | done | ✓ | 523 | `backend/app/services/attachment.py`、`backend/tests/services/test_attachment.py` |
| 525 | proxy 接線:快照改吃路徑、`_rewrite_request` 零 diff、串流 + 非串流 | done | ✓ | 524 | `backend/app/services/proxy.py`、`backend/tests/services/test_proxy_s3_snapshot.py` |
| 526 | `request_snapshot` 正規化層認得 S3 路徑與 `upload_failed` | done | ✓ | 524 | `backend/app/services/request_snapshot.py`、`backend/tests/services/test_request_snapshot_s3.py` |
| 527 | 用量明細 API 回吐 presigned URL(含錯誤對照表) | done | ✓ | 523, 526 | `backend/app/api/v1/usage_logs.py`、`backend/app/schemas/usage_log.py`、`backend/tests/api/test_usage_logs_presign.py` |
| 528 | 前端明細頁三形態渲染 + types | done | ✓ | 527 | `frontend/src/app/(main)/usage-logs/[uid]/page.tsx`、`frontend/src/types/api.ts` |
| 529 | docker-compose 兩份 env 注入 | done | ✓ | 522 | `docker-compose.dev.yml`、`docker-compose-prod.yml` |
| 530 | 遷移 script **Phase 1**(只上傳,DB 零變更) | done | ✓ | 523, 524 | `backend/scripts/migrate_base64_to_s3.py`、`backend/tests/services/test_migrate_base64_to_s3.py` |
| 531 | 遷移 script **Phase 2**(改寫 JSONB)+ 執行 runbook | done | ✗ | 530 | `backend/scripts/migrate_base64_to_s3.py`、`backend/tests/services/test_migrate_base64_to_s3.py`、`docs/Tasks/v2.2/runbook-v2.2.1-migration.md` |
| 532 | 對外文件同步(`INTEGRATION.md` + `user-guide` 頁) | done | ✓ | 525, 527 | `docs/INTEGRATION.md`、`frontend/src/app/(main)/user-guide/page.tsx` |

## 並行批次

- **批次 A(零依賴,立即可認領)**:**521**(Design-Base 規範檔)、**522**(env)。檔案完全不重疊,兩人可同時開工。
- **批次 B**:**523**(S3 client;待 521 + 522)、**529**(compose;待 522)。可並行。
- **批次 C**:**524**(附件落地層;待 523)。
- **批次 D**:**525**(proxy)、**526**(正規化層)、**530**(遷移 Phase 1)。三者皆待 524,彼此**檔案零重疊**,可三人同時跑。
- **批次 E**:**527**(明細 API;待 523 + 526)、**531**(遷移 Phase 2;待 530)。可並行。
- **批次 F**:**528**(前端;待 527)、**532**(文件;待 525 + 527)。可並行。

> **依賴主鏈**:規範(521)+ env(522)→ S3 client(523)→ 附件落地層(524)→ **三路分岔**:
> - 寫入端:**525**
> - 讀取端:**526 → 527 → 528**
> - 遷移:**530 → 531**
>
> **跨 area 三段鏈(後端 → 前端 → 文件)**:`527(後端 API)→ 528(前端串接)→ 532(對外文件)`。
> **無 e2e task**:Playwright 於本專案預設 disabled(`05-CI/06-e2e.md`),驗證走 pytest + vitest + 手測 case(見各 task Acceptance)。

## 檔案零重疊驗證

全部 `parallel: true` 的 task,`affected_files` 兩兩取交集為空:

- **Design-Base 兩 task 不撞**:521 動 `90-third-party-service/09-object-storage.md` + `README.md` + `AGENTS.md`;523 只動 `00-overview/01-versions.md`(boto3 鎖版)。不同檔。
- **`proxy.py` 只有 525 動**;**`request_snapshot.py` 只有 526 動**;**`usage_logs.py` 只有 527 動**。
- **前端兩 task 不撞**:528 動 `usage-logs/[uid]/page.tsx` + `types/api.ts`;532 動 `user-guide/page.tsx` + `docs/INTEGRATION.md`。
- **唯一重疊 → 已序列化**:530 與 531 同動 `backend/scripts/migrate_base64_to_s3.py` 與其測試檔 → **531 標 `parallel: false` + `depends_on: [530]`**,禁同時認領。
- **`config.py` 只有 522 動**;**compose 只有 529 動**;**`pyproject.toml` 只有 523 動**。

## 已決議(2026-07-29 user 拍板;對齊 propose §D 決議表)

worker **不必再問 user**:

- **D.3 檔案存實體**:`files`(PDF 等)實體上傳 S3,快照存 `filename` + 路徑。**推翻 v2.1.2「僅記檔名」的法務決策**,須於 commit message 與 task doc 明寫此推翻。**視為新功能,歷史紀錄不回填**。影響 524 / 525。
- **D.4 下游 payload 完全不動**:送 OpenRouter / internal 的 `image_url.url` / `file_data` 維持現行 base64 或原始 URL。**`_rewrite_request` 本版零 diff** —— 這是最好用的 review 判準,PR 若動到它就是走偏。presigned URL **只**用於管理端明細頁。影響 525 / 527。
- **D.5 上傳失敗 = best-effort**:**不擋請求**(代理照常呼叫下游、照常回應、`usage_logs` 照常寫入)、**不降級 base64**、**只記結構化 log**;該附件在快照記為 `{"type": "image_url", "upload_failed": true, "mime": ..., "bytes": N, "sha256": ...}`。**硬規則:`file_data` 的 base64 任何情況下不得寫入 `usage_logs.request_content`**。影響 523(短 timeout)/ 524 / 525 / 528。
- **D.6 遷移兩階段**:Phase 1 只上傳、DB 零變更 → **人工驗收關卡** → Phase 2 才改寫 JSONB(改寫前逐一 `head_object`)。key 為 **deterministic**(`usage_log_uid + 位置 + 內容 sha256`),因此**不需要 mapping 表 / 暫存欄位 / migration**。走獨立 script,**不**走 alembic。影響 530 / 531。
- **D.1 SDK**:`boto3` + `asyncio.to_thread`(非 `aioboto3`、非自簽 SigV4)。影響 523。
- **D.2 遠端 URL 不代抓**:輸入若已是 `http(s)://` → 原樣保留,**不**代抓落 S3(避免 SSRF 面)。影響 524。
- **D.7 遷移不動 `updated_at`**:Phase 2 的 UPDATE 須顯式保留原值;ORM 若有 `onupdate` 自動覆寫則改走 raw SQL(仍禁字串拼接)。影響 531。
- **D.8 單一 bucket + 環境前綴**:bucket 固定 `df-openrouter-dispatch-prod`,dev / test / prod 靠 `S3_KEY_PREFIX` 隔離;**本版不設 lifecycle 自動刪除**。影響 522 / 524。
- **D.9 明細頁取圖**:明細 API **回吐時直接換成 presigned URL**(不另開 302 導轉端點)。影響 527 / 528。

## 實作期發現(2026-07-29,須留檔)

### 🔴 propose §D.7 的前提是錯的:`updated_at` 由 **DB trigger** 覆寫,不是 ORM `onupdate`

propose §D.7 與 task-530 的接入點註記都假設覆寫者是 ORM 的 `onupdate`,並推論「改走 raw SQL 即可保留原值」。**這個推論擋不住實際的覆寫者**——`usage_logs` 掛著 DB 層 trigger:

```sql
-- backend/alembic/baseline_sql/V6__usage_logs.sql:29
CREATE TRIGGER trg_usage_logs_updated_at
BEFORE UPDATE ON usage_logs
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
```

raw SQL 一樣會觸發它。task-531 實測(未繞過 → `updated_at` 被推到今天;繞過 → 保留原值),解法為每個寫入交易先送 `SET LOCAL session_replication_role = replica`(交易結束自動還原、不影響其他連線;相對於 `ALTER TABLE ... DISABLE TRIGGER` 是全域生效 + ACCESS EXCLUSIVE lock)。

**需 superuser 權限;權限不足時 script 直接中止(exit 2),刻意不降級續跑**——一旦續跑,全庫 `updated_at` 會被推成執行當日且無法回頭。runbook §1-2 有前置權限檢查。

> 若 user 要回填 propose §D.7 的敘述,請自行編輯(`propose-v*.md` 由 user 撰寫,agent 不得更動)。

### 其他實作期發現

1. **`AGENTS.md § Build/Test/Lint` 的指令是壞的**:`uv sync` 不帶 `--extra dev` 會移除 pytest / ruff / mypy(dev 相依在 `[project.optional-dependencies].dev`),照著跑第二個指令即 `program not found`。根治方式為改用 uv 原生 `[dependency-groups].dev`,屬 repo-wide 建置設定變更,**不在 v2.2.1 scope**,建議另開 patch。
2. **`backend/scripts/` 無 `__init__.py`**:若測試以 `from scripts.xxx import` 匯入,同一檔會在 `mypy .` 下被認成兩個模組名,mypy 以 `Source file found twice` **中止全庫檢查**(既有 49 個錯誤會被整個遮蔽,看起來像全綠)。task-530 改用 `sys.path.append` 頂層匯入繞開;正規解法是補 `__init__.py`,但需連帶調整匯入方式,建議另案處理。
3. **歷史畸形 data URI 無法遷移**:`data:image/png;base64,@@@` 這類髒資料無內容可搬,改寫後仍符合 `LIKE '%data:%base64,%'`,**完成判準查詢不會歸零**。已列入 script 的待處理清單(`malformed_data_uri`)並於 runbook §6-1 說明如何逐筆核對。屬資料現實,非實作缺陷。
4. **AI 重跑對「messages 模式 + 含圖」紀錄的能力減損**:遷移後快照內是 S3 物件 key,`replay_messages` 一律剔除(送物件 key 給下游只是畸形 payload,換 presigned URL 需 I/O 而 `request_snapshot.py` 受純函式約束)。propose 只寫「不擴大重跑行為」,未預見「不擴大」在本設計下等同「縮減」。若要讓重跑帶得動 S3 圖片,須在 replay 鏈路注入 presign 能力,屬**架構改動**,建議另開版本。
5. **`image/svg+xml` 刻意排除在 MIME 白名單外**(task-524 決策):SVG 可夾帶 script,經 presigned URL 在明細頁直接渲染等同儲存型 XSS;落 `application/octet-stream` 讓瀏覽器下載而非渲染。前端(task-528)未加任何格式白名單把它拉回 `<img>` 路徑。
6. **單輪 `files` 的裸字串不可 presign**(task-527 決策):v2.2.0 及歷史列的 `files[i]` 是純檔名字串,而 `attachment_form` 的 fallback 會把認不出的字串判為 `object_key`;`generate_presigned_url` 只做本地簽章、不驗物件存在,照簽會產出「看起來正常、點下去 404」的 URL。故單輪 `files` 只對 Mapping 值 presign。

## 拆解註記(orchestrator)

- **scope 守門**:12 個 task 全數映自 propose `In Scope` 三個工作面,無 orphan、無超出 scope 偷渡。逐條映射:
  - 工作面一(寫入端):物件儲存能力 → 523;代理落地(單輪 / messages / files)→ 524 + 525;下游不動 → 525;presigned 保留 → 523 + 527;失敗語意 → 524 + 525;總開關 env → 522。
  - 工作面二(遷移):Phase 1 → 530;驗證關卡 + Phase 2 + 備份 + 完成判準 → 531。
  - 工作面三(讀取端與周邊):明細頁 → 527 + 528;快照正規化層 → 526;設定 / 部署 → 522 + 529;文件同步 → 532。
- **521 為何不阻塞 522**:propose 要求「先補 Design-Base 再開工」,其約束對象是**實際的 S3 串接程式碼**(命名 / 落點 / 錯誤轉換 / key 規則),故 521 設為 **523 的硬前置**。522 只動 `config.py` + `.env.example`,鍵名已由 propose §C 逐欄定死,不依賴新規範檔內容,因此可與 521 並行以縮短關鍵路徑。
- **530 / 531 刻意拆兩 task 而非一支 script 一次寫完**:兩階段中間卡的是**人工驗收關卡**(byte-for-byte 抽樣 + `pg_dump` 可還原驗證)。拆成兩個 task 讓「Phase 2 未經驗收就開跑」在流程上不可能發生 —— 531 的 Acceptance 第一條即為「提出 Phase 1 驗收證據」。這是 propose §風險明列的殘餘風險對策。
- **無 DB migration**:全版不動 schema(D.6 的 deterministic key 設計正是為了免除暫存欄位);無 alembic 產出,`alembic upgrade head` round-trip 僅作為 CI 既有防護。
- **未納入 task 的 propose 提及事項**(交還 user 決定,orchestrator 不擅自處理):
  1. propose §規範層級註記提到「回頭在 `docs/Tasks/v2.1/propose-v2.1.2.md` 變更紀錄補一行指向本版」。`propose-v*.md` 由 user 撰寫、agent 不得更動([`01-propose-format.md`](../../Design-Base/01-propose/01-propose-format.md)),故**不**開 task;推翻 v2.1.2 決策一事改由 523 / 524 / 525 的 commit message 與 task doc 記錄。若 user 要回填該行,請自行編輯。
  2. 決議表 #13「上線前 rotate AWS 金鑰 + IAM 權限收斂到單一 bucket」屬 **AWS 主控台操作**,非 repo 內可執行的程式碼變更,故不開 task;列為**上線前置**,由 user 於部署前完成。
