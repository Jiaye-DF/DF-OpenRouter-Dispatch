---
id: task-523
title: S3 client(app/clients/s3/)+ boto3 鎖版 + 短 timeout + presign
status: pending
parallel: true
depends_on: [task-521, task-522]
affected_files:
  - backend/app/clients/s3/__init__.py
  - backend/app/clients/s3/client.py
  - backend/app/clients/s3/errors.py
  - backend/app/clients/s3/README.md
  - backend/pyproject.toml
  - docs/Design-Base/00-overview/01-versions.md
  - backend/tests/clients/test_s3_client.py
estimated_hours: 3
---

## 目標

新增 S3 物件儲存 client,提供上傳 / 簽發短期讀取 URL / 刪除 / 存在檢查四項能力,作為 524（附件落地層）與 530/531（遷移 script）的共同底層(propose §B.1)。

## 範圍(只做這些)

- 目錄結構依 [`90-third-party-service/00-overview.md § 集中位置`](../../../Design-Base/90-third-party-service/00-overview.md):`client.py`(`S3Client`)/ `errors.py`(`S3Error` + `S3UploadError` / `S3NotFoundError`)/ `README.md`(quirk 紀錄)/ `__init__.py`。
- 能力四項:
  - `put_object(key: str, body: bytes, content_type: str) -> None`
  - `presign_get(key: str, ttl: int) -> str`
  - `delete_object(key: str) -> None`
  - `head_object(key: str) -> bool`(存在檢查;530 / 531 的冪等與安全網靠它)
- **boto3 同步 SDK → 全部呼叫以 `asyncio.to_thread` 包裹**(D.1;對齊 [`03-backend/03-async-and-tx.md`](../../../Design-Base/03-backend/03-async-and-tx.md) 與 [`08-performance.md`](../../../Design-Base/03-backend/08-performance.md))。**禁**在 async 函式內直接呼叫 boto3。
- **短 timeout + 低重試上限**(D.5):`botocore.config.Config(connect_timeout=…, read_timeout=…, retries={"max_attempts": …})`,秒級 timeout、重試 ≤ 1 次。理由:上傳失敗不擋請求,但**會拖延遲**,必須有硬上限。
- **錯誤轉換契約**:`botocore.exceptions.*` / `ClientError` 一律轉 `S3Error` 子類,**禁**讓原生 exception 流到 service / api 層。
- **機密不入 log**:log 只記 bucket / key / 錯誤碼,**禁**記憑證;必要時金鑰只留前後 4 字元。
- 依賴管理:`backend/pyproject.toml` 加 `boto3`(鎖到 patch),並同步 [`00-overview/01-versions.md`](../../../Design-Base/00-overview/01-versions.md) 的版本鎖清單(該檔**只有本 task 動**,不與 521 互鎖)。
- `README.md` 記錄 quirk:presigned URL 權限繼承簽發者 IAM、Block Public Access 開啟仍可用 presigned、SigV4 TTL 上限 7 天。

## 不做

- **不**接線 proxy(525 的事)、**不**寫附件落地邏輯(524 的事)、**不**寫遷移 script(530 的事)。
- **不**做 MinIO / GCS 抽象層(propose Out of Scope)。

## 錯誤處理對照表

| 情境 | boto3 原生 | 轉成 | 上層行為 |
| --- | --- | --- | --- |
| 憑證錯 / 無權限 | `ClientError` (403 / `AccessDenied`) | `S3UploadError` | 524 記 `upload_failed` + log,不擋請求 |
| bucket 不存在 | `ClientError` (`NoSuchBucket`) | `S3UploadError` | 同上 |
| 物件不存在 | `ClientError` (404) | `head_object` 回 `False`(不拋) | 531 跳過該列 |
| 連線 / 讀取逾時 | `ConnectTimeoutError` / `ReadTimeoutError` | `S3UploadError` | 同上,且不重試超過上限 |
| 其他未預期 | `BotoCoreError` | `S3Error` | 同上 |

## Acceptance

- [ ] `[ -f backend/app/clients/s3/client.py ] && [ -f backend/app/clients/s3/errors.py ] && [ -f backend/app/clients/s3/README.md ]` 為真
- [ ] `cd backend && uv run pytest tests/clients/test_s3_client.py` 全綠,且測試涵蓋:put / presign / delete / head 四能力、403 與逾時各自轉成 `S3UploadError`、`head_object` 對 404 回 `False` 不拋
- [ ] **無阻塞**:`grep -n "boto3\|client\." backend/app/clients/s3/client.py` 顯示所有 boto3 呼叫皆在 `asyncio.to_thread(...)` 內(以測試斷言或 code review checklist 佐證);`grep -c "to_thread" backend/app/clients/s3/client.py` **≥ 4**
- [ ] **timeout 有硬上限**:`grep -q "connect_timeout" backend/app/clients/s3/client.py && grep -q "max_attempts" backend/app/clients/s3/client.py`
- [ ] **錯誤不外洩**:`grep -rn "botocore" backend/app/services/ backend/app/api/` **無任何輸出**(原生 exception 未流出 client 層)
- [ ] `grep -q "boto3" backend/pyproject.toml && grep -q "boto3" docs/Design-Base/00-overview/01-versions.md`
- [ ] `cd backend && uv sync && uv run ruff check app/clients/s3 && uv run mypy app/clients/s3` 全綠
- [ ] 測試**不打真 AWS**:`grep -rn "amazonaws.com" backend/tests/clients/test_s3_client.py` 僅出現在 mock / stub 設定中(或無輸出)

## 必讀檔(Just-in-time)

- `docs/Design-Base/90-third-party-service/00-overview.md`
- `docs/Design-Base/90-third-party-service/01-client-design.md`
- `docs/Design-Base/90-third-party-service/09-object-storage.md`(**由 task-521 建立,本 task 為其首個實作者**)
- `docs/Design-Base/03-backend/06-clients.md`
- `docs/Design-Base/03-backend/03-async-and-tx.md`
- `docs/Design-Base/03-backend/08-performance.md`
- `docs/Design-Base/03-backend/05-exceptions-and-logging.md`
- `docs/Design-Base/00-overview/01-versions.md`
- `docs/Design-Base/00-overview/02-secrets.md`
