# Fix: 修改使用者部門時 `UUID is not JSON serializable`

## 現象

修改使用者（含部門 `department_uid`）時，寫入 `audit_logs` 失敗：

```
sqlalchemy.exc.StatementError: (builtins.TypeError) Object of type UUID is not JSON serializable
[SQL: INSERT INTO audit_logs (... extra ... ) VALUES (... $10::JSONB ...)]
```

## 根本原因（為什麼會發生）

不是真的「低級錯誤」，而是 **Pydantic dump 模式** 與 **JSONB 序列化** 的銜接落差：

1. `update_user` 取欄位用的是
   `fields = body.model_dump(exclude_unset=True)`（[users.py:171](backend/app/api/v1/users.py#L171)）。
   **沒有帶 `mode="json"`**，所以 `department_uid` 在 dict 裡仍是 **Python `UUID` 物件**，不是字串。
2. 這個 `fields` 直接被塞進稽核 log 的 `extra`：
   `extra={**fields, "tokens_revoked": tokens_revoked}`。
3. `audit_logs.extra` 是 **JSONB** 欄位。SQLAlchemy 寫入時用標準庫 `json.dumps`
   序列化，而 `json.dumps` 預設不認得 `UUID` → `TypeError`。

> 只有「同時改到 `department_uid`」這類 UUID 欄位才會觸發；只改 username/email（字串）時剛好沒踩到，所以平常看起來正常。

## 修正

### 1. 呼叫端：用 `mode="json"` 產生 extra（[users.py](backend/app/api/v1/users.py)）

`fields` 仍維持 Python 物件供 `setattr` 寫回 model；只有監查 `extra` 改用 JSON 化版本：

```python
extra={
    **body.model_dump(exclude_unset=True, mode="json"),
    "tokens_revoked": tokens_revoked,
},
```

### 2. 根本防護：`write_audit` 統一把 `extra` 轉成 JSON-safe（[audit.py](backend/app/core/audit.py)）

其他呼叫端（`departments` / `projects` / `sdk_keys` / `openrouter_keys` /
`internal_keys` / `allowed_models`）也用 `extra=fields` 的同款寫法，屬潛在地雷。
在共用入口統一做 JSON round-trip，一次保護所有呼叫點：

```python
safe_extra = json.loads(json.dumps(extra or {}, default=str))
...
extra=safe_extra,
```

`default=str` 讓 `UUID`、`datetime` 等以字串落地（對稽核 log 而言可接受）。

## 影響範圍

- 行為：稽核 log 內的 UUID/datetime 改以字串記錄，原本能成功的內容不受影響。
- 風險：低。僅序列化形態變更，不動業務邏輯。

## 後續建議

- 凡是要把 Pydantic dump 放進 JSONB 的地方，一律帶 `mode="json"`；
  共用層（`write_audit`）已做防護網，但呼叫端維持正確習慣更佳。

---

# Enhance: SSO 首次登入自動帶入員工編號與部門

## 背景

DF-SSO 經由 [sso.py](backend/app/services/sso.py) 首次登入自動建立成員時，原本**刻意只設 username/email，部門留空**（「由 admin 後續指派」）。
這不是 bug，是設計；但既然 DF-SSO 回應已含部門資訊，可在建立時自動帶入，省去管理者逐一手動指派。

## 資料來源（DF-SSO `/api/auth/me` 回應的 `erpData`）

依 DF-SSO `INTEGRATION.md`「用戶資料格式」，`user.erpData` 內容範例：

```json
"erpData": {
  "gen01": "00063", "gen02": "王小明", "gen03": "F000",
  "gem02": "財務部", "gen06": "user@df-recycle.com"
}
```

欄位對應本地：

| erpData 欄位 | 範例 | 對應本地欄位 |
| ------------ | ------ | ------------------------------------------- |
| `gen01`      | `00063` | `users.employee_id`（員工編號） |
| `gen03`      | `F000`  | `departments.code`（成本中心代碼）→ 查出 `department_uid` |
| `gem02`      | `財務部` | 部門名稱（僅參考，不另存） |
| `gen02`      | `王小明` | `users.username`（原本已用 `info.name`） |

> `SsoUserInfo` 早已接住 `erpData`（[schemas/sso.py:22](backend/app/schemas/sso.py#L22)），
> `DepartmentRepository.get_by_code()` 也現成（[repositories/department.py:21](backend/app/repositories/department.py#L21)）。

## 修改（[sso.py](backend/app/services/sso.py)）

1. 新增 helper `_resolve_erp_profile(db, erp_data)`：
   - 從 `gen01` 取 `employee_id`。
   - 用 `gen03`（成本中心代碼）呼叫 `get_by_code()` 查部門；查到回 `department_uid`。
2. 首次建立成員時把 `department_uid` / `employee_id` 帶入 `User(...)`。

```python
department_uid, employee_id = await _resolve_erp_profile(db, info.erp_data)
user = User(
    ...,
    department_uid=department_uid,
    employee_id=employee_id,
    ...
)
```

## 查無部門時的行為（已採「留空 + 記 log」）

- `erpData` 為 `null`，或 `gen03` 在 `departments` 表查無對應 → `department_uid` 留 `None`，
  **維持原本「管理者後補」行為**，並 `logger.warning` 記下查無的成本中心代碼方便排查。
- 不擲錯、不阻擋登入、不自動新增部門主檔（避免 SSO 灌入未控管資料）。

## 影響範圍

- 行為：能對應到成本中心代碼的新進員工，登入即帶部門與員工編號；對不上的維持空部門待管理者指派。
- 風險：低。僅在「首次建立成員」路徑新增欄位填值，既有使用者登入不受影響。
- 連動：自動指派成功的使用者，管理者就**不必再手動改部門**，自然也不會再走到本文件上半段那條稽核 log 路徑（該路徑亦已修正）。

---

# Fix: 掃描報告 260622 — CORS 回退 + prod fail-fast + 申請單併發 race

> 來源:`docs/Tasks/scan-project/Issue-Scan-Project-260622052905.md`。本批處理該報告唯一 🔴 與一項 🟠。

## R-BE-008 🔴 + R-BE-020 🟠：CORS 萬用字元回退 + prod 啟動把關

### 問題

`main.py` 的 `allow_origins=settings.cors_origins_list or ["*"]`:`CORS_ORIGINS` 未設(空字串)→ `cors_origins_list` 回 `[]` → 回退 `["*"]`，搭配 `allow_credentials=True` 構成「任意來源帶 cookie」。env **有讀**，問題是「漏設時靜默退化成最不安全狀態」。

### 修正

1. [main.py](backend/app/main.py)：移除 `or ["*"]`，改 `allow_origins=settings.cors_origins_list`（空就是不開放跨域，不回退）。
2. [config.py](backend/app/core/config.py)：新增 `@model_validator(mode="after") _fail_fast_in_prod`，`is_prod` 為真時斷言 `len(JWT_SECRET) >= 32` 且 `cors_origins_list` 非空，否則 raise——讓「prod 忘了設」在**啟動當下**就爆，而非上線後被攻擊才暴露。
3. 本機開發在 `.env` 明確填 `CORS_ORIGINS=http://localhost:3000`。

## AD-002 🟠：同 (部門+專案+負責人) 併發送單 race → 重複開通

### 問題

`route → AI → provision → commit` 全程對 project / user 無鎖、無唯一約束。同 owner 同專案的兩個並發請求(最常見:使用者雙擊送出)都在 `route()` 看到「無既有資料」→ 各自開通 → 重複建立 Project / User / SDK Key，繞過 `system_cancel` 去重。

### 修正（採交易級 advisory lock，不改 schema、不影響既有資料）

[api_key_requests.py](backend/app/api/v1/api_key_requests.py)：新增 `_lock_dedup_key()`，以 `pg_advisory_xact_lock(hashtext(:k)::bigint)` 對 `部門代號|專案名|負責人email`(正規化小寫)上交易鎖。

- `create` 端點:`route()` 前取鎖。
- `process` 端點(admin 人工開通):同樣取鎖，與 create 一致。

鎖隨交易 commit 自動釋放;後到者等先到者 commit 後再 `route()`，屆時既有 project/user 已可見 → 正確走沿用/`system_cancel` 去重，不再重複建立。

> 選擇 advisory lock 而非 DB 唯一約束:後者需新 migration，且 `users(email)` / `projects(department_uid,name)` 加唯一約束有撞既有重複資料與軟刪除語義的風險;advisory lock 自我內聚、可逆、零 schema 變更。

### 影響範圍

- 行為：併發送單由「都成功、產生重複」變為「序列化，第二筆走去重/沿用」。正常單一送單無感（鎖瞬間取得即放行）。
- 風險：低。鎖粒度限於同 (部門+專案+負責人)，不影響其他送單併發。

## R-BE-012 🟠：`process` 端點把原始例外字串回前端

### 問題

人工開通失敗時 `raise AppError((pr.error ...) or "provision_failed", code=409)`;`pr.error = str(exc)[:300]` 是**原始例外字串**，`AppError` 首參即 `detail`，經 `failure_response` 原樣回前端，可能洩漏 SQL 約束名 / 表名，甚至 `IntegrityError` 的 `DETAIL: Key (email)=(...)` 回灌**他人 email(PII)**。

### 修正

[api_key_requests.py](backend/app/api/v1/api_key_requests.py)：`process` 端點 `except` 改為 `logger.exception(...)` 把細節(含 `pr.error`)只進 log，對外固定 `raise AppError("provision_failed", code=409)`。新增模組 `logger`。

### 影響範圍

- 行為：admin 開通失敗時畫面只見穩定錯誤碼 `provision_failed`，真正原因進 Seq/console 供排查。
- 風險：低。不影響成功路徑;失敗診斷改由 log 取得。

## AD-003 🟠：usage_log `create_task` fire-and-forget 漏記帳

### 問題

`schedule_usage_log` 用 `asyncio.create_task(_task())` 但回傳無人持有 reference。CPython 文件明載 event loop 只持 task 的 weak reference,無強引用者可能在完成前被 GC 靜默取消 → `usage_logs` 隨機漏寫(對以計費/用量為核心的閘道是資料正確性問題)。串流路徑同樣經此函式。

### 修正

[proxy.py](backend/app/services/proxy.py)：新增 module-level `_usage_log_tasks: set`，建立後 `add` 持強引用、`add_done_callback(discard)` 完成移除。

## AD-007 🔵：OpenRouter Key failover 迴圈內 N+1 重查全表

### 問題

非串流(`run_chat`)與串流(`stream`)兩條 OR 路徑的 failover 迴圈,每圈呼叫 `pick_random_active` → 重查整張 `openrouter_keys`(最多 5 次)。internal 路徑早已是「迴圈外查一次、記憶體 shuffle」。

### 修正（記憶體預取,非 Redis)

[proxy.py](backend/app/services/proxy.py)：兩處改為迴圈外 `OpenRouterKeyRepository(db).list_active_by_department()` 查一次,`random.sample(keys, len(keys))[:_MAX_RETRIES]` 記憶體內 shuffle 後依序取,移除 per-iteration 查詢與 `tried` 排除集合。

> **設計討論**:此處只是「同一請求內重複查同一張表」,把結果存進區域變數即可,**非跨 worker 共享狀態**,故用記憶體預取而非 Redis。Redis 留給真正需要跨 worker 一致的項目(M3 多 worker 速率限制、AD-006 per-caller 配額、壞 key cooldown)——本批經討論**暫不導入 Redis**。

## R-LOG-006 🔵：新增 `/api/v1/version` 端點

### 修正

- [config.py](backend/app/core/config.py)：新增 `APP_VERSION`(預設 `1.10.0`)作為部署版本標記;[.env.example](.env.example) 同步。
- [health.py](backend/app/api/v1/health.py)：新增 `version_router`,`GET /api/v1/version` 回 `{version, app}`;[api/v1/__init__.py](backend/app/api/v1/__init__.py) 註冊。

## AD-008 🔵：`api_key_requests.status` server_default 對齊狀態機

### 問題

DB 欄位 DEFAULT 為 `pending`,但 v1.9.1 狀態機無此值(`manual_pending` 才是初始態);0013 只改了既有資料、未改欄位 DEFAULT。

### 修正

- [models/api_key_request.py](backend/app/models/api_key_request.py)：`server_default="pending"` → `"manual_pending"`。
- 新增 migration [0016_api_key_request_status_default.py](backend/alembic/versions/0016_api_key_request_status_default.py)：`ALTER COLUMN status SET DEFAULT 'manual_pending'`(僅變更 DEFAULT,不動既有資料)。

---

## 本輪掃描報告處理進度小結

| 項目 | 嚴重度 | 狀態 |
| --- | --- | --- |
| R-BE-008 CORS 回退 | 🔴 | ✅ |
| R-BE-020 prod fail-fast | 🟠 | ✅ |
| AD-002 併發送單 race | 🟠 | ✅ |
| R-BE-012 process 端點錯誤洩漏 | 🟠 | ✅ |
| AD-003 usage_log 漏記帳 | 🟠 | ✅ |
| AD-004 SSE relay 非 OR 收尾 | 🟡 | ✅ |
| AD-005 prompt at-rest PII | 🟡 | ⏸ 暫維持現狀(使用者決策 2026-06-22) |
| AD-006 per-caller 配額 | 🟡 | ⏸ 待 Redis 任務 |
| R-LOG-006 version 端點 | 🔵 | ✅ |
| AD-007 failover N+1 | 🔵 | ✅ |
| AD-008 status 預設值 | 🔵 | ✅ |
| AD-001 SDK Key 明文 | 🟠 | ⏸ 暫維持現狀(使用者決策 2026-06-22,已文件化取捨) |

## AD-004 🟡：SSE 串流非 OpenRouterError 例外不補送收尾

### 問題

relay 階段只 `except OpenRouterError`。串流中途若發生非 OR 例外(httpx `ReadError`、`asyncio.TimeoutError` 等),不送 `error chunk + [DONE]` → SSE 客戶端無預警截斷、等不到結束而 hang;另 `finally` 的 `agen.aclose()` 若自身拋例外會蓋掉記帳。

### 修正

[proxy.py](backend/app/services/proxy.py)：
- relay `try` 新增泛型 `except Exception` 分支,非 OR 例外同樣補送 `{"error":"stream_incomplete"}` + `[DONE]`(`CancelledError` 屬 BaseException 不落此分支,呼叫端斷線交 finally 記帳後自然傳播)。
- `finally` 的 `agen.aclose()` 包 `try/except`,確保其失敗不影響下方 `schedule_usage_log` 記帳。

## 維持現狀(使用者決策 2026-06-22)

- **AD-001**(SDK Key 明文存 DB,🟠):已簽核取捨,暫維持現狀。
- **AD-005**(prompt / images 全文落地 `usage_logs`,🟡):暫維持現狀。
- **AD-006 / M3 / 壞 key cooldown**:歸入未來 Redis 任務,本批不導入 Redis。
