# 專案掃描報告 — Issue-Scan-Project-260625173653

> 本報告僅涵蓋**本地開發**範圍(程式碼 + 本地服務組態),不涵蓋部署規範。
> 前次基準:`Issue-Scan-Project-260622060413.md`(2026-06-22,全清)。
> 本次目的:對基準後新增的 **v2.0.0 / v2.0.1 / v2.0.2**(評審地基 + taskiq/Redis 判別管線 + DB 自我說明)做累積式掃描。
> 掃描方式:依 context 策略分 4 區並行 sub-agent(BE+tasks+SEC+LOG / DB+PII / FE / ENV+GIT+DEP+TEST)後彙整。

---

## 0. 與前次差異

以 `R-xxx` / `AD-xxx` ID + 路徑為 key。基準後新增 v2.0.x 三個版本,差異如下。

| 狀態 | 項目 | 嚴重度 | 佐證 / 說明 |
| --- | --- | --- | --- |
| 🆕 新發現 | R-DEP-002 前端 node 版本未 pin | 🟡 | `frontend/package.json` 無 `engines.node` / `.nvmrc` / `.node-version`。 |
| 🆕 新發現 | R-PII-002 部分 PII 欄位 comment 未標 `(PII)` | 🔵 | `models/user.py` 的 `email`/`employee_id`/`username` 未標,`api_key_request.py` 的 `owner_email` 已標,不一致。 |
| 🆕 新發現 | R-DEP-004 無 CI / 無依賴掃描 | 🔵 | 無 `.github/workflows/`;`pip-audit` / `npm audit` 無從談起。 |
| 🔄 阻塞解除 | AD-006 per-caller 配額 / M3 多 worker rate limit | 🟡 | v2.0.1 已導入 **Redis**(taskiq broker)。原「待 Redis 任務」的技術阻塞已解除,但這兩項功能本身**尚未實作**(v2.0.1 只把 Redis 用於 taskiq)→ 可重啟為獨立任務。 |
| ⏸ 決策維持 | AD-001 SDK Key 明文存 DB | 🟠 | 使用者 2026-06-22 決策維持;`models/sdk_api_key.py` 不變,本次未改。 |
| ⏸ 決策維持 | AD-005 prompt / images 全文落地 | 🟡 | 使用者 2026-06-22 決策維持;v2.0.1 評審管線沿用 `request_content` 全文(內部 worker 讀,不對外、不入 log)。 |
| ✅ 自證通過 | R-DB-013/014/015/016 v2.0.2 自我說明 | 🟠/🟡 | 新增規則,v2.0.2 本身「吃狗糧」全數通過(見第 6 章)。 |

**本次新增 v2.0.x 三版,僅 1 🟡 + 2 🔵,無任何 🔴 / 🟠 缺陷。** v2.0.x 後端評審管線、DB 自我說明、前端判別設定頁實作品質高。

---

## 1. 總覽

| 項目 | 內容 |
| --- | --- |
| 掃描時間 | 2026-06-25 17:36 (UTC+8) |
| 性質 | 累積式掃描(基準後 v2.0.0/v2.0.1/v2.0.2 新增碼 + 既有面回歸) |
| 🔴 Critical | 0 |
| 🟠 High | 0 |
| 🟡 Medium | 1(R-DEP-002 前端 node 未 pin) |
| 🔵 Low | 2(R-PII-002 PII 標註不一致、R-DEP-004 無 CI) |
| ⚪ Info | 0 |

**結論**:基準(2026-06-22)後新增的三個版本(v2.0.0 評審地基 + v2.0.1 taskiq/Redis 判別管線 + v2.0.2 DB 自我說明)**無 🔴/🟠 缺陷**。後端鑑權 / Response 殼 / 錯誤收斂 / 多表 transaction / 金鑰與 PII 不入 log 全數乾淨;DB 新規則自證通過;前端判別設定頁三態 / 權限 / 型別 / disable 全齊;env 一致性(含 taskiq/Redis 7 個新鍵)三方對齊。唯 3 筆輕量待辦(1🟡 + 2🔵)。

---

## 2. 專案摘要

- **目標**:DF-OpenRouter-Dispatch — 內部 LLM 派發閘道。
- **技術棧**:Next.js 14 + React 18 + FastAPI + asyncpg/SQLAlchemy + Alembic(0001→**0022**)+ **taskiq + Redis**(v2.0.1)+ Seq。
- **Task 進度**:v2.0.0(評審地基:3 ai_ 表 + 判別設定 UI)→ v2.0.1(taskiq/Redis 三評審管線,7 tasks done)→ **v2.0.2(DB 自我說明:table_catalog 字典 + 全表/欄位 COMMENT + model↔DB schema parity,6 tasks done)**。
- **本批掃描覆蓋新碼**:`api/v1/ai_eval.py`、`tasks/*`、`services/ai_model_eval*.py`、`repositories/ai_*.py`、18 model 的 `comment=` + `__table_args__`、`models/table_catalog.py`、migration 0019–0022、`app/(main)/ai-analysis/judge-settings/page.tsx`、`.claude/commands/scan-project.md`、Design-Base 自我說明規則。

---

## 3. 詳細發現(依嚴重度)

### 🟡 [R-DEP-002] 前端 node 版本未 pin

- **檔案**:`frontend/package.json`(無 `engines` 欄位);專案無 `frontend/.nvmrc` / `.node-version`
- **內容**:後端 `backend/pyproject.toml:5` 有 `requires-python = ">=3.14"`,但前端未宣告 node 版本下限。
- **白話**:不同開發者 / CI 用不同 node 版本可能造成 build 行為差異(Next 14 對 node 版本敏感)。
- **修正**:`frontend/package.json` 加 `"engines": { "node": ">=20" }`(對齊 Next 14 與 `@types/node ^20`),或新增 `frontend/.nvmrc` 寫 `20`。

### 🔵 [R-PII-002] 部分 PII 欄位 comment 未標 `(PII)`

- **檔案**:`backend/app/models/user.py:59`(`username`)、`:79`(`employee_id`)、`:84`(`email`)
- **內容**:這三欄屬 PII,但 v2.0.2 補的 `comment=` 未加 `(PII)` 尾標;對照 `backend/app/models/api_key_request.py:71/76` 的 `owner_name` / `owner_email` 已標 `(PII)`,標註不一致。
- **白話**:PII 標註是合規與資料治理線索,標一半會讓「哪些欄是 PII」無法靠 schema 自我說明判斷。
- **修正**:`user.py` 的 `username` / `employee_id` / `email` comment 尾端補 `(PII)`(與 `api_key_request` 風格一致)。屬資訊性,不影響功能。

### 🔵 [R-DEP-004] 無 CI / 無依賴掃描

- **檔案**:專案無 `.github/workflows/`
- **內容**:無任何 CI pipeline,故無 `pip-audit` / `npm audit` 依賴弱點掃描。
- **白話**:依賴 CVE 無自動把關,須靠人工。屬既有狀態(非 v2.0.x 引入)。
- **修正**:若後續導入 CI,納入 `pip-audit`(後端)/ `npm audit`(前端)+ ruff/mypy/pytest gate。Design-Base `05-CI/*` 已有規範可循,惟尚未落地 workflow 檔。

---

## 4. 修正優先序

- **本週(可選)**:R-DEP-002(前端加 `engines.node`,1 行)。
- **有空**:R-PII-002(`user.py` 三欄 comment 補 `(PII)`)、R-DEP-004(導入 CI + 依賴掃描,較大,獨立規劃)。
- **待使用者決策(維持中)**:AD-001(SDK Key 加密 or 簽核)、AD-005(prompt 保留策略)。
- **可重啟之架構待辦**:AD-006 / M3(per-caller 配額 / 多 worker rate limit)— Redis 已於 v2.0.1 導入,技術阻塞解除,可開獨立任務實作。

---

## 5. 已跳過類別(附原因)

| 類別 | 原因 |
| --- | --- |
| ENV / GIT 機密 | `.env` 已 gitignore、`git log --all -- .env` 0 筆、無敏感檔追蹤、無機密寫死(命中皆 placeholder `sk-or-v1-xxxx`);taskiq/Redis 7 新鍵三方對齊(R-ENV-004 通過)。 |
| FE(localStorage / XSS / any / 三態) | v2.0.1/v2.0.2 無前端變更;v2.0.0 的 judge-settings 頁逐項通過(三態 / 權限三層 / 強型別 / disable / i18n error-map)。 |
| BE 鑑權 / Response / 錯誤收斂 | ai_eval 兩端點皆 `AdminDep`、回 `success_response`、錯誤收斂為通用 AppError、3 exception handler 齊;taskiq worker 錯誤處理 + 冪等正確。 |
| DB 必備欄位(R-DB-002) | 專案採 `pid`+`<entity>_uid`+`is_active`/`is_deleted`/`created_at`/`updated_at`,Design-Base 既定偏離(不強制 `created_by`/`updated_by`),依規範優先不報。 |
| R-DEP-003 版本浮動 | `pyproject.toml`/`package.json` 雖用 `>=`/`^`,但 `uv.lock` + `package-lock.json` 已 pin 解析版本,實質可重現。 |
| R-TEST 新碼覆蓋 | v2.0.x 測試齊備:`tests/api/test_ai_eval.py`、`tests/services/test_ai_model_eval*.py`、`tests/repositories/test_ai_model_evaluation.py`、`tests/tasks/test_ai_model_eval_dispatch.py`;走真 DB(asyncpg),無 mock SQL。 |

---

## 6. AD-xxx + v2.0.x 重點回歸

### v2.0.2 自我說明規則「吃狗糧」自證(R-DB-013~016)

- **R-DB-013(migration COMMENT)**:`0019`(3 ai_ 表)、`0020`(usage_logs 2 欄)為 comment 規則訂立前所建,**已由 `0022` 全表/欄位回填**(0022 涵蓋三 ai_ 表 + usage_logs 兩新欄)→ 依規則屬「已補回」,不算缺陷。`0021`(table_catalog)建表即自帶表級 + 每欄 COMMENT,符合規則。
- **R-DB-014(table_catalog 登錄)**:`0021` 種子 19 筆(18 既有 + 自身 `category='系統'`),含三 ai_ 表,`ON CONFLICT (table_name) DO NOTHING` 冪等;table_catalog 自我登錄成立。
- **R-DB-015/016(model comment= 普及)**:`TimestampMixin` 四必備欄 + 全 18 表業務欄位皆帶 `comment=`,抽查無漏網;R-DB-016(零覆蓋)已不成立。
- **model↔DB parity**:三 ai_ model 的 `__table_args__` partial index 名稱與 0019 完全對應,partial WHERE `(is_deleted = false)` 正確鏡射(model 小寫帶括號 vs migration `FALSE`,Postgres 語意等價,非缺陷);本專案慣例純 UUID 軟引用、無 DB 層 FK,三 ai_ model 一致遵循。寫入原子性:`create_evaluation_with_candidates` 以 `begin_nested()`/`begin()` 包父+三子+游標為單一原子單位,以 `usage_log_uid` UNIQUE 冪等。

### 已巡視、低後果未列正式項

- 評審 dim1/2 三評審不一致時取「首個成功值」作父表值 — 2026-06-25 使用者拍板設計(docstring 載明),非缺陷。
- `raw_json` 於 repository `del` 丟棄不落地 — AD-005 範疇內「本版不存原始回覆」既定決議,介面預留,非缺陷。
- `/api/v1/version` 公開端點(延續前次)— 業界常見,資訊揭露面極低,不列缺陷。
- SDK Key 驗證 timing / prefix enumeration(secret 高熵不可爆)— 延續前次,不列。

---

## 7. 規範自身問題(Design-Base 矛盾 / 缺漏)

1. **Tailwind 版本:Design-Base / 記憶宣稱 v4,實際為 v3** — `frontend/package.json` 仍為 `tailwindcss ^3.4.13`,但 Design-Base re-baseline 與專案記憶記載「升 Tailwind v4」。屬**規範與實況不一致**:要嘛實際升 v4,要嘛把 Design-Base/記憶改回 v3 現況。建議擇一對齊,避免後續前端任務依錯誤前提。
2. **缺「機密 at-rest 加密」準則**(延續前次未解):`internal_keys`/`openrouter_keys` 加密、`sdk_api_keys` 明文(AD-001 決策維持)。建議於 `04-databases/03-passwords-and-pii.md` 或 `90-project-database.md` 明定「哪類機密須加密 / 哪類可明文及其簽核要求」,讓 AD-001 維持現狀有正式依據。
3. **缺「跨 worker 共享狀態」準則**(部分解除):Redis 已於 v2.0.1 導入,但僅用於 taskiq broker;rate_limit / per-caller 配額 / 壞 key cooldown 仍為單 process。建議於 Design-Base 明定「多 worker 共享狀態一律走 Redis」與 AD-006/M3 的導入時機,讓這類待辦有單一出處。
4. **CI 規範已寫但未落地**:`docs/Design-Base/05-CI/*` 有完整 workflow 規範,但 repo 無 `.github/workflows/`(R-DEP-004)。規範與實況落差,建議補最小 CI(lint/typecheck/test + 依賴掃描)使規範生效。

---

> 結論:基準(2026-06-22)後新增 v2.0.0/v2.0.1/v2.0.2 三版,**無 🔴/🟠 缺陷**,僅 1 🟡(前端 node pin)+ 2 🔵(PII 標註一致性、無 CI)。v2.0.2 的 DB 自我說明新規則已對自身「吃狗糧」全數自證通過。最具行動價值者為第 7 章的 4 項「規範自身問題」,尤以 **Tailwind v4 宣稱 vs v3 實況** 與 **CI 未落地** 值得優先對齊。
