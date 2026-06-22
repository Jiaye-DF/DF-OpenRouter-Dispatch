# 專案掃描報告 — Issue-Scan-Project-260622060413

> 本報告僅涵蓋**本地開發**範圍(程式碼 + 本地服務組態),不涵蓋部署規範。
> 前次基準:`Issue-Scan-Project-260622052905.md`(同日稍早)。本次目的:**確認該報告各項修正後的具體現況**,並對本批修正做回歸檢查。
> 對應修正紀錄:`docs/Tasks/v1.10/fixed.md`。

---

## 0. 與前次差異

以 `R-xxx` / `AD-xxx` ID + 路徑為 key。本次無新增程式功能,差異全為前次發現的處理結果。

| 狀態 | 項目 | 嚴重度 | 佐證 |
| --- | --- | --- | --- |
| ✅ 已修 | R-BE-008 CORS 萬用字元回退 | 🔴 | `main.py:50` `allow_origins=settings.cors_origins_list`(移除 `or ["*"]`)。 |
| ✅ 已修 | R-BE-020 prod fail-fast | 🟠 | `config.py:97-109` `_fail_fast_in_prod`:prod 下 `JWT_SECRET<32` 或 `CORS_ORIGINS` 空即 raise。 |
| ✅ 已修 | AD-002 併發送單 race | 🟠 | `api_key_requests.py:38-50` `_lock_dedup_key`(`pg_advisory_xact_lock`),create / process 兩入口皆取鎖。 |
| ✅ 已修 | R-BE-012 process 錯誤外洩 | 🟠 | `api_key_requests.py` process `except` 改 `logger.exception` + 固定 `provision_failed`,不回原始例外。 |
| ✅ 已修 | AD-003 usage_log 漏記帳 | 🟠 | `proxy.py:54-56,330-336` `_usage_log_tasks` set 持強引用 + `add_done_callback`。 |
| ✅ 已修 | AD-004 SSE 非 OR 收尾 | 🟡 | `proxy.py` relay 增泛型 `except Exception` 補送 `[DONE]`;`aclose()` 包 try/except 保記帳。 |
| ✅ 已修 | R-LOG-006 version 端點 | 🔵 | `health.py:18-24` `version_router` → `GET /api/v1/version`;`__init__.py` 已註冊。 |
| ✅ 已修 | AD-007 failover N+1 | 🔵 | `proxy.py` 兩條 OR 路徑改迴圈外 `list_active_by_department` 一次 + 記憶體 shuffle。 |
| ✅ 已修 | AD-008 status 預設值 | 🔵 | `models/api_key_request.py:34` `server_default="manual_pending"` + migration `0016`。 |
| ⏸ 決策維持 | AD-001 SDK Key 明文存 DB | 🟠 | 使用者 2026-06-22 決策暫維持(已文件化取捨),`models/sdk_api_key.py:23` 不變。 |
| ⏸ 決策維持 | AD-005 prompt/images 全文落地 | 🟡 | 使用者 2026-06-22 決策暫維持,`proxy.py` `request_content` 不變。 |
| ⏸ 待 Redis 任務 | AD-006 無 per-caller 配額 | 🟡 | 需跨 worker 共享計數,歸入未來 Redis 任務;本批不導入 Redis。 |
| ⏸ 待 Redis 任務 | M3 rate_limit 單 process | — | 同上,多 worker 速率限制需 Redis。 |

**前次 9 項可立即處理的發現(🔴×1 / 🟠×4 / 🟡×1 / 🔵×3)全數已修並 commit。** 其餘 3 項屬「使用者決策維持現狀」或「待 Redis 任務」,非疏漏。

---

## 1. 總覽

| 項目 | 內容 |
| --- | --- |
| 掃描時間 | 2026-06-22 06:04 (UTC+8) |
| 性質 | 修正後複查(confirm)+ 本批回歸檢查 |
| 🔴 Critical | 0 |
| 🟠 High | 0(未解;AD-001 已決策維持) |
| 🟡 Medium | 0(未解;AD-005 決策維持、AD-006 待 Redis) |
| 🔵 Low | 0 |
| ⚪ Info | 0 |

**結論**:前次報告所有「應修且可立即修」的項目皆已完成並通過 `py_compile`,已 commit(`a4c3ff7`)並推送 origin + df-it。**目前無未處理的待修缺陷**;剩餘三項為使用者明示維持現狀(AD-001 / AD-005)或架構性待辦(AD-006 / M3,需 Redis)。本批修正經回歸檢查未發現新引入問題(見第 6 章)。

---

## 2. 專案摘要

- **目標**:DF-OpenRouter-Dispatch — 內部 LLM 派發閘道。
- **技術棧**:Next.js 14 + FastAPI + asyncpg/SQLAlchemy + Alembic(0001→**0016**)+ Seq。
- **Task 進度**:v1.10(SSO 自動帶部門 + 稽核 log 修正 + 本批 scan 修正)。
- **變更檔(本批)**:`main.py`、`config.py`、`api_key_requests.py`、`proxy.py`、`health.py`、`api/v1/__init__.py`、`models/api_key_request.py`、`.env.example`、`alembic/versions/0016_*.py`。

---

## 3. 詳細發現(依嚴重度)

**無新增待修缺陷。** 以下為「未解但屬決策 / 待辦」三項的現況追蹤(非本次新發現,僅標明狀態與後續條件)。

### 🟠 [AD-001] SDK API Key 明文存 DB(決策維持現狀)

- **檔案**:`backend/app/models/sdk_api_key.py:23`(`key_values` 明文)
- **現況**:使用者 2026-06-22 決策暫維持;屬已簽核業務取捨(DB 可直編)。
- **後續條件**:若日後改為 reveal-once 或 at-rest 加密,再行處理;否則建議於 Design-Base 留正式簽核紀錄(見第 7 章)。

### 🟡 [AD-005] prompt / images 全文落地 `usage_logs.request_content`(決策維持現狀)

- **檔案**:`backend/app/services/proxy.py`(`_build_request_log` / `request_content`)
- **現況**:使用者 2026-06-22 決策暫維持(dashboard 檢視需求)。
- **後續條件**:若合規要求收緊,評估 images 比照 files 只記 metadata,或欄位級加密 / 保留期限。

### 🟡 [AD-006] SDK Key 維度無配額 / rate limit(待 Redis 任務)

- **檔案**:`backend/app/core/sdk_auth.py`(只做身分解析,無 per-caller 配額)
- **現況**:歸入未來 Redis 任務。per-caller 日 token / RPM 需跨 worker、跨請求累計,記憶體不可行。
- **後續條件**:導入 Redis 後一併處理(與 M3 多 worker 速率限制、壞 key cooldown 同批)。

---

## 4. 修正優先序

**已完成(本批,commit a4c3ff7)**:R-BE-008 / R-BE-020 / AD-002 / R-BE-012 / AD-003 / AD-004 / R-LOG-006 / AD-007 / AD-008。

**待使用者決策(目前選擇維持)**:AD-001(SDK Key 加密 or 簽核)、AD-005(prompt 保留策略)。

**架構性待辦(獨立 Redis 任務)**:AD-006(per-caller 配額)、M3(多 worker 速率限制)、壞 key cooldown。建議一次規劃導入 Redis(含 docker-compose / 連線 / 健康檢查),不夾在程式修正批。

---

## 5. 已跳過類別(附原因)

| 類別 | 原因 |
| --- | --- |
| ENV / GIT / 機密寫死 | 同前次:`.env` 已 gitignore、無敏感檔追蹤、無機密寫死;`.env.example` 本次已同步新增 `APP_VERSION`。 |
| FE(localStorage / XSS / any / 三態) | 前次已逐項驗證通過,本批未動前端。 |
| DB(金額 / 雜湊 / SQL 拼接 / 軟刪 / migration) | 前次通過;本批新增 migration `0016` 為線性接續 `0015`,僅 `ALTER COLUMN ... SET DEFAULT`,無重寫既有 revision。 |
| 規範優先跳過項(R-DB-002 / R-BE-003 / R-BE-001) | 同前次,依 Design-Base 優先。 |

---

## 6. AD-xxx + 本批回歸檢查

### 本批修正回歸檢查(確認未引入新問題)

- **CORS 移除回退**(`main.py:50`):空 `CORS_ORIGINS` 時 `allow_origins=[]` → 不開放跨域(非崩潰);prod 由 `_fail_fast_in_prod` 提前 raise。dev 行為:需在 `.env` 明列 origin,否則前端跨域被擋——**屬預期,已於 `.env.example` 提示**。
- **prod fail-fast validator**:`mode="after"` 僅在 `is_prod` 為真時檢查,dev / test 不受影響;`get_settings` 仍 `lru_cache`,驗證只在首次建構執行一次。無誤擋。
- **advisory lock**(`_lock_dedup_key`):每交易僅取單一鍵、固定取得順序,無交叉鎖 → **無死鎖風險**;鎖隨交易 commit 釋放。注意:鎖在 create 路徑會橫跨 AI 驗證(OpenRouter 呼叫)期間持有,等於同 (部門+專案+負責人) 的併發送單會序列化等待該外呼——**屬刻意且正確的去重序列化**,併發稀少,可接受。
- **proxy 預取 shuffle**:`random.sample(keys, len(keys))` 對空清單回 `[]` → 迴圈不執行 → 落入既有「全部失敗」分支,與原 `pick_random_active` 回 None → break 行為一致。`tried` 排除集合已移除且無殘留參照(internal 路徑 `tried_uids` 未動)。無行為回歸。
- **usage_log task set**:`add` + `add_done_callback(discard)` 標準寫法;`schedule_usage_log` 無 running loop 時 early return,不入 set。無洩漏。
- **SSE 泛型 except**:`CancelledError` 屬 `BaseException` 不落 `except Exception`,呼叫端斷線仍由 finally 記帳後自然傳播,不被吞;`aclose()` try/except 確保記帳必執行。

### 已巡視、低後果未列正式項(延續前次)

- SDK Key 驗證 timing/prefix enumeration(secret 62³² 熵,實務不可爆)。
- claim-secrets 併發領取(同一申請人,影響有限)。

### 新觀察(資訊揭露,低後果,僅記錄)

- **`/api/v1/version` 為公開端點**(無 `Depends` 鑑權):未認證即可讀 `version` / `app` 名稱。屬業界常見做法(health/version 多公開),資訊揭露面極低;若團隊政策要求,可改掛 `AdminDep`。**不列為缺陷**。

---

## 7. 規範自身問題(Design-Base 矛盾 / 缺漏)

1. **缺「機密 at-rest 加密」準則**(延續前次未解):`internal_keys` / `openrouter_keys` 加密、`sdk_api_keys` 明文並存(AD-001 已決策維持)。建議於 `30-database.md` 明定「哪類機密須加密、哪類可明文及其簽核要求」,讓 AD-001 的維持現狀有正式依據。
2. **缺「對外錯誤回應內容」準則**(R-BE-012 已修):建議於 Design-Base 明文「API 回應 `detail` 一律為穩定錯誤碼字串,原始例外只進 log」,作為各端點一致準則,避免再現。
3. **缺「跨 worker 共享狀態」準則**:rate_limit / 配額 / cooldown 散見「單 process 暫行 + 未來 Redis」註解(M3 / AD-006)。建議於 Design-Base 明定多 worker 部署時的共享狀態策略(Redis)與導入時機,讓這類待辦有單一出處。

---

> 結論:前次報告**可立即處理項已全清(已 commit a4c3ff7、推送 origin + df-it)**,且本批修正無新引入問題。目前尚未處理者僅:AD-001 / AD-005(使用者決策維持現狀)、AD-006 / M3 / cooldown(待獨立 Redis 任務)。
