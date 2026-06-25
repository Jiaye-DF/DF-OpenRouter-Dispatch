# 80 · 權限設計（本專案特定）

本文件定義 **DF-OpenRouter-Dispatch 專案**的權限模型與存取規則。與其他 Design-Base 文件不同，**此檔為專案特定規則**，其他專案沿用本 Base 結構時**必須**替換本檔內容。

## 1. 主體類型

本平台存在兩種 API 呼叫主體，**必須**嚴格分離：

| 主體 | 認證方式 | 使用端點 | 典型情境 |
| --- | --- | --- | --- |
| 管理使用者（User） | 平台自簽 JWT Cookie（本地登入，見 [70-auth.md](../03-backend/91-project-auth.md)） | `/api/v1/*`（管理 API） | Web 管理介面操作 |
| SDK 呼叫端（Proxy Caller） | `X-SDK-Key`（部門識別，argon2 hash 比對）+ `X-User-Token`（AES-256-GCM 加密使用者身分）**雙因子** | `/api/v1/model/openrouter/*`（代理端點） | 使用者應用 / SDK 呼叫模型 |

- 管理 API 與代理 API **禁止**共用認證；代理端點**禁止**接受 Cookie，管理端點**禁止**接受 `X-SDK-Key` / `X-User-Token`。
- SDK Key 與 User Token **兩者缺一不可**；下列任一條件不成立 → **一律** 401 `unauthorized`，**禁止**分別揭露哪一項失敗：
  1. `X-SDK-Key` 存在且能以 prefix + argon2 比對成功。
  2. `X-User-Token` 存在且能以 `ENCRYPTION_KEY` 解密、payload 結構合法。
  3. User Token 的 `issued_at` 晚於或等於該 user 最近一次撤銷時間（`user_tokens_revocations.revoked_issued_at`）。
  4. **SDK 所屬 `department_uid` 與 User Token payload 中的 `department_uid` 一致**（部門一致性檢查）。
- 管理 API 的 `/me` 回傳 `Actor` + `role`；代理端點的 context 以 `SdkCallerContext`（`department_uid` / `user_uid` / `employee_id` / `email`）為主。

## 2. 角色定義

管理使用者僅有兩種角色，不做細粒度 RBAC：

| 角色 | 代號 | 判定依據 | 權限範圍摘要 |
| --- | --- | --- | --- |
| 管理員 | `admin` | `user.role = 'admin'` | 全平台使用者管理、所有部門 / 專案 / OpenRouter Key / SDK Key / 使用者 Token / 用量 / 稽核 / 系統設定 |
| 一般使用者 | `user` | 其他所有已登入使用者 | 僅查看自身部門下的部門資訊、專案、自身用量 |

- 第一位 admin 由 Migration Seed 建立（`INITIAL_ADMIN_ACCOUNT` / `INITIAL_ADMIN_USERNAME` / `INITIAL_ADMIN_PASSWORD` 注入），後續 admin 由既有 admin 於後台指派。
- 角色儲存於 `users.role`；**禁止**於 JWT Claim 中固化 role，**必須**每次請求從 DB 即時讀取，確保降級立即生效。

## 3. 判定流程

```
┌──────────────────────────────────────────────────────┐
│ Management Request (帶登入 Cookie)                    │
└───────────────────┬──────────────────────────────────┘
                    ▼
          FastAPI Depends(require_user)
                    │  驗證 JWT / Session → 取 user_uid
                    │  由 DB 讀取 user（含 role）
                    ▼
                 Actor(
                   user_uid, account, username, email,
                   role: "admin" | "user",
                   department_uid,
                 )
                    ▼
     各 router 依 role 決定資料範圍 / 動作許可
```

```
┌─────────────────────────────────────────────────────────────┐
│ Proxy Request (Headers: X-SDK-Key, X-User-Token)            │
└───────────────────┬─────────────────────────────────────────┘
                    ▼
          FastAPI Depends(require_sdk_caller)
                    │  1. prefix 候選 + argon2 比對 sdk_api_keys
                    │  2. AES-256-GCM 解密 User Token、驗 payload、驗 revocation
                    │  3. 比對 SDK.department_uid == UserToken.department_uid
                    ▼
                 SdkCallerContext(
                   department_uid, department_code,
                   user_uid, employee_id, email,
                   sdk_api_key_uid,
                 )
                    ▼
     proxy router 將請求轉至 OpenRouterClient
```

- `Actor` 與 `SdkCallerContext` 均為 Pydantic 模型，置於 `backend/app/schemas/`，**禁止**在各 router 自行解析 token。
- 兩個 Dependency 皆封裝於 `backend/app/core/deps.py`。

## 4. 管理端資源存取規則

| 資源 | Admin | User |
| --- | --- | --- |
| 使用者 CRUD / 重設密碼 | ✅ | ❌（僅可改自己密碼） |
| 自己帳號資料 / 密碼 | ✅ | ✅ |
| 部門 / 專案 列表 | ✅（全部） | ✅（僅自身部門） |
| 部門 / 專案 CRUD | ✅ | ❌ |
| OpenRouter Key CRUD | ✅ | ❌ |
| SDK Key CRUD | ✅ | ❌ |
| 使用者 Token 產生 / 撤銷 | ✅ | ❌ |
| 所有用量 / 成本統計 | ✅ | ❌ |
| 自身部門用量 / 個人用量 | ✅ | ✅ |
| 系統稽核 Log | ✅ | ❌ |
| 模型 CRUD-lite（toggle / tier） | ✅ | ❌（僅讀已啟用） |
| 模型分級（model_tiers）CRUD | ✅ | ❌（可讀，UI 顯示徽章用） |
| OpenRouter 餘額欄位 | ✅ | ❌ |

- 查詢端點**必須**在 service 層套用 `if not actor.is_admin: query.where(department_uid == actor.department_uid)`，**禁止**前端過濾。

## 5. 代理端（Proxy）存取規則

代理端以「部門」為資源邊界；權限與限制由部門層級的 SDK Key、OpenRouter Key、全域白名單決定：

| 配置 | 意義 |
| --- | --- |
| `sdk_api_keys.is_active` | 停用後任何呼叫均 401 |
| `openrouter_keys.is_active` | 停用後該把不被選中；全部停用 → 502 `openrouter_unavailable` |
| `models.is_active` | 全域控管；模型停用或不存在均拒絕呼叫 |
| `user_tokens_revocations` | 撤銷某時間前簽發的全部 User Token |

- 本版本**不**實作配額（日 / 月 tokens / cost）；後續版本得擴充。
- 白名單檢查**必須**在呼叫 OpenRouter **之前**完成；拒絕時回 403 `model_forbidden`，**不得**計入 OpenRouter 用量。

## 6. 權限檢查抽象（FastAPI 實作）

所有權限檢查**必須**透過 Dependency 完成，**禁止**在 router / service 內寫 `if actor.role != "admin": raise ...` 之類的散落檢查。

### 6.1 Actor 與 SdkCallerContext Schema

```python
# backend/app/schemas/actor.py
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

Role = Literal["admin", "user"]


class Actor(BaseModel):
    user_uid: UUID
    account: str
    username: str
    email: str | None = None
    role: Role
    department_uid: UUID | None = None

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


class SdkCallerContext(BaseModel):
    sdk_api_key_uid: UUID
    department_uid: UUID
    department_code: str
    user_uid: UUID
    employee_id: str | None = None
    email: str | None = None
```

### 6.2 Dependencies

```python
# backend/app/core/deps.py
from fastapi import Depends

from app.core.exceptions import AppError
from app.schemas.actor import Actor, SdkCallerContext


async def require_user(...) -> Actor: ...


def require_admin(actor: Actor = Depends(require_user)) -> Actor:
    if not actor.is_admin:
        raise AppError("forbidden", code=403)
    return actor


async def require_sdk_caller(...) -> SdkCallerContext: ...
```

### 6.3 路由使用方式

```python
@router.get("/departments")
async def list_departments(actor: Actor = Depends(require_user)):
    """一般使用者只看到自己部門；管理員看到全部。"""
    ...


@router.delete("/users/{uid}")
async def delete_user(
    uid: UUID,
    actor: Actor = Depends(require_admin),
):
    ...


@router.post("/model/chat")  # v1.2 canonical;舊 /model/openrouter/chat 為 deprecated alias
async def proxy_chat(
    ctx: SdkCallerContext = Depends(require_sdk_caller),
):
    ...
```

## 7. 前端顯示規則

- 前端**禁止**在客戶端自行判斷 role 來決定資料可見性；所有過濾**必須**由後端完成。
- 前端**可**依 `/api/v1/auth/me` 回傳的 `role` 欄位決定**按鈕顯示 / 隱藏**（UX 提示），但即使按鈕被繞過，後端仍會以 403 回絕。

## 8. 錯誤處理對照

| 情境 | HTTP | `detail` | 備註 |
| --- | --- | --- | --- |
| 未登入（管理端） | 401 | `unauthorized` | 由 `require_user` 擋下 |
| SDK Key 無效 / User Token 解密失敗 / 部門不一致 / Token 已撤銷（代理端） | 401 | `unauthorized` | 由 `require_sdk_caller` 擋下，**禁止**分別揭露具體原因 |
| 已登入但非 admin | 403 | `forbidden` | 由 `require_admin` 擋下 |
| User 存取他部門資源 | 403 | `forbidden` | service 層以 `department_uid` 比對 |
| 模型不在白名單 | 403 | `model_forbidden` | 由代理端於呼叫 OpenRouter 前擋下 |
| 所有部門 OpenRouter Key 均失效 | 502 | `openrouter_unavailable` | 由代理端於重試耗盡後回報 |

## 9. 稽核 Log

管理員操作（建立 / 修改 / 停用 / 刪除 / 重設密碼 / 產生 Token / 撤銷 Token）**必須**寫入稽核 Log，欄位至少包含：

```
user_uid         # 操作者
actor_role       # 操作者角色
action           # e.g. "create_user", "revoke_user_token", "create_openrouter_key"
target_type      # e.g. "user", "user_token", "openrouter_key"
target_uid       # UUID
result           # "success" | "failure"
detail           # 失敗原因或額外資訊
ip               # 來源 IP
created_at
```

代理端呼叫的業務紀錄寫入 `usage_logs`（詳見 [50-openrouter.md § 10](../90-third-party-service/50-openrouter.md#10-用量紀錄usage-log)），**不**重複寫入稽核表，但兩者**應**可透過 `user_uid` + 時間範圍交叉查詢。

## 10. 禁止事項

- **禁止**將管理端認證（Cookie）與代理端認證（`X-SDK-Key` + `X-User-Token`）混用。
- **禁止**在 JWT Claim 或 Cookie 中存放 role（應每次請求即時解析）。
- **禁止**在 Response、Log、Commit 中出現 SDK Key 明文、User Token 明文、OpenRouter Key 明文或其 hash；Log 僅可記錄 UID 或 prefix。
- **禁止**前端自行決定資料可見性；所有過濾一律由後端完成。
- **禁止**在代理端回應中分別揭露「SDK Key 無效」「Token 解密失敗」「部門不一致」中的具體項目；一律 401 `unauthorized`。
- **禁止**在沒有 admin 稽核紀錄的情況下調整他人資源或撤銷 Token。
