[//]: # (此檔為 v2.2.0 任務提案,實作前先由使用者確認範圍與設計取捨。Agent 草擬、User 拍板。)

# Propose v2.2.0 · 模型清單自動同步排程 + 申請單判決後通知系統管理員

> 此為 **proposal**(詳設母本),確認後即據以拆 `workflow/` + `tasks/`。
>
> 本版兩支獨立功能,共用「既有能力 + 排程 / 通知外掛」的路數,彼此無耦合:
> 1. **模型自動同步**:把現有「模型管理頁 → 手動同步 OpenRouter」的動作,交給排程每 3 天 00:00 自動跑一次。
> 2. **申請單判決通知**:金鑰申請單(`api_key_requests`)判決出終態後,除既有寄給申請人外,**加寄一封通知信給系統管理員**。
>
> **狀態**:**草稿,待 user 拍板**(§D 各項)。

---

## ⚠️ 版號判定註記

依 [`01-propose/05-version-bump.md`](../../Design-Base/01-propose/05-version-bump.md) 判準:

- 兩項皆為**向下相容的新增**(新排程任務、既有申請單流程加一封通知信),**無** API 路徑 / response schema / DB 不可逆變更 → 屬 **minor**,落 **v2.2.0**(user 指定)。
- 對外 API **無**任何變更;既有手動同步端點(`POST /api/v1/models/sync`)行為不變,排程走同一 service。

## ⚠️ 規範層級註記

已檢查 `docs/Design-Base/*`:兩項均落在既有規範內,**無**觸及 Design-Base 地板需先改的情形。相依規範錨點:

- 排程 / 背景任務:沿用既有 taskiq + Redis 基建(`app/tasks/broker.py`、`scheduler.py` 的 `LabelScheduleSource`);對齊 [`03-backend/03-async-and-tx.md`](../../Design-Base/03-backend/03-async-and-tx.md)、[`90-third-party-service/50-openrouter.md`](../../Design-Base/90-third-party-service/50-openrouter.md)。
- 寄信:沿用既有 M365 Graph 寄信路(`app/services/email_graph.py`),對齊 [`90-third-party-service/03-smtp.md`](../../Design-Base/90-third-party-service/03-smtp.md)(transactional 通知信,不需退訂)。
- 稽核 / 用量:同步為管理端異動,寫稽核 log(對齊 [`03-backend/92-project-permission.md § 9`](../../Design-Base/03-backend/92-project-permission.md));沿用既有 `write_audit`。
- env / secret:新增排程開關 env,對齊 [`00-overview/02-secrets.md`](../../Design-Base/00-overview/02-secrets.md)、[`03-env-layers.md`](../../Design-Base/00-overview/03-env-layers.md)。

---

## 版本目標

把兩件「今天要靠人記得做 / 靠人主動看」的事自動化,降低 admin 的例行負擔、縮短申請單處理反應時間:

1. **模型清單不再靠人手動同步**:OpenRouter 常有新模型上架 / 舊模型下架,目前只能由 admin 進「模型管理」頁按「同步」。本版讓系統**每 3 天 00:00 自動同步一次**,模型清單維持新鮮而無需人工介入(手動同步鈕保留)。
2. **申請單一有判決,系統管理員即時知道**:金鑰申請單判決出終態(自動開通 / 轉人工 / 取消等)後,**主動寄一封通知信給系統管理員**,讓管理者不必反覆巡頁,尤其「轉人工待處理」的單能第一時間被看見。

## In Scope

### 功能一 · 模型清單自動同步排程

- **新排程任務**(§B.1):新增 taskiq 排程任務,週期性呼叫**既有** `sync_models_and_credits(...)`(不改同步邏輯本體);排程節奏「每 **N** 天 00:00」,**N 由環境變數 `MODEL_SYNC_INTERVAL_DAYS` 設定**(整數,預設 3),import 時據此組 cron `0 0 */N * *`(§C / §D.1)。
- **排程進程掛載 + compose 更新**(§B.1):任務模組被 `app/tasks/scheduler.py` import(`LabelScheduleSource` 才看得到排程)、被 worker 啟動命令登記;**兩個 compose 檔都要更新**——(a) `taskiq-worker` command 追加新模組;(b) 新 env(`MODEL_SYNC_SCHEDULE_ENABLED` / `MODEL_SYNC_INTERVAL_DAYS`)在 **prod compose** 需明列於 `taskiq-worker` 與 `taskiq-scheduler` 兩者的 `environment:`(prod 無 `env_file`,dev 走 `env_file: .env` 自動可見),scheduler 尤其必要(排程 label 於 import 時讀該 env)。對齊既有 `dispatch_unevaluated` 的掛法。
- **系統 actor**(§B.1 / §D.2):排程無登入使用者,同步的稽核 actor 以「種子系統管理員」(`account = INITIAL_ADMIN_ACCOUNT`)解析後帶入;稽核 action 沿用 `sync_models_and_credits`,可由 audit log 區分是排程觸發(§D.2)。
- **節流 / 鎖相容**(§B.1):排程任務對既有 `sync_throttled`(10 分鐘)/ `sync_in_progress`(advisory lock)例外採「log 後靜默略過」,不視為失敗、不重試(§D.3)。
- **總開關 env**(§C):`MODEL_SYNC_SCHEDULE_ENABLED`,預設 `false`(對齊既有 `AI_EVAL_ENABLED` 慣例:排程類功能預設關,由環境顯式開)。

### 功能二 · 申請單判決後通知系統管理員

- **管理員收件解析**(§B.2 / §D.4):以 `UserRepository.get_by_account(INITIAL_ADMIN_ACCOUNT)` 取系統管理員(姓名慣例為「系統管理員」)之 `email`;無 email / 查無 → best-effort 略過並 log,不擋主流程。
- **通知信寄送**(§B.2):沿用既有 M365 Graph 寄信路,新增一支**收件人 / 模板可指定**的寄信函式(既有 `send_provision_email` 收件人硬綁申請人),或將其一般化;新增管理員通知信模板(`app/templates/email/`)。
- **觸發點**(§B.2 / §D.5):申請單**判決出終態後**觸發——涵蓋建立時的自動判決(`cancelled` / `manual_pending` / `agent_done`)與後續人工終態(`done` / `revoked` / 人工 `cancelled`);與既有寄申請人通知(`_notify_owner`)同層、彼此獨立(申請人信照舊,不受影響)。
- **best-effort 語意**(§B.2):管理員通知失敗**不**回滾申請單狀態、不擋既有申請人通知;結果落 log(是否落 DB 欄位見 §D.6)。
- **總開關 env**(§C):`APIREQ_ADMIN_NOTIFY_ENABLED`,預設 `false`;M365 未配置(`m365_mail_enabled=false`)時自然不寄。

## Out of Scope

- **改同步邏輯本體**:`sync_models_and_credits` 的比對 / upsert / 節流 / 白名單收斂一律不動;本版只加「排程觸發它」。
- **同步結果通知信**:排程同步的結果(新增 / 下架幾筆)本版**不**另寄通知(只落稽核 log);若日後要「同步完寄摘要給 admin」另提。
- **前端呈現排程狀態 / 下次執行時間**:模型管理頁不加「上次自動同步 / 下次排程」UI;本版純後端排程(手動同步鈕與既有 toast 不動)。
- **申請單通知內容個人化 / 多語切換**:管理員通知信用單一模板(繁中),不做 locale 切換。
- **新增申請單「類型」**:本版「申請表單」即現有金鑰申請單(`api_key_requests`),不新增其他表單種類;通知設計保留擴充餘地但不先做。
- **管理員收件人可設定化 / 多收件人**:只寄給「系統管理員」單一帳號,不做「通知群組 / 副本名單」設定頁(若日後要另提)。
- **排程節奏 UI 可調**:週期走 env,不做後台可調排程的介面。
- **換掉 taskiq / broker**:沿用現有 taskiq + Redis;RabbitMQ 遷移屬另線(見專案方向記憶),本版不碰。

## 對外承諾

- **對外 API 零變更**:SDK / chat / 管理端所有既有端點路徑與行為不變;`POST /api/v1/models/sync` 手動同步照舊。
- **行為承諾**:
  - `MODEL_SYNC_SCHEDULE_ENABLED=true` 時,系統每 3 天 00:00(§D.1 節奏)自動同步一次 OpenRouter 模型清單,結果與手動同步一致(同一 service),並寫稽核 log;預設 `false` = 現況(僅手動)。
  - 排程同步遇既有節流 / 併發鎖時靜默略過,不產生錯誤告警、不重試堆積。
  - `APIREQ_ADMIN_NOTIFY_ENABLED=true` 且 M365 已配置時,金鑰申請單每次判決出終態後,系統管理員信箱收到一封通知信;寄申請人的既有通知信不受影響。
  - 管理員通知寄送失敗不影響申請單建立 / 開通 / 既有申請人通知(best-effort)。
- **文件承諾**:`.env.example` 同步新增排程 / 通知 env;`docs/Tasks/v2.2/` 留決議紀錄。本版**未動對外 API 鏈路**,依 [`sync-user-facing-docs-on-api-change`] 判斷無使用者文件需同步(若拍板加前端呈現則另補)。

## 資料流

### 功能一(自動同步)

```
[scheduler 進程] LabelScheduleSource 依 cron「0 0 */N * *」(N=MODEL_SYNC_INTERVAL_DAYS)到點
   ▼
把 model_sync 排程 task 送進 broker(Redis)
   ▼
[worker 進程] 消費 task:
   ├─ MODEL_SYNC_SCHEDULE_ENABLED=false → return(不同步)
   ├─ 自建 SessionLocal + OpenRouterClient(沿 dispatch_* 慣例)
   ├─ 解析系統 actor(account=INITIAL_ADMIN_ACCOUNT)→ actor_user_uid / role
   ├─ sync_models_and_credits(db, client, actor=…)   ← 既有 service,不改
   │     ├─ advisory lock / 10 分鐘 throttle → 命中則 log 後靜默略過(§D.3)
   │     ├─ UPSERT models(新增 / 更新 / 下架標記)
   │     ├─ best-effort 回填餘額
   │     └─ write_audit(action="sync_models_and_credits")
   └─ db.commit()
```

### 功能二(申請單判決通知管理員)

```
[POST /api/v1/api-key-requests](建立) 或 process / cancel / revoke
   ▼
route → (AI 判決) → 決定 status 終態(cancelled / manual_pending / agent_done / done / revoked)
   ▼
既有:_notify_owner(...)  → 寄申請人通知(不變)
   ▼
新增:notify_admin_on_verdict(db, row, …)(best-effort,與申請人通知獨立):
   ├─ APIREQ_ADMIN_NOTIFY_ENABLED=false / M365 未配置 → 略過
   ├─ 解析系統管理員 email(get_by_account(INITIAL_ADMIN_ACCOUNT).email);無 → log 略過
   ├─ render_email(admin 通知模板;含 申請人 / 部門 / 判決 status / reason)
   ├─ send_mail(to=admin_email, …)   ← M365 Graph,收件人可指定
   └─ 成敗落 log(§D.6 決定是否落 DB 欄位);失敗不回滾、不擋主流程
```

## 後端(§B)

### B.1 模型自動同步排程

- **新任務模組**:`backend/app/tasks/model_sync.py`(獨立於 `ai_model_eval.py`,語意分離)。
  - 排程任務 `scheduled_sync_models`,cron 由 env 天數組出:import 時 `_INTERVAL_DAYS = coerce_int_env("MODEL_SYNC_INTERVAL_DAYS", os.environ.get(...), 3)` → `@broker.task(schedule=[{"cron": f"0 0 */{_INTERVAL_DAYS} * *"}])`(逐字沿 `ai_model_eval.py` 的 `_BEAT_INTERVAL` import 時定型慣例);函式體內走 `get_settings()`、延遲 import `SessionLocal`,保 CI-importability。
  - 任務體:enable flag 短路 → 自建 `SessionLocal` + `OpenRouterClient` → 解析系統 actor → 呼叫既有 `sync_models_and_credits(...)` → `commit`。對 `AppError("sync_throttled" / "sync_in_progress")` 攔截為 log 後 return(不 raise、不觸發 taskiq 重試,§D.3)。
- **掛載**:
  - `backend/app/tasks/scheduler.py` 追加 `import app.tasks.model_sync  # noqa: F401`(scheduler 才看得到此排程)。
  - `docker-compose.dev.yml` 與 `docker-compose-prod.yml` 的 **taskiq-worker** 啟動命令追加模組名 `app.tasks.model_sync`(worker 才註冊此 task)。
- **系統 actor**:任務內以 `UserRepository(db).get_by_account(settings.INITIAL_ADMIN_ACCOUNT)` 取 admin user,帶 `actor_user_uid=admin.user_uid` / `actor_role="admin"` 進 `sync_models_and_credits`;查無 admin(理論上種子必存在)→ log 後略過本次(§D.2)。
- **不動**:`sync_models_and_credits`、`ModelRepository`、`POST /models/sync` 端點、前端 `SyncButton` 全數不改。

### B.2 申請單判決通知系統管理員

- **落點**:`backend/app/services/email_graph.py`(寄信)、`backend/app/services/email_render.py` + `backend/app/templates/email/`(模板)、`backend/app/api/v1/api_key_requests.py`(觸發)、`backend/app/repositories/user.py`(既有 `get_by_account`,不改)。
- **寄信函式**:既有 `send_provision_email` 收件人 / 模板硬綁申請人開通信;新增 `send_admin_notify_email(*, to_email, …)` 或將 Graph 寄送底層抽為「收件人 + subject + html/text 可指定」的內部函式,`send_provision_email` 與新函式共用(§D.7 落點取捨)。沿 M365 best-effort 語意:未配置 → `EmailResult(ok=False, error="m365_not_configured")`,**不 raise**。
- **模板**:`backend/app/templates/email/admin_apireq_verdict.{html,txt}`,`render_email` 渲染;內容含申請人姓名 / 部門 / 專案、判決 `status`(以中文語意呈現)、`agent_decision.reason`(若有)、申請單識別(對外 uid,**禁**露內部 pid / 一次性密鑰);沿 base 模板樣式。
- **觸發整合**:於 `api_key_requests.py` 各終態落點呼叫(§D.5 決定涵蓋範圍);建議抽 `notify_admin_on_verdict(db, row, actor, ip)` helper,與既有 `_notify_owner` 平行呼叫、各自 try/except best-effort,互不連坐。
- **收件解析**:`get_by_account(INITIAL_ADMIN_ACCOUNT).email`;`email` 為 nullable → 無值視同「無管理員信箱」,log 後略過。

## 設定(環境變數)(§C)

| env | 預設 | 說明 |
| --- | --- | --- |
| `MODEL_SYNC_SCHEDULE_ENABLED` | `false` | 模型自動同步排程總開關;`false` = 僅手動同步(現況) |
| `MODEL_SYNC_INTERVAL_DAYS` | `3` | 自動同步間隔**天數**(整數,可設定);排程於「每 N 天的 00:00」觸發,import 時據此組 cron `0 0 */N * *`。cron `*/N` 於月底邊界會重置,非嚴格滾動(§D.1) |
| `APIREQ_ADMIN_NOTIFY_ENABLED` | `false` | 申請單判決後通知系統管理員總開關;M365 未配置時自然不寄 |

- 皆走既有 `coerce_bool_env` / `coerce_int_env` 容錯;`.env.example` 同步新增。M365 相關 env(`M365_*`)沿用既有,不新增。
- **compose 注入**:dev(`docker-compose.dev.yml`)的 taskiq 服務走 `env_file: .env`,新 env 自動可見;prod(`docker-compose-prod.yml`)無 `env_file`、走顯式 `environment:` mapping,故 `MODEL_SYNC_SCHEDULE_ENABLED` / `MODEL_SYNC_INTERVAL_DAYS` 須**手動加進 `taskiq-worker` 與 `taskiq-scheduler` 兩者**的 `environment:`(排程 label 於 import 時讀,scheduler 進程一定要拿得到);`APIREQ_ADMIN_NOTIFY_ENABLED` 為 API 進程使用,加進 backend 服務 env。
- **無 DB migration**(兩功能皆無新表 / 新欄;§D.6 若拍板「落 DB 記錄管理員通知結果」才需一支加欄 migration)。

## D. 設計取捨(待 user 拍板)

### D.1 排程節奏 — 建議「env 天數 `MODEL_SYNC_INTERVAL_DAYS`(預設 3)組 cron `0 0 */N * *`」

- user 指定「每 N 天的 00:00 自動同步,N 可設定」。以整數 env `MODEL_SYNC_INTERVAL_DAYS` 於 import 時組出 cron `0 0 */{N} * *`——N 天為乾淨可調的整數、且鎖 00:00 觸發。
- **已知取捨**:cron `*/N` 於每月重置(每月 N、2N、3N… 號 00:00 觸發),**月底邊界會重置**,跨月最長間隔可能 > N 天(例 N=3 時月底 30→次月 3 號約 4 天)。屬語意可接受的近似。
- 替代案:(a) 純 `{"interval": N*86400}`(嚴格滾動 N 天,但觸發時刻隨進程啟動漂移,**不保證** 00:00);(b) DB 存「上次同步時間」游標,每日 00:00 觸發但僅在「距上次 ≥ N 天」才真跑(嚴格 N 天 + 固定 00:00,需一支游標欄 + migration)。
- **✅ user 定案(2026-07-16):採 cron 版**(N 可調、鎖 00:00、零 DB,接受月底近似)。

### D.2 排程同步的稽核 actor — 建議「種子系統管理員」

- `sync_models_and_credits` 需 `actor_user_uid` / `actor_role` 寫稽核;排程無登入使用者。建議解析 `account=INITIAL_ADMIN_ACCOUNT` 的 admin user 當 actor(role=admin),稽核可讀。
- 排程 vs 人工區分:建議稽核 `extra` 加 `trigger="scheduler"` 標記(既有手動不帶此鍵),audit log 可過濾;或沿用同 action 不區分(較省,但事後難分辨誰觸發)。**待拍板**:是否加 `trigger` 標記。
- 替代案:引入「系統 actor」哨兵 UID(不綁真人)——語意更純但需動 `write_audit` / actor 解析,重量級,不建議。

### D.3 排程遇節流 / 鎖 — 建議「log 後靜默略過」

- 排程每 3 天一次,幾乎不會撞 10 分鐘 throttle;但若 admin 剛好在排程前手動同步過,排程會收 `sync_throttled`(425)。建議任務攔截 `sync_throttled` / `sync_in_progress` → log(info)後 return,**不** raise(避免 taskiq 重試堆積、不產生錯誤告警)。
- 替代案:重試(對排程場景無意義,反而堆積);或放任 raise(污染錯誤 log)。**建議靜默略過。**

### D.4 管理員收件解析 — 建議「以 account 解析,姓名為慣例」

- user 描述為「姓名 = 系統管理員的信箱」。實作上「姓名(`username`)」非唯一鍵、且由 `INITIAL_ADMIN_USERNAME` 種子而來(慣例值即「系統管理員」);**穩健作法是以 `account = INITIAL_ADMIN_ACCOUNT` 解析**該帳號再讀 `email`,其 `username` 慣例即「系統管理員」。
- 替代案:真的以 `username == "系統管理員"` 查(可能多筆 / 改名即失效,不建議);或新增 env `APIREQ_ADMIN_NOTIFY_EMAIL` 直接指定收件信箱(最白箱、與帳號解耦,但多一個 env 要維護)。**✅ user 定案(2026-07-16):以 `account=INITIAL_ADMIN_ACCOUNT` 解析**。

### D.5 通知觸發範圍 — 建議「所有終態轉換都通知」

- 「判決完狀態後」最小語意 = 建立時的自動判決(`cancelled` / `manual_pending` / `agent_done`)。但申請單後續還有人工 `done` / `revoke` / `cancel` 終態。
- 建議**所有終態轉換都寄**(admin 掌握全生命週期);若嫌信量大,可收斂為「僅 `manual_pending`(需人工介入者)+ 建立時自動終態」。**✅ user 定案(2026-07-16):所有終態轉換都寄**。

### D.6 管理員通知結果是否落 DB — 建議「僅 log,不落 DB」

- 既有申請人通知有 `notified_at` / `notify_error` 欄記錄結果。管理員通知建議**僅落結構化 log**(不加 DB 欄 → 零 migration、最輕);admin 通知屬「知會」性質,失敗容忍度高。
- 替代案:加 `admin_notified_at` / `admin_notify_error` 欄(可查、可補寄,但需 migration + 端點回吐)。**✅ user 定案(2026-07-16):僅 log,不落 DB**(維持零 migration;若日後要補寄能力再升級)。

### D.7 寄信函式落點 — 建議「抽共用 Graph 底層 + 兩個語意函式」

- 既有 `send_provision_email` 收件人 / 模板硬綁。建議把 M365 token 取得 + `sendMail` POST 抽為內部 `_send_mail(*, to, subject, html, text)`,`send_provision_email` 與新 `send_admin_notify_email` 各自組模板後共用底層。
- 替代案:直接複製一份寄送邏輯(重複、日後 token / 錯誤處理要改兩處,不建議)。**建議抽共用底層。**

## 風險與相依

- **排程掛載遺漏(功能一)**:taskiq 排程需**三處**同步才生效——task 帶 `schedule` label、`scheduler.py` import 該模組、worker 啟動命令登記該模組。漏任一 → 排程靜默不觸發。驗收須實際確認 scheduler 有送、worker 有收(§驗收)。
- **cron 月底邊界(功能一)**:`*/3` 於每月重置,跨月最長間隔約 4 天(§D.1);若 user 要求嚴格 72h 需改方案。上線後首次觸發時刻依當月日期,需在驗收時說明。
- **系統 actor 相依(功能一)**:排程同步的稽核 actor 依賴種子 admin 存在;種子未跑 / admin 帳號被改 account → 解析失敗。以 `INITIAL_ADMIN_ACCOUNT` 為準(種子必建),查無則 log 略過本次同步。
- **同步阻塞 worker(功能一)**:`sync_models_and_credits` 為較重的 I/O(拉 OpenRouter /models + 逐 key 回填餘額),與 AI 評審 task 共用 worker;3 天一次、單次數秒~數十秒,對評審派發影響有限,但需確認不與同步 advisory lock 互卡(排程遇鎖靜默略過已涵蓋)。
- **M365 相依(功能二)**:管理員通知走與開通信同一 M365 Graph app-only token;M365 未配置 → 兩者都不寄(既有行為),不新增失敗面。best-effort 不擋主流程。
- **收件人為 PII(功能二)**:管理員 email 為 PII,**禁**入 log 明文 / commit;通知信內容**禁**含一次性密鑰(`provisioned_secrets`)、內部 pid。沿既有 log 機密過濾。
- **信量(功能二)**:若拍板「全終態都寄」,高申請量時管理員收信頻繁;env 可關、且可依 §D.5 收斂觸發範圍。
- **無 migration**:兩功能預設皆不動 DB(§D.6 若落 DB 才需一支加欄 migration);排程 / 通知皆可安全上線、可 env 關閉回退現況。

## 驗收標準

### 功能一(自動同步排程)

- `MODEL_SYNC_SCHEDULE_ENABLED=true`:scheduler 依 cron 到點送 task、worker 消費並實際呼叫 `sync_models_and_credits`,`models` 表依 OpenRouter 回應 upsert(新增 / 更新 / 下架標記),稽核 log 有 `sync_models_and_credits` 一筆(actor = 系統管理員,§D.2 若加 `trigger` 標記可辨識為排程)。
- `MODEL_SYNC_SCHEDULE_ENABLED=false`:排程 task 消費即 return,不同步(手動同步不受影響)。
- 排程觸發時若遇 throttle / lock → log(info)後略過,**無** error log、**無** taskiq 重試堆積。
- 手動同步鈕與既有 toast / 10 分鐘 cooldown 行為完全不變。
- 單元 / 整合測試:enable 開關短路、系統 actor 解析、throttle/lock 攔截靜默略過;掛載驗證(scheduler import + worker command 含新模組)以文件 / 啟動檢查涵蓋。

### 功能二(申請單判決通知管理員)

- `APIREQ_ADMIN_NOTIFY_ENABLED=true` 且 M365 配置:建立申請單判出終態(`agent_done` / `manual_pending` / `cancelled`)後,系統管理員信箱收到一封通知信,內容含申請人 / 部門 / 判決 status / reason,**不含**一次性密鑰 / 內部 pid;寄申請人的既有通知信照常寄出(兩者獨立)。
- 依 §D.5 拍板範圍,人工 `done` / `revoke` / `cancel` 終態亦寄(若採全終態)。
- 管理員 email 查無 / M365 未配置 / 寄送失敗 → 主流程(申請單建立 / 開通 / 申請人通知)完全不受影響,失敗落 log。
- `APIREQ_ADMIN_NOTIFY_ENABLED=false` → 行為與現況完全一致(不寄管理員信)。
- 單元測試:收件解析(account → email;無 email 略過)、開關關閉直通、寄送失敗 best-effort 不拋、模板不含敏感欄位。

## 設計取捨 / 決議

| # | 議題 | Agent 建議 | 狀態 |
| --- | --- | --- | --- |
| 1 | 範圍 = 模型自動同步排程 + 申請單判決通知管理員(兩獨立功能) | — | ✅ user 指定(2026-07-16) |
| 2 | 排程精確度:env 天數 `MODEL_SYNC_INTERVAL_DAYS`(預設 3)組 cron `0 0 */N * *`,接受月底近似 | cron 版 | ✅ user 定案(2026-07-16) |
| 3 | 排程稽核 actor = 種子系統管理員 + `trigger="scheduler"` 標記 | 採建議 | ✅ 實作預設(未反對即採) |
| 4 | 排程遇 throttle / lock → log 後靜默略過(不重試) | 採建議 | ✅ 實作預設(未反對即採) |
| 5 | 管理員收件以 `account=INITIAL_ADMIN_ACCOUNT` 解析(姓名慣例即系統管理員) | account 解析 | ✅ user 定案(2026-07-16) |
| 6 | 通知觸發範圍:所有終態轉換都寄(含建立自動判決 + 人工 done/revoke/cancel) | 全終態 | ✅ user 定案(2026-07-16) |
| 7 | 管理員通知結果僅 log,不落 DB(零 migration) | 僅 log | ✅ user 定案(2026-07-16) |
| 8 | 寄信抽共用 Graph 底層 + 兩語意函式 | 採建議 | ✅ 實作預設(未反對即採) |

## 變更紀錄

| 日期 | 改動 | 理由 |
| --- | --- | --- |
| 2026-07-14 | 初版草擬:AI 評審(第一層模型推薦)成本優化(截斷 / 重排+快取 / 白名單瘦身 / 去重 + 量測) | 原 v2.2.0 方向 |
| 2026-07-16 | **全面改向**:v2.2.0 目標改為「模型清單自動同步排程」+「申請單判決後通知系統管理員」兩支獨立功能;原 AI 評審成本優化方向整體移除 | user 指示改向(2026-07-16):❶ 每 3 天 00:00 自動同步 OpenRouter 模型;❷ 申請表單判決終態後加寄通知信給系統管理員 |
| 2026-07-16 | 同步間隔改為可設定整數 env `MODEL_SYNC_INTERVAL_DAYS`(預設 3),import 時組 cron `0 0 */N * *`;明列 dev(`env_file`)/ prod(顯式 `environment:`,worker+scheduler 皆需)compose 注入差異 | user 指示:每 N 天寫進環境變數、N 可設定,docker-compose 一併更新 |
| 2026-07-16 | §D 拍板:D.1 cron 版(接受月底近似)/ D.4 account 解析收件 / D.5 全終態都寄 / D.6 僅 log 不落 DB;D.2/D.3/D.7 採實作預設 | user 定案(2026-07-16 AskUserQuestion) |
