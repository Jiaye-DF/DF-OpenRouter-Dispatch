# 專案掃描報告 — Issue-Scan-Project-260716075637

> 掃描時間:2026-07-16 07:56:37 (UTC+8)
> 範圍焦點:**v2.2.0 變更**(task-501~503 / 511~512:模型清單自動同步排程 + 申請單判決後通知系統管理員)+ 通用規則回歸
> 基準報告:[Issue-Scan-Project-260707050320.md](./Issue-Scan-Project-260707050320.md)(v2.1.1)
> 掃描者:資深工程師(非 linter)。規則為地板;AD 寧空勿湊。

---

## 0. 與前次差異

以 `R-xxx`/`AD-xxx` ID + 路徑為 key:

| 狀態 | 項目 | 嚴重度 | 說明 |
| --- | --- | --- | --- |
| ✅ 已解決 | AD-001 `resolve_filters` 空部門漏洞(`_scope_filters.py`) | 🟠→✅ | 前次 High,已修正並記錄於 `docs/Tasks/v2.1/fixed.md §10`;v2.2.0 未觸及該路徑,狀態維持已修。 |
| 🆕 新增 | R-ENV-004 本機 `.env` 未同步三顆新 key(`.env.example` 已加) | 🟡 | v2.2.0 新增 `MODEL_SYNC_SCHEDULE_ENABLED` / `MODEL_SYNC_INTERVAL_DAYS` / `APIREQ_ADMIN_NOTIFY_ENABLED`;三者皆有 Settings 預設值,**功能不受影響**,但違反 CLAUDE.md 開發前必檢查(`.env` 應含 example 所有 key)。詳見第 3 章。 |
| ⏸ 既有債維持 | mypy `list` 方法名遮蔽(`fixed.md §1/§2/§4/§7`) | 🟠→記錄 | v2.2.0 新碼未觸及該 repository,無新增連坐;既有債仍未清,已達升規門檻(第 4 次)。 |
| ⏸ 既有債維持 | 共用 `frontend/src/lib/utils/datetime.ts` 未建(`fixed.md §5/§8`) | 🟡→記錄 | v2.2.0 無前端變更,不觸及;既有債維持。 |
| ⏸ 既有債維持 | `api_key_requests.py:240` `validate_fields` 型別(`Department \| None`) | 🔵→記錄 | 追溯 v1.9.1(commit `e94f661`),**非 v2.2.0 引入**;task-512 新碼在 `--follow-imports=silent` 下零新錯。 |
| ✅ 沿用通過 | R-BE-003 ApiResponse 殼 | 🟠 | task-512 未改 response schema;既有端點外殼不變。 |
| ✅ 沿用通過 | R-SEC-008 權限後端強制 | 🔴 | 排程 actor / 管理員解析皆於後端;無前端權限判斷引入。 |

**本次結論:v2.2.0 五個 task 新碼品質高,無 🔴、無 🟠。唯一 🆕 為 R-ENV-004(本機 `.env` 未補三顆新 key,有預設值故不影響執行,屬 dev 環境同步提醒)。既有跨版技術債(mypy `list` 遮蔽第 4 次、datetime util 第 2 次)維持,建議交 `/reflect-rules`。**

---

## 1. 總覽

| 項目 | 值 |
| --- | --- |
| 掃描時間 | 2026-07-16 07:56:37 (UTC+8) |
| 類別涵蓋 | ENV / AI / BE / SEC / PII / LOG / GIT / TEST / DEP(FE / DB-schema 本版無變更,見第 5 章) |
| 🔴 Critical | 0 |
| 🟠 High | 0 新增 |
| 🟡 Medium | 1(R-ENV-004)+ 2 既有債記錄(`fixed.md §7/§8`) |
| 🔵 Low | 0 新增(+ 1 既有債記錄) |
| ⚪ Info | — |

**結論**:功能一(模型自動同步排程)沿用既有 taskiq + `sync_models_and_credits`,新任務 `scheduled_sync_models` 完整複製 `ai_model_eval.py` 的 CI-importability / 短路 / 自建 session 慣例,節流與併發鎖以 `AppError.detail` key 判斷後靜默略過,乾淨。功能二(申請單判決通知管理員)best-effort helper `notify_admin_on_verdict` 獨立 try/except、失敗只落 log 不擋主流程、email 模板 jinja `autoescape` 啟用、log 不含 PII / 機密,良好。`sync_models_and_credits` 的 `audit_meta` 為向下相容 optional 參數(預設 `None` = 現況),對既有手動同步端點零影響。**唯一提醒**是本機 `.env` 未同步新 env key。

---

## 2. 專案摘要

- **目標**:OpenRouter API 中控派發管理平台(金鑰/配額/路由/稽核 + 用量統計 + AI 評審)。
- **技術棧對照**:FastAPI + SQLAlchemy 2 async + PostgreSQL(後端)/ Next.js App Router + TS + RTK + Tailwind(前端)/ taskiq + Redis(背景任務,scheduler + worker 雙進程)。與 Design-Base 一致。
- **目錄結構**:`backend/app/{api,services,repositories,schemas,models,core,tasks,templates}` 分層清楚;新增 `tasks/model_sync.py` 與 `templates/email/admin_apireq_verdict.{html,txt}` 落點正確。
- **Task 進度**:v2.2.0 五 task(501 env / 502 排程 task / 503 compose / 511 M365 寄信底層 / 512 申請單觸發)**全數 done**,5/5;本版無 `fixed.md`(尚無規範違反 / bug)。
- **完成度**:功能完整,測試覆蓋(test_model_sync_dispatch 4、test_email_graph_admin_notify 6、test_api_key_requests_admin_notify 7;consolidated ruff 全綠、`tests/api` 85 綠)。全版無 DB migration。

---

## 3. 詳細發現(依嚴重度)

### 🟡 [R-ENV-004] 本機 `.env` 未同步 v2.2.0 三顆新 env key

- **檔案**:`.env`(本機,未追蹤)對照 `.env.example`(已含三 key)
- **內容**:`.env.example` 已加 `MODEL_SYNC_SCHEDULE_ENABLED` / `MODEL_SYNC_INTERVAL_DAYS` / `APIREQ_ADMIN_NOTIFY_ENABLED`,但本機 `.env` 三者皆缺(`grep -c` = 0)。
- **白話**:三者於 `app/core/config.py` 皆有預設值(`False` / `3` / `False`),故 app / worker / scheduler **啟動與執行不受影響**,行為等同「排程關、通知關」。但違反 CLAUDE.md「開發前必檢查:`.env.example` 所有鍵名已於 `.env` 填值」——未同步會讓要**啟用**這兩功能的人漏設。
- **修正(具體)**:在本機 `.env` 補三行(與 `.env.example` 同):
  ```
  MODEL_SYNC_SCHEDULE_ENABLED=false
  MODEL_SYNC_INTERVAL_DAYS=3
  APIREQ_ADMIN_NOTIFY_ENABLED=false
  ```
  正式環境(Coolify)則於 Environment Variables 補這三顆(prod compose 已注入 `${...}` 佔位,task-503)。
- **首次發現**:2026-07-16

---

## 4. 修正優先序

- **立刻**:無(無 🔴)。
- **本週**:無新增 🟠。
- **有空**:
  - 🟡 R-ENV-004 — 本機 `.env` 補三顆新 key(不影響現況執行,啟用功能前必補)。
  - 🟡 清債(`fixed.md §7`)— `UsageLogRepository.list` 改名根治 mypy 連坐(第 4 次,達升規門檻)。
  - 🟡 清債(`fixed.md §8`)— 建立共用 `frontend/src/lib/utils/datetime.ts`。
  - 🔵 清債 — `api_key_requests.py:240` `validate_fields` 型別(`Department | None` vs `Department`,v1.9.1 遺留)。

---

## 5. 已跳過類別(附原因)

- **R-FE-***(全前端)**:v2.2.0 **無前端變更**(propose 明訂「前端呈現排程狀態 / 模型管理頁改動」皆 Out of Scope),無 `.tsx` / `.jsx` 異動。
- **R-DB-001~016(migration / schema / COMMENT / table_catalog)**:v2.2.0 **無 migration、不動 DB schema**(propose §D.6「僅 log 不落 DB」),整批 DB-schema 規則不適用。
- **R-SEC-001/004/006(JWT alg / eval / 上傳)**:未觸及認證簽章、無 `eval`/`exec`、無檔案上傳。
- **R-LOG-001/004/006(health / graceful shutdown / version)**:未動啟動 / lifespan / 健康檢查端點(排程 task 掛既有 scheduler 進程,`engine.dispose` 沿用既有 lifespan)。
- **R-DEP-***:未動 `pyproject.toml` / `package.json` / lock 檔(無新套件;taskiq / httpx / jinja2 皆既有)。
- **R-BE-001~013(路由 / response / CORS)**:v2.2.0 未新增 API endpoint(功能一為排程 task、功能二為既有端點內加寄信),無新路由面。

---

## 6. AD-xxx(規則外架構判斷)

**本次無新增 AD 項。** 已巡視面向與判斷:

- **排程冪等 / 併發**:`scheduled_sync_models` 依賴 `sync_models_and_credits` 的 pg advisory xact lock + 10 分鐘 throttle;排程遇兩者以 `AppError.detail ∈ {sync_throttled, sync_in_progress}` 靜默略過,不重試堆積——正確。任務尾端 `await db.commit()` 在 sync 已內部 commit 後為 no-op,無害(對齊「session 擁有者負責 commit」慣例)。
- **best-effort 通知不連坐**:`notify_admin_on_verdict` 全 body 包 try/except(`api_key_requests.py:123`),失敗只 `logger.exception` / `info`,不回滾申請單、不影響 `_notify_owner`——符合 propose §D.6 best-effort 語意。四終態呼叫點與 owner-notify 同層、非巢狀。
- **PII / 機密**:管理員通知 log 只印 `INITIAL_ADMIN_ACCOUNT`(帳號字串)與 `row.request_uid`(對外 UID),**不印** email / 一次性密鑰;email 模板經 task-511 測試確認不含 `sdk_key` / `user_token`。jinja `autoescape=select_autoescape(["html"])` 啟用,申請人姓名 / reason 入 HTML 有跳脫,無 HTML injection。
- **稽核可歸因**:排程同步帶 `audit_meta={"trigger":"scheduler"}`,`write_audit(extra=...)` 落庫,可與手動同步區分——對齊 D.2。
- **cron 月底近似**:`0 0 */N * *` 月底邊界重置(跨月最長 > N 天)為 propose §D.1 已揭露並拍板的取捨,非缺陷。

---

## 7. 規範自身問題(Design-Base 矛盾 / 缺漏)

1. **既有債達升規門檻(第 4 次,延續前次第 2 點)**:mypy `list` 方法名遮蔽(`fixed.md §1/§2/§4/§7`)。前兩次報告已建議開清債 task + `/reflect-rules`,至今未動。**建議**本輪收口一併跑 `/reflect-rules`,將「repository 方法名禁與內建型別同名」升為 `03-backend/00-overview.md` 命名段規則。
2. **共用 `utils/datetime.ts` 缺漏(第 2 次,`fixed.md §5/§8`)**:延續前次第 3 點,`04-datetime.md` 規定共用檔存在但未建;v2.2.0 無前端變更未觸及,債維持。
3. **排程任務掛載三處同步無規範明載**:taskiq 排程需 ❶ task 帶 `schedule` label、❷ `scheduler.py` import 模組、❸ worker command 登記模組——三處漏一即靜默不觸發(本版 task-502/503 已正確處理,但屬易漏隱性契約)。**建議**於 `03-backend/*` 或 `06-Coolify-CD/*` 補一條「新增排程任務的三處掛載檢查表」,避免未來漏掛。

---

> 總結:v2.2.0 五 task 新碼**無 🔴、無 🟠**、品質高,best-effort / 冪等 / PII / 稽核面向皆正確。唯一 🆕 為 R-ENV-004(本機 `.env` 未補三顆新 key,有預設值不影響執行,啟用功能前補即可)。其餘為既有跨版技術債(mypy `list` 遮蔽第 4 次、datetime util 第 2 次),建議本輪收口交 `/reflect-rules` 升規。

---

**本版無 Critical / High。** 要我幫你:❶ 補本機 `.env` 三顆新 key(R-ENV-004),或 ❷ 跑 `/reflect-rules` 處理達門檻的既有債?
