# 03-backend — 後端入口 + 風格地板

鎖定 **Python 3.14 + FastAPI + SQLAlchemy 2 async + Pydantic 2 + Alembic + uv + httpx + `pyjwt` + `argon2-cffi`(argon2id)**。本專案密碼雜湊用 **argon2id**(`argon2-cffi`),**不**用 `passlib[bcrypt]`;log 走 **Seq**(`seqlog`)。版本見 `00-overview/01-versions.md`。

> **永遠讀**:本檔為任何後端任務都必遵守的「風格地板」(分層 / 命名 / 型別 / 註解)。子任務專屬規則見對應子檔。

> **變更紀錄**
> - 2026-07-07:命名 + 型別段新增「禁方法名遮蔽 Python 內建型別 / 函式」規則(基於 fixed.md v2.1 §1 / §4 / §7,`list` 遮蔽第 4 次復發;reflect-report-260707051743 候選 1)。既有 8 repo 的 `list` 方法 **grandfather**,僅規範本日之後新增方法。

---

## 分層(永遠遵守)

```
api → services → repositories → models
        ↓
     clients(第三方)
```

**禁**跨層(api 直 import repository、service 直寫 raw SQL)。`clients/` 只由 `services` 呼叫;第三方錯誤須轉 `AppError`。

## 命名(永遠遵守)

| 對象 | 慣例 | 範例 |
| --- | --- | --- |
| 模組 / 檔案 | snake_case | `account_service.py` |
| 類別 | PascalCase | `AccountService` |
| 函式 / 變數 | snake_case | `get_account_by_uid` |
| 常數 | SCREAMING_SNAKE | `MAX_RETRY_COUNT` |
| API 路徑 | kebab-case 複數 | `/api/v1/user-groups` |
| 環境變數 | SCREAMING_SNAKE | `JWT_SECRET_KEY` |
| Pydantic schema | PascalCase + 後綴 | `AccountCreateRequest` / `UserResponse` |

- **禁方法名遮蔽 Python 內建型別 / 函式**(`list` / `dict` / `set` / `type` / `id` / `filter` / `map` …):class 方法名一旦與內建同名,會使該 class scope 內所有 `-> list[...]` 等裸內建標註觸 mypy `valid-type` 假錯並連坐呼叫端(見 fixed.md v2.1 §7)。**新增**的 repository / service 分頁查詢方法一律用 `list_page` / `list_paged`(**禁** `list`)。既有 8 repo 的 `list` 為 grandfather 慣例(2026-07-07 前),遷移走獨立清債 task,不在此強制。

## 型別(永遠遵守)

- 函式**必**標參數+回傳型別
- **禁** `Any`(異質容器用 `object`,DB session 用 `AsyncSession`)
- **禁** `typing.List` / `typing.Dict` → `list[...]` / `dict[...]`
- 若方法名不得已遮蔽內建型別(grandfather 的 `list` 等),該 class 內的回傳標註**必**用完整限定 `builtins.list[...]` 迴避遮蔽假錯(對齊 fixed.md v2.1 §7);新碼應循上段直接改名避免遮蔽。

## 註解

不主動加;只在 *why* 從程式碼難推斷時加。

---

## 子章節(依子任務載入)

- `01-routing.md` — 路由 + ApiResponse 外殼 + Pydantic schema
- `02-auth.md` — JWT cookie + Depends + CORS
- `03-async-and-tx.md` — async safety + 多表 transaction
- `04-config.md` — Settings + fail-fast + lifespan
- `05-exceptions-and-logging.md` — 3 個 handler + 結構化 log
- `06-clients.md` — clients/* 結構(細節見 `90-third-party-service/`)
- `07-testing.md` — 真 DB + respx
- `08-performance.md` — N+1 / async 阻塞
