# app/clients/s3 — S3 物件儲存 client

> 規範來源:[`docs/Design-Base/90-third-party-service/09-object-storage.md`](../../../../docs/Design-Base/90-third-party-service/09-object-storage.md)
> 建立版本:v2.2.1(task-523)

平台後端把圖片 / 檔案附件從 `usage_logs` 的 base64 改存 S3、DB 只留物件路徑,本 client 為
524(附件落地層)、527(明細頁 presigned URL)、530 / 531(遷移 script)的共同底層。

## 能力

| 方法 | 說明 |
| --- | --- |
| `put_object(key, body, content_type)` | 上傳物件(強制 `ServerSideEncryption=AES256`) |
| `presign_get(key, ttl)` | 簽發短期唯讀 URL(分鐘級 TTL) |
| `delete_object(key)` | 刪除物件 |
| `head_object(key) -> bool` | 存在檢查;**物件層級**不存在回 `False`,bucket 不存在則拋 |

四項皆為 `async`,內部一律 `asyncio.to_thread` 包裹 boto3(見下方「同步 SDK」)。

## bucket / region / 設定

由 `Settings`(`app/core/config.py`,task-522)注入,**禁**在本目錄寫死:

| env | 預設 | 說明 |
| --- | --- | --- |
| `S3_STORAGE_ENABLED` | `false` | 總開關;`false` 時 `get_s3_client()` 直接拋 `S3ConfigError` |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | 空 | 機密,env 注入;留空則回退 boto3 預設 credential chain |
| `AWS_REGION` | `ap-northeast-1` | |
| `S3_BUCKET` | `df-openrouter-dispatch-prod` | 單一 bucket(D.8) |
| `S3_KEY_PREFIX` | `dev` | dev / test / prod 共用 bucket,靠前綴隔離 |
| `S3_PRESIGN_TTL_SECONDS` | `900` | presign TTL;由呼叫端讀取後傳入 `presign_get` |

## IAM 權限清單(最小化)

presigned URL 的權限**繼承簽發者的 IAM** —— 簽發者能做什麼,拿到 URL 的人在 TTL 內就能做
什麼。因此**禁**用 `s3:*` 或 admin 憑證簽發,權限收斂到單一 bucket:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::df-openrouter-dispatch-prod/*"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": "arn:aws:s3:::df-openrouter-dispatch-prod"
    }
  ]
}
```

> `head_object` 對**不存在**的物件:有 `s3:ListBucket` 權限時回 404,沒有時回 **403**
> (AWS 刻意不洩漏物件是否存在)。上表已含 `ListBucket`,故本 client 的 404 判定成立;
> 若日後收掉 `ListBucket`,`head_object` 會改拋 `S3UploadError` 而非回 `False`。

## quirk 紀錄

- **presigned URL 權限繼承簽發者 IAM**:見上。簽發者權限外溢即 URL 權限外溢。
- **Block Public Access 四項全開仍可用 presigned URL**:BPA 擋的是 ACL / bucket policy 的
  匿名公開,presigned URL 走的是「已授權簽章」路徑,不受影響。bucket 一律 private。
- **SigV4 presigned URL TTL 上限 7 天**(長期 IAM 憑證);用臨時憑證(STS)時實際上限為
  該憑證的剩餘壽命,可能遠短於 `ExpiresIn`。本 client 硬擋 `ttl > 7 天`,實務值取分鐘級。
- **`head_object` 缺物件時 botocore 回的 `Error.Code` 是字串 `"404"`,不是 `"NoSuchKey"`**
  (HeadObject 無回應 body 可解析);`get_object` 才會回 `NoSuchKey`。兩者皆已納入
  `errors.py` 的 `_OBJECT_MISSING_CODES`。
- **`NoSuchBucket` 的 HTTP status 也是 404**,故不能只看 status 判定「物件不存在」,
  否則 bucket 打錯時 `head_object` 會全數回 `False`,遷移 Phase 2 會靜默跳過全庫。
  `errors.py` 的 `is_missing_object()` 專門處理此分歧。
- **`delete_object` 對不存在的 key 回 204 成功**,天然冪等,不需先 `head_object`。
- **boto3 預設 retry 為 legacy mode(最多 5 次)**:已改 `standard` + `max_attempts=1`。
- **`Config(retries={"max_attempts": N})` 的 N 是「重試」次數,不是總嘗試次數**:botocore
  內部換算為 `total_max_attempts = N + 1`,讀 `client.meta.config.retries` 時只看得到
  `total_max_attempts`(`max_attempts` 這個 key 已被 pop 掉)。本 client 取 N=1 → 總嘗試 2 次。
- **boto3 `client` thread-safe、`resource` 不是**:本 client 只用 `client`,單例共用。

## 同步 SDK 與機密

- boto3 為同步 SDK,單 worker 下裸呼叫會卡住 event loop 上所有請求 → 四項能力全部
  `asyncio.to_thread` 包裹。`generate_presigned_url` 雖為本地簽章計算,仍一併包裹,
  讓「本目錄所有 boto3 呼叫皆在 `to_thread` 內」成為可機械驗證的單一規則。
- 錯誤轉換**只**擷取安全欄位(錯誤碼 / HTTP status / 操作 / bucket / key / 例外類別名),
  **不轉傳** botocore 原始訊息,且以 `raise ... from None` 切斷 `__cause__` 鏈 ——
  原因(botocore 訊息可能夾帶 `AWSAccessKeyId` / `StringToSign`,本專案 log 無機密過濾層)
  詳見 `errors.py` 檔頭。
- presigned URL 視同臨時憑證:**禁**寫 log、**禁**存 DB、**禁**送下游模型。

## 本目錄沒有 `schemas.py`

S3 回傳為 SDK 原生 dict,不是我方定義的 HTTP schema;需要結構化時於 service 層轉自家
model(`09-object-storage.md` § 落點與命名)。

## 測試

`backend/tests/clients/test_s3_client.py`,走 `botocore.stub.Stubber`,**不打真 AWS**。
