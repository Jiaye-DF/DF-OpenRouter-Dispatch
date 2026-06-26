# 專案掃描報告 — Issue-Scan-Project-260626142613

> 本報告僅涵蓋**本地開發**範圍(程式碼 + 本地服務組態),不涵蓋部署規範。
> 前次基準:`Issue-Scan-Project-260625173653.md`(2026-06-25,v2.0.x 累積掃描,1🟡 + 2🔵)。
> 本次目的:對基準後新增的 **v2.1.0**(推薦模型「真實重跑 + 對比裁決」champion/challenger GAN 閉環,10 tasks done)做累積式掃描。
> 掃描方式:讀 v2.1.0 全 18 個新增/修改檔(後端管線 401→406 + 讀取 API 407/408 + 前端 409/410),對照 R-xxx 規則 + fixed.md §1–§5 既有債。

---

## 0. 與前次差異

以 `R-xxx` / `AD-xxx` ID + 路徑為 key。基準後新增 v2.1.0 一個版本,差異如下。

| 狀態 | 項目 | 嚴重度 | 佐證 / 說明 |
| --- | --- | --- | --- |
| 🆕 新發現 | R-DB-013 新表表級 COMMENT 單語(中文) | 🟡 | `0026_ai_eval_reruns.py:245` 表級 `comment="模型評審 challenger 真實重跑與對比裁決"` 為中文單語;同檔欄級 COMMENT 皆中英雙語(`active flag` / `soft-delete flag` …),表級與欄級不一致。 |
| 🆕 新發現 | R-FE-005 重跑空狀態未區分「評審中/維持原模型」 | 🔵 | `AiRerunSection.tsx` empty state 僅提示「尚無 challenger 重跑」,未區分「重跑未派發」vs「推薦=原模型故 0 筆」。低後果。 |
| ⏸ 既有債維持 | fixed.md §1/§2/§4 mypy 整包連坐(`list` 方法名 / `Result.rowcount` / `seqlog` 缺 stub) | 🟠→記錄 | v2.1 新碼**自身檔** mypy 全綠;錯誤全來自範圍外既有檔。已達升規門檻(跨 §1/§3/§4 第 3 次),建議開清債 task。詳見第 7 章。 |
| ⏸ 既有債維持 | fixed.md §3 `AiModelEvaluationRepository` 缺 `find_by_uid` getter | 🟡→記錄 | task-405 service 以 ORM `select` 權宜直取父列(非 raw SQL,對齊 `proxy.py` 先例),已註解 cross-ref。建議清債 task 補 repo getter。 |
| ⏸ 既有債維持 | fixed.md §5 `utils/datetime.ts` 未建 | 🟡→記錄 | task-410 範圍鎖檔下於 `AiRerunSection.tsx` 就地實作 `formatDateTime`(正規表示式版,不用 `toLocaleString`,符合時區地板)。建議開基建 task。 |
| ✅ 沿用通過 | R-DB-014 新表登錄 table_catalog | 🟠 | `0026:266–284` 已 upsert 一筆(`ON CONFLICT (table_name) DO NOTHING`),含 `display_name_zh` + `category`,冪等。 |
| ✅ 沿用通過 | R-DB-005 cost/score 精度 | 🟠 | `Numeric(12,6)`(cost)/ `Numeric(4,3)`(score)為 propose 指定,model docstring 已註明理由,非缺陷。 |
| ⏸ 決策維持 | AD-001 / AD-005 / R-DEP-002 / R-DEP-004 / Tailwind v4 vs v3 | — | 前次既有,本版未觸碰,維持原狀(見前報告)。 |

**本次新增 v2.1.0(10 tasks),僅 1 🟡(表級 COMMENT 單語)+ 1 🔵(空狀態提示),無任何 🔴 / 🟠 新缺陷。** 後端重跑管線(冪等/串行/部分失敗/盲化裁決)、讀取 API(AdminDep/ApiResponse 殼/純讀)、前端三態與型別品質高;fixed.md 已誠實記錄 5 條既有債,v2.1 新碼自身全綠未惡化。

---

## 1. 總覽

| 項目 | 內容 |
| --- | --- |
| 掃描時間 | 2026-06-26 14:26 (UTC+8) |
| 性質 | 累積式掃描(基準後 v2.1.0 新增碼 + 既有債回歸確認) |
| 🔴 Critical | 0 |
| 🟠 High | 0(既有 mypy 債連坐已由 fixed.md §1/§2/§4 記錄,非 v2.1 引入) |
| 🟡 Medium | 1(R-DB-013 新表表級 COMMENT 單語) |
| 🔵 Low | 1(R-FE-005 重跑空狀態提示可精化) |
| ⚪ Info | 0 |

**結論**:v2.1.0「真實重跑 + 對比裁決」10 個 task 新碼**無 🔴/🟠 缺陷**。受保護端點 `AdminDep`、Response `ApiResponse` 殼、純讀不開 transaction、challenger 重跑冪等(`UNIQUE(ai_evaluation_uid, rerun_model)`)、discriminator 盲化(payload 不含模型名)、金鑰不入 log、Decimal→str 對外、前端強型別 + 三態 + 集中 label 全數乾淨。唯 1🟡(表級 COMMENT 補英文)+ 1🔵(空狀態提示)+ 沿用 fixed.md 5 條既有債(建議清債 task)。

---

## 2. 專案摘要

- **目標**:DF-OpenRouter-Dispatch — 內部 LLM 派發閘道。
- **技術棧**:Next.js 14 + React 18 + FastAPI + asyncpg/SQLAlchemy + Alembic(0001→**0026**)+ taskiq + Redis + Seq。
- **Task 進度**:v2.0.0(評審地基)→ v2.0.1(taskiq/Redis 判別管線)→ v2.0.2(DB 自我說明)→ v2.0.3(評審結果顯示)→ **v2.1.0(推薦模型真實重跑 + 對比裁決,GAN 閉環,10/10 done)**。
- **本批掃描覆蓋新碼**(18 檔):
  - 後端管線:`core/config.py`(2 env)、`models/ai_model_eval_rerun.py`、`models/ai_model_evaluation.py`(2 游標欄)、`alembic/versions/0026_ai_eval_reruns.py`、`repositories/ai_model_eval_rerun.py`、`repositories/ai_model_evaluation.py`、`services/ai_model_eval_rerun.py`、`services/ai_model_eval_rerun_prompt.py`、`schemas/ai_model_eval.py`(DiscriminatorOutput)、`tasks/ai_model_eval.py`(dispatch_unrerun / rerun_evaluation_task)。
  - 讀取 API:`services/ai_model_eval_rerun_result.py`、`schemas/ai_model_eval_rerun_result.py`、`api/v1/ai_eval_reruns.py`、`api/v1/__init__.py`。
  - 前端:`types/api.ts`、`lib/api/endpoints.ts`、`lib/ai-eval-labels.ts`、`app/(main)/usage-logs/[uid]/AiRerunSection.tsx`、`AiAnalysisSection.tsx`。
- **完成度**:10/10 task `done`,各 task Acceptance(pytest/ruff/自身檔 mypy/前端 type-check+lint+build)實跑全綠;fixed.md 5 條既有債均屬範圍外、已記錄。

---

## 3. 詳細發現(依嚴重度)

### 🟡 [R-DB-013] 新表表級 COMMENT 為中文單語(欄級已雙語)

- **檔案**:`backend/alembic/versions/0026_ai_eval_reruns.py:245`(`comment="模型評審 challenger 真實重跑與對比裁決"`);對應 model `backend/app/models/ai_model_eval_rerun.py` `__table_args__` 表級註解同源
- **內容**:同份 migration 的**欄級** COMMENT 皆中英雙語(如 `:56` `"是否啟用… | active flag"`、`:63` `"… | soft-delete flag"`),但**表級** COMMENT 只有中文,缺英文。
- **白話**:`04-databases/00-overview.md § 自我說明` 要求 schema COMMENT 中英雙語。欄級做到了、表級漏了,屬同檔內標準不一致,不影響功能,但讓「表級自我說明」少一半。
- **修正**:`0026:245` 與 model `__table_args__` 的表級 comment 改雙語,例:`comment="模型評審 challenger 真實重跑與對比裁決 | model evaluation challenger rerun & discriminator verdict"`;`table_catalog` 的 `description`(`:281`)可一併對齊。屬資訊性,可併入後續 DB 清債 task。
- **首次發現**:2026-06-26

### 🔵 [R-FE-005] 重跑空狀態未區分「評審中/未派發」與「維持原模型故 0 筆」

- **檔案**:`frontend/src/app/(main)/usage-logs/[uid]/AiRerunSection.tsx`(empty state 分支)
- **內容**:`reruns` 為空時統一顯示「尚無 challenger 重跑」。實際空集合有兩種語意:(a) 重跑尚未派發 / 進行中;(b) 三裁判推薦皆=原模型,去重後 0 筆(決議 #4,屬正常終局)。
- **白話**:Loading/Error/Empty 三態本身齊備(scan 確認),此為 empty 態的**語意細分**,屬體驗精化非缺陷;後端目前回 `reruns:[]` 不帶「為何空」的旗標。
- **修正**:可選——後端讀取面未來補父表 `ai_rerun_status` / `ai_reran_at` 提示,前端據此顯示「重跑進行中」或「推薦模型與原模型一致,無需重跑」;現版以單一空狀態文案處理可接受。
- **首次發現**:2026-06-26

---

## 4. 修正優先序

- **立刻**:無(無 🔴/🟠 新缺陷)。
- **本週(可選)**:R-DB-013(表級 COMMENT 補英文,1–2 行,可併 DB 清債 task)。
- **有空**:R-FE-005(空狀態語意細分,需後端配合帶旗標)。
- **建議開清債 task(fixed.md 升規候選,見第 7 章)**:
  1. mypy 既有債(`UsageLogRepository.list` / `*.list` 方法改名、`model.py` `Result.rowcount` 替代寫法、`pyproject.toml` 加 `seqlog.*` mypy override)— **已達升規門檻**(fixed.md §1/§3/§4 連續第 3 版同類)。
  2. `AiModelEvaluationRepository.find_by_uid(ai_evaluation_uid)` getter(fixed.md §3),完成後把 task-405 service 改回走 repository。
  3. `frontend/src/lib/utils/datetime.ts` 共用 `formatDateTime`(fixed.md §5),把 `AiRerunSection.tsx` 就地版與既有 `usage-logs/[uid]/page.tsx:195` 的 `toLocaleString()` 一併改走共用。
- **待使用者決策(維持中,前次延續)**:AD-001(SDK Key 加密)、AD-005(prompt 保留策略)。

---

## 5. 已跳過類別(附原因)

| 類別 | 原因 |
| --- | --- |
| ENV 機密 / GIT | v2.1 僅新增 `AI_RERUN_ENABLED` / `AI_RERUN_DISCRIMINATOR_ENABLED` 兩布林開關,`.env.example` 已同步(R-ENV-002/004 通過);無機密寫死、challenger/discriminator 沿用既有 `DEFAULT_OPENROUTER_KEY` 不新增金鑰 env。 |
| BE 鑑權 / Response / 錯誤收斂 | `api/v1/ai_eval_reruns.py` 端點 `AdminDep`、回 `success_response`(ApiResponse 殼)、路徑 `/api/v1/ai-eval/...`、純讀不開 transaction;service 錯誤收斂 AppError、不洩金鑰(R-BE-001/003/005/012 通過)。 |
| BE transaction | `create_rerun` 以 `begin_nested()`/`begin()` 原子寫一筆 + `UNIQUE` 冪等;`rerun_evaluation_task` session 擁有者 `await db.commit()`(R-BE-019 通過)。 |
| DB raw SQL / 軟刪 / migration | 無字串拼接(service 以 ORM `select`);`list_by_*` 預設 `is_deleted=false` 過濾;migration 不改既有欄、downgrade 對稱、登錄 table_catalog(R-DB-004/009/012/014 通過)。 |
| AI 幻覺 / 硬編 | service 呼叫為實體函式、無幻覺 API;無硬編 IP/URL/magic;無未追蹤 TODO(R-AI-001/002/003 通過)。 |
| FE any / 三態 / fetch / XSS / i18n | `AiRerunSection.tsx` 無 `any`、走 `apiClient` 非裸 fetch、無 `dangerouslySetInnerHTML`、label 集中 `ai-eval-labels.ts`、loading/error/empty 三態齊(R-FE-002/003/004/010 通過;R-FE-005 僅空狀態語意細分,列 🔵)。 |
| PII / 機密 log | service 異常只進結構化 log、對外收斂 AppError,無金鑰/PII 印字(R-PII-001 通過);`response_summary` 為摘要非全文。 |
| TEST | v2.1 各 task 自帶測試:`test_ai_model_eval_rerun_prompt.py`(23)、`test_ai_model_eval_rerun.py`(repo 11 / service 12)、`test_ai_model_eval_rerun_result.py`(7)、`test_ai_model_eval_rerun_dispatch.py`(5)、`test_ai_eval_reruns.py`(4)— 走真 DB / respx,無 mock SQL(R-TEST-001/004/005 通過)。 |
| R-DEP / R-DB-002 必備欄 | 前次已評估,本版未變;新表沿用 `pid`+`<entity>_uid`+`is_active`/`is_deleted`/`created_at`/`updated_at` 慣例。 |

---

## 6. AD-xxx + v2.1.0 重點回歸

### AD-xxx(規則外架構判斷)

本次掃描**無新增 AD**(寧空勿湊)。已巡視面向:

- **邏輯邊界**:challenger 去重集合 `{裁判推薦} − {原模型}`、串行重跑、單筆失敗不阻斷、全失敗 `mark_reran(0)` / ≥1 成功 `mark_reran(1)`、無推薦≠原模型 → 0 筆 + `mark_reran(1)` — 狀態機完整,終局不重派(`ai_reran_at` 短路)。
- **效能**:`dispatch_unrerun` 沿用既有 beat/batch(`AI_EVAL_DISPATCH_BATCH_SIZE`)、FIFO `created_at ASC` 反餓死;查詢 API 純讀、`list_by_usage_log_uid` 走索引 `(usage_log_uid)`。無 N+1 / 阻塞新風險。
- **商業邏輯 / race**:`create_rerun` 以 `UNIQUE(ai_evaluation_uid, rerun_model)` 冪等(不分軟刪),重複派發安全;`rerun_evaluation_task` 呼叫前短路已重跑父評審,省 API。
- **啟動 / 維運**:不動 `scheduler.py`(`LabelScheduleSource` 自動撈新 schedule label);維持模組裸環境 importability;`AI_RERUN_ENABLED=false` 預設關 → 零成本零派發(成本閘靠總開關 + 去重 + 維持原模型跳過,決議 #1/#8)。

### v2.1.0 既有債誠實揭露(fixed.md §1–§5)

worker 在範圍鎖檔(「禁碰其他檔案」)下,對 5 處超出範圍的既有債/基建缺口**未擅改**,改寫 fixed.md 記錄並以權宜方案(ORM select / 就地 formatDateTime / 自身檔 mypy 佐證)交付,符合 `01-propose/03-multi-agent-flow.md` 違規回報協議。此為正向行為,非缺陷。

### 已巡視、低後果未列正式項

- `cost_delta_usd` 無原成本時留 NULL(propose §9 風險,model/schema 已涵蓋)— 既定設計,非缺陷。
- discriminator A/B 盲化隨機映射在 service 端,prompt 端不知模型名(決議 #7)— 測試已斷言映射還原正確 + payload 不含模型名,正確。
- 子開關 `AI_RERUN_DISCRIMINATOR_ENABLED=false` → `compare_*` 全 NULL 仍寫客觀指標列 — 既定設計,前端「已重跑·未裁決」狀態對應。

---

## 7. 規範自身問題(Design-Base 矛盾 / 缺漏)

1. **mypy acceptance 範圍 vs「禁碰其他檔案」衝突(fixed.md §1/§3/§4,已達升規門檻)** — 多個 task 的 acceptance 訂為 `mypy app/<pkg>/`(整包),但 task 又鎖「禁碰其他檔案」,使既有債在新 task 驗收上「連坐」。**跨 v2.1 第 3 次同類**,建議:(a) 對「禁碰其他檔案」的 task,mypy acceptance 收斂為「僅本 task 變更檔」或建立 mypy baseline;(b) 同時開清債 task 根治(`*.list` 方法改名、`Result.rowcount` 替代、`pyproject.toml` 加 `[[tool.mypy.overrides]] module="seqlog.*" ignore_missing_imports=true`)。**此條建議交 `/reflect-rules` 升規。**
2. **任務切分應把「消費 service 所需的 repository 讀取方法」納入上游 repo task(fixed.md §3)** — task-405 入口參數為 `ai_evaluation_uid`,但 repo 只補了 by-uid 寫入口(`mark_reran` / `fetch_unreran_*`),漏補 by-uid 讀 getter,逼下游 service 在鎖檔下繞道 ORM select。建議 orchestrator 拆解時對齊「service 讀取面 ↔ repo task 範圍」。
3. **共用 `utils/datetime.ts` 從未落地(fixed.md §5)** — `02-frontend/04-datetime.md` / `05-components.md` 規定日期格式化必走共用 `formatDateTime`,但該 util 從未被任何前一版 task 建立;首個需日期顯示的前端 task(410)被迫就地實作。建議開基建 task 補 util,並順手修既有 `usage-logs/[uid]/page.tsx:195` 的 `toLocaleString()` 違規。
4. **(前次延續,未解)** Tailwind v4 宣稱 vs v3 實況、機密 at-rest 加密準則缺、跨 worker 共享狀態準則(Redis 僅用於 taskiq)、CI 規範已寫未落地(無 `.github/workflows/`)。詳見前報告第 7 章,本版未觸碰,維持。

---

> 結論:v2.1.0「真實重跑 + 對比裁決」10 個 task **無 🔴/🟠 新缺陷**,僅 1🟡(新表表級 COMMENT 補英文)+ 1🔵(重跑空狀態語意細分)。後端管線冪等/串行/盲化/錯誤收斂、讀取 API 鑑權/殼/純讀、前端三態/型別/集中 label 品質高。最具行動價值者為 fixed.md 已揭露的 **3 條清債候選**(mypy 連坐根治【已達升規門檻】、repo `find_by_uid` getter、共用 `datetime.ts`),建議開獨立清債 task 並交 `/reflect-rules` 處理升規(第 7 章第 1 項)。
