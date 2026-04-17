# 20 · 後端基本設計

本文件定義後端（FastAPI / Uvicorn / Pydantic / SQLAlchemy）不隨版本異動的基礎規範。技術棧版本詳見 [00-overview.md § 技術棧](./00-overview.md#技術棧)。資料表與 Migration 規範獨立於 [30-database.md](./30-database.md)。

## 目錄結構

```
backend/app
├── api/v1/              # 路由層（每個資源一個檔案）
├── clients/             # 外部服務 client（openrouter, ...）
├── core/
│   ├── config.py        # pydantic-settings
│   ├── deps.py          # 依賴注入（require_user, get_db, ...）
│   ├── exceptions.py    # AppError
│   └── response.py      # ApiResponse helpers
├── models/              # SQLAlchemy ORM Model
├── repositories/        # 資料存取層（封裝 query）
├── schemas/             # Pydantic Request / Response schema
├── services/            # 業務邏輯
└── main.py              # FastAPI 入口（指定 docs_url="/api/docs"）
```

**分層原則：** `api` → `services` → `repositories` → `models`。上層**禁止**跨層呼叫下下層。

## 1. 統一 Response 格式

**所有** API 回應（含錯誤）**必須**符合以下結構：

```python
class ApiResponse(BaseModel, Generic[T]):
    success: bool           # 業務是否成功
    code: int               # HTTP 狀態碼 或 業務錯誤碼
    data: T | None = None   # 成功時的資料
    detail: str = ""        # 面向使用者的簡要訊息
```

### 成功範例（HTTP 200）

```json
{
  "success": true,
  "code": 200,
  "data": { "id": 1, "name": "api-key-001" },
  "detail": "success"
}
```

### 失敗範例（HTTP 400 / 401 / 403 / 404 / 500）

```json
{
  "success": false,
  "code": 400,
  "data": null,
  "detail": "欄位 name 不符合格式"
}
```

### 實作位置

- 統一封裝於 `backend/app/core/response.py`
- 提供 `success(data=None, detail="success")` 與 `failure(code, detail)` 兩個 helper
- 自訂例外 `AppError(detail, code)` 於 `backend/app/core/exceptions.py`
- 於 `backend/app/main.py` 註冊 `exception_handler`：
  - `AppError` → 對應 `code` 的 HTTP 狀態 + `ApiResponse`
  - `RequestValidationError` → HTTP 400 + 將 Pydantic 錯誤轉為使用者友善訊息
  - `Exception`（未捕捉） → HTTP 500 + `detail="操作失敗"`

### 串流端點（SSE / chunked）例外

模型串流回應（如 OpenRouter `stream=true`）屬例外，**允許**以 SSE 或 chunked text 回傳原始 chunk，**不**包在 `ApiResponse` 內；但起始錯誤（驗證失敗、配額不足、OpenRouter 拒絕）**必須**在第一個 chunk 前以 HTTP 4xx/5xx + `ApiResponse` 回絕。詳見 [50-openrouter.md](./50-openrouter.md)。

## 2. 錯誤訊息規範

**禁止**在 `detail` 欄位洩漏以下內容：

- SQL 語法 / 資料表結構 / 欄位名稱（英文欄位名除非業務必要）
- Python traceback / function 名稱 / 檔案路徑
- 第三方服務的原始錯誤字串（例 OpenRouter 的 raw response）
- 連線字串、Token、API Key 等任何敏感資訊

**允許**的 `detail` 範例：

| 情境 | HTTP | detail 範例 |
| --- | --- | --- |
| 欄位驗證失敗 | 400 | `欄位 model 不符合格式` |
| 未帶 token | 401 | `unauthorized` |
| 權限不足 | 403 | `forbidden` |
| 資源不存在 | 404 | `資源不存在` |
| 業務規則違反 | 409 | `金鑰名稱已存在` |
| 配額耗盡 | 429 | `quota_exceeded` |
| 外部服務錯誤 | 502 | `openrouter_unavailable` |
| 未知錯誤 | 500 | **固定**使用 `操作失敗` |

完整原始錯誤一律寫入**後端 log**（使用 `logger.exception(...)`），**絕不**回傳給前端。呼叫 OpenRouter API 失敗時需保留原始錯誤訊息於 Log（含 `request_id`），但對前端隱藏內部細節。

## 3. 路由與 API 命名

- 所有 API **必須**以 `/api/v1` 為前綴。
- 路徑使用小寫、複數、連字號：`/api/v1/api-keys`、`/api/v1/usage-logs`。
- 單一資源使用 UID：`/api/v1/api-keys/{api_key_uid}`（對外識別規則詳見 [30-database.md](./30-database.md)）。
- 分頁查詢使用 query string：`?page=1&size=20`；回傳 `data: { items, total, page, size }`。
- FastAPI 路由依資源分檔放置於 `app/api/v1/`，每個資源對應一個 router。
- 商業邏輯集中於 `app/services/`，外部服務呼叫集中於 `app/clients/<service>/`，**禁止**重複實作。
- Pydantic Schema 放置於 `app/schemas/`，Request / Response 模型分離。

## 4. Swagger 文件

- 位於 `/api/docs`（強制規範於 [CLAUDE.md](../../CLAUDE.md)），**禁用** `/swagger`、`/docs`、`/openapi` 等其他路徑。
- FastAPI 初始化時**必須**明確指定 `docs_url="/api/docs"`。
- 每個路由**必須**提供 `summary` 與 `description`。
- Request / Response schema **必須**以 Pydantic 明確定義，**禁止**使用 `dict` 當 response type。

## 5. Logging

- 使用 Python 標準 `logging`，以 `logger = logging.getLogger(__name__)`。
- 格式：`%(asctime)s %(levelname)s [%(name)s] %(message)s`。
- 後端**應**使用結構化 Log（JSON），紀錄 `request_id`、`user_id`、`action`、耗時、狀態碼。
- **禁止** log 任何 API Key、密碼、Cookie 原始值；必要時以 `***` 遮罩，或只記錄前後 4 字元。
- 例外**必須**用 `logger.exception(...)` 紀錄 traceback。

## 6. CORS

- 僅允許 `CORS_ORIGINS` 環境變數明列的 origin。
- `allow_credentials=True`（cookie 需跨埠送達）。
- `allow_methods=["*"]`、`allow_headers=["*"]`。

## 7. 認證與安全

- 後端對外 API 使用 JWT / Session 驗證，前端透過 HttpOnly Cookie 保存登入狀態。
- OpenRouter API Key、資料庫連線字串、JWT Secret 等敏感資訊**必須**透過環境變數注入，**禁止**進入版控。
- 重要操作（建立 / 停用金鑰、修改配額、刪除使用者）**必須**記錄稽核 Log（`user_id`、`action`、`target`、`timestamp`）。
- 受保護 API **必須**透過 FastAPI `Depends(require_user)` 注入當前使用者。

## 8. Session 與 Transaction 規範

- `get_db()` 產生的 `AsyncSession` **不會自動 commit**；離開 context 後未 commit 的交易**自動 rollback**。
- Repository 層的寫入方法（`create`、`upsert`…）使用 `await session.flush()` 將 SQL 送達 DB，但 **flush ≠ commit**——資料尚未持久化。
- **呼叫端**（Dependency 或 Service 層）**必須**在所有寫入完成後顯式呼叫 `await db.commit()`。
- 批次任務（例：用量彙總）不走 FastAPI Dependency，**必須**自行建立 session 並在結束時 commit：

```python
async with SessionLocal() as session:
    repo = UsageRepository(session)
    await repo.aggregate_daily(...)
    await session.commit()
```

- **禁止**在 Repository 內部 commit（Repository 不知道呼叫端是否還有後續寫入）。

## 9. 連線池

- DB 連線使用 SQLAlchemy + asyncpg 連線池，**禁止**每請求建立連線。
- 外部 HTTP 呼叫（含 OpenRouter）使用共用 `httpx.AsyncClient`，設置逾時（模型同步呼叫**應**為 60 秒，串流另議）。

## 10. 測試

- 單元與整合測試使用 `pytest` + `pytest-asyncio`，位於 `backend/tests/`。
- 對 DB 的測試使用 **testcontainers 或獨立 test database**，**禁止** mock SQL 查詢。
- 外部服務（OpenRouter）使用 `respx` 或 httpx `MockTransport` stub。
- Critical Flow（登入、代理呼叫、配額扣減）**應**另行撰寫 E2E 測試。

## 11. Uvicorn 啟動

- 開發環境以 `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` 啟動，**僅限**容器內使用，**禁止**於正式環境開啟 `--reload`。
- 正式環境於 Dockerfile 的 `CMD` 中固定 worker 數（例 `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS}`），worker 數透過環境變數調整。
