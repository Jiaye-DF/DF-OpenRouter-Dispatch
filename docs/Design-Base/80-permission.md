# 80 · 權限設計（本專案特定）

本文件定義 **DF-OpenRouter-Dispatch 專案**的權限模型與存取規則。與其他 Design-Base 文件不同，**此檔為專案特定規則**，其他專案沿用本 Base 結構時**必須**替換本檔內容。

## 1. 主體類型

本平台存在兩種 API 呼叫主體，**必須**嚴格分離：

| 主體 | 認證方式 | 使用端點 | 典型情境 |
| --- | --- | --- | --- |
| 管理使用者（User） | 平台自簽 JWT Cookie（本地登入，見 [70-auth.md](./70-auth.md)） | `/api/v1/*`（管理 API） | Web 管理介面操作 |
| 本地金鑰（API Key） | `Authorization: Bearer ord_*` | `/api/v1/proxy/*`（代理端點） | 使用者應用呼叫模型 |

- 管理 API 與代理 API **禁止**共用認證；代理端點**禁止**接受 Cookie，管理端點**禁止**接受 `ord_*` 金鑰。
- 管理 API 的 `/me` 回傳 `Actor` + `role`；代理端點的 context 以 `ApiKey` + 其 `owner_user` 為主。

## 2. 角色定義

管理使用者僅有兩種角色，不做細粒度 RBAC：

| 角色 | 代號 | 判定依據 | 權限範圍摘要 |
| --- | --- | --- | --- |
| 管理員 | `admin` | `user.role = 'admin'` | 全平台使用者管理、所有金鑰、配額、用量、稽核、系統設定 |
| 一般使用者 | `user` | 其他所有已登入使用者 | 僅管理自己名下金鑰、查看自己的用量與稽核 |

- 第一位 admin 由 Migration Seed 建立（帳號 / 密碼由環境變數 `INITIAL_ADMIN_USERNAME` / `INITIAL_ADMIN_PASSWORD` 注入），後續 admin 由既有 admin 於後台指派。
- 角色儲存於 `user.role` 欄位；**禁止**於 JWT Claim 中固化 role，**必須**每次請求從 DB 即時讀取，確保降級立即生效。

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
                   user_uid, email, name,
                   role: "admin" | "user",
                 )
                    ▼
     各 router 依 role 決定資料範圍 / 動作許可
```

```
┌──────────────────────────────────────────────────────┐
│ Proxy Request (帶 Authorization: Bearer ord_*)        │
└───────────────────┬──────────────────────────────────┘
                    ▼
          FastAPI Depends(require_api_key)
                    │  比對 hash → api_key + owner user
                    │  檢查 is_active、白名單、配額
                    ▼
                 ApiKeyContext(
                   api_key_uid, user_uid,
                   allowed_models, quota,
                 )
                    ▼
          proxy router 將請求轉至 OpenRouterClient
```

- `Actor` 與 `ApiKeyContext` 均為 Pydantic 模型，置於 `backend/app/schemas/`，**禁止**在各 router 自行解析 token。
- 兩個 Dependency 皆封裝於 `backend/app/core/deps.py`。

## 4. 管理端資源存取規則

| 資源 | Admin | User |
| --- | --- | --- |
| 使用者列表 / 建立 / 停用 | ✅ | ❌ |
| 自己帳號資料 / 密碼 | ✅ | ✅ |
| 所有本地金鑰列表 | ✅ | ❌ |
| 自己的本地金鑰（建立 / 停用 / 撤銷） | ✅ | ✅ |
| 配額設定（建立 / 修改） | ✅ | ❌（僅可檢視自身配額） |
| 模型白名單（全域） | ✅ | ❌ |
| 所有用量 / 成本統計 | ✅ | ❌ |
| 自己名下金鑰的用量 | ✅ | ✅ |
| 系統稽核 Log | ✅ | ❌ |

- 查詢端點**必須**在 service 層套用 `if not actor.is_admin: query.where(owner_user_uid == actor.user_uid)`，**禁止**前端過濾。

## 5. 代理端（Proxy）存取規則

代理端以「金鑰」為邊界，權限由金鑰本身配置：

| 配置 | 意義 |
| --- | --- |
| `allowed_models` | 模型白名單（為空代表套用全域預設） |
| `daily_request_limit` / `monthly_request_limit` | 請求數配額 |
| `monthly_token_limit` | Token 配額（prompt + completion） |
| `monthly_cost_limit_usd` | 金額配額 |
| `is_active` | 停用後任何呼叫均 401 |

- 配額檢查**必須**在呼叫 OpenRouter **之前**完成；拒絕時回 429 `quota_exceeded`，**不得**計入 OpenRouter 用量。
- 超額後可於下一計費週期自動恢復；手動調整需透過管理 API 並寫入稽核。

## 6. 權限檢查抽象（FastAPI 實作）

所有權限檢查**必須**透過 Dependency 完成，**禁止**在 router / service 內寫 `if actor.role != "admin": raise ...` 之類的散落檢查。

### 6.1 Actor 與 ApiKeyContext Schema

```python
# backend/app/schemas/actor.py
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

Role = Literal["admin", "user"]


class Actor(BaseModel):
    user_uid: UUID
    email: str
    name: str
    role: Role

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


class ApiKeyContext(BaseModel):
    api_key_uid: UUID
    user_uid: UUID
    allowed_models: list[str]
    is_active: bool
```

### 6.2 Dependencies

```python
# backend/app/core/deps.py
from fastapi import Depends

from app.core.exceptions import AppError
from app.schemas.actor import Actor, ApiKeyContext


async def require_user(...) -> Actor: ...


def require_admin(actor: Actor = Depends(require_user)) -> Actor:
    if not actor.is_admin:
        raise AppError("forbidden", code=403)
    return actor


async def require_api_key(...) -> ApiKeyContext: ...
```

### 6.3 路由使用方式

```python
@router.get("/api-keys")
async def list_api_keys(actor: Actor = Depends(require_user)):
    """一般使用者只看到自己的金鑰；管理員看到全部。"""
    ...


@router.delete("/users/{uid}")
async def delete_user(
    uid: UUID,
    actor: Actor = Depends(require_admin),
):
    ...


@router.post("/proxy/chat/completions")
async def proxy_chat(
    ctx: ApiKeyContext = Depends(require_api_key),
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
| 金鑰無效 / 停用（代理端） | 401 | `unauthorized` | 由 `require_api_key` 擋下，**禁止**洩漏「金鑰已撤銷」或「金鑰不存在」的具體區別 |
| 已登入但非 admin | 403 | `forbidden` | 由 `require_admin` 擋下 |
| User 存取他人資源 | 403 | `forbidden` | service 層以 `owner_user_uid` 比對 |
| 配額耗盡 | 429 | `quota_exceeded` | 由代理端於呼叫 OpenRouter 前擋下 |
| 模型不在白名單 | 403 | `model_forbidden` | 由代理端於呼叫 OpenRouter 前擋下 |

## 9. 稽核 Log

管理員操作（建立 / 修改 / 停用 / 刪除 / 調整配額）**必須**寫入稽核 Log，欄位至少包含：

```
user_uid         # 操作者
actor_role       # 操作者角色
action           # e.g. "revoke_api_key"
target_type      # e.g. "api_key"
target_uid       # UUID
result           # "success" | "failure"
detail           # 失敗原因或額外資訊
ip               # 來源 IP
created_at
```

代理端呼叫的業務紀錄寫入 `usage_logs`（詳見 [50-openrouter.md § 10](./50-openrouter.md#10-用量紀錄usage-log)），**不**重複寫入稽核表，但兩者**應**可透過 `user_uid` + 時間範圍交叉查詢。

## 10. 禁止事項

- **禁止**將管理端認證（Cookie）與代理端認證（`ord_*` 金鑰）混用。
- **禁止**在 JWT Claim 或 Cookie 中存放 role（應每次請求即時解析）。
- **禁止**在 Response、Log、Commit 中出現金鑰明文或 hash；Log 僅可記錄 `api_key_uid` 或 prefix。
- **禁止**前端自行決定資料可見性；所有過濾一律由後端完成。
- **禁止**代理端於「配額不足」時仍送請求到 OpenRouter 再事後扣除——**必須**預先擋下。
- **禁止**在沒有 admin 稽核紀錄的情況下調整他人配額。
