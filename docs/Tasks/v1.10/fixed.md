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
