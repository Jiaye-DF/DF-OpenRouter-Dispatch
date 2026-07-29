# 09-object-storage — 物件儲存(S3 / S3-compatible)

> **何時讀**:把二進位資料(圖片 / 檔案 / 匯出報表 / 稽核快照附件)寫進物件儲存,或從中取用時讀。治理底線見 `00-overview.md`,client 結構 / timeout / retry 見 `01-client-design.md`,同步 SDK 的 async 規則見 `03-backend/03-async-and-tx.md`。

物件儲存視為**一般第三方服務**,`00-overview.md` 的集中位置 / 命名 / 錯誤轉換契約**全數適用**;本檔只補「物件儲存特有」的規則(key 規則、存取權、presigned URL、同步 SDK 包裹、失敗語意)。

---

## 落點與命名(永遠遵守)

```
app/clients/s3/
├── __init__.py          # public exports(S3Client / S3Error 與子類)
├── client.py            # 主類 S3Client + boto3 整合
├── errors.py            # S3Error 與子類
└── README.md            # bucket / region / quirk / IAM 權限清單紀錄
```

- 主類:`S3Client`;錯誤類:`S3Error` + 子類(`S3NotFoundError` / `S3TimeoutError` / `S3UploadError` / `S3ConfigError`)
- **無** `schemas.py`:S3 回傳為 SDK 原生 dict,不是我方定義的 HTTP schema;需要結構化時於 service 層轉自家 model
- **禁**在 `services/` / `api/` 直接 `boto3.client("s3")`(對齊 `00-overview.md § 集中位置`、`03-backend/06-clients.md`)
- 設定命名走 `<SERVICE>_<KIND>`:儲存策略類用 `S3_*`,雲端憑證類沿用 AWS SDK 慣例的 `AWS_*`(SDK 會自動讀取,自訂前綴反而要手動轉接)

```
S3_STORAGE_ENABLED=false          # 總開關;新外部相依預設關,由環境顯式開
AWS_ACCESS_KEY_ID=<runtime-injected>
AWS_SECRET_ACCESS_KEY=<runtime-injected>   # 機密
AWS_REGION=<region>
S3_BUCKET=<bucket-name>
S3_KEY_PREFIX=<env>/              # dev / test / prod 隔離用
S3_PRESIGN_TTL_SECONDS=900        # presigned URL 有效期(分鐘級)
```

- 設定走 `Settings`(`03-backend/04-config.md`);`S3_STORAGE_ENABLED=true` 而 bucket / region / 憑證缺漏 → **啟動 fail-fast**
- 新增上述鍵時同步 `.env*.example`(對齊 `00-overview/02-secrets.md § .env*.example 規則`)

## 錯誤轉換契約(永遠遵守)

`botocore.exceptions.*` / `boto3` 原生 exception **禁**流到 service / api 層,一律於 client 內轉 `S3Error` 子類:

```python
# app/clients/s3/client.py
from botocore.exceptions import ClientError, ConnectTimeoutError, ReadTimeoutError

class S3Error(AppError): ...
class S3NotFoundError(S3Error): ...
class S3TimeoutError(S3Error): ...
class S3UploadError(S3Error): ...

def _put(self, *, key: str, body: bytes, content_type: str) -> None:
    try:
        self._s3.put_object(Bucket=self._bucket, Key=key, Body=body, ContentType=content_type)
    except (ConnectTimeoutError, ReadTimeoutError) as e:
        raise S3TimeoutError("S3 逾時") from e
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in {"NoSuchKey", "404"}:
            raise S3NotFoundError("物件不存在") from e
        raise S3UploadError(f"S3 上傳失敗:{code}") from e
```

| botocore 原生 | 轉成 |
| --- | --- |
| `ConnectTimeoutError` / `ReadTimeoutError` | `S3TimeoutError` |
| `ClientError` code `NoSuchKey` / `404` / `NoSuchBucket` | `S3NotFoundError` |
| `ClientError` code `AccessDenied` / `403` / `InvalidAccessKeyId` | `S3Error`(權限類,**禁**把 key 內容帶進訊息) |
| `EndpointConnectionError` / 其餘 `ClientError` | `S3Error` / `S3UploadError` |

- service / api 層**只** catch `S3Error`(`AppError` 子類),**禁** catch `botocore.*`
- 錯誤訊息**禁**帶 access key / secret / presigned URL / 物件內容

## 同步 SDK 的 async 規則(永遠遵守)

`boto3` 為**同步** SDK,在 async 函式內裸呼叫會卡住 event loop(違反 `03-backend/03-async-and-tx.md`)。

```python
await asyncio.to_thread(self._put, key=key, body=body, content_type=mime)   # ✅
self._put(key=key, body=body, content_type=mime)                            # ❌ 卡 event loop
```

- 所有網路型呼叫(`put_object` / `get_object` / `head_object` / `delete_object` / `list_objects_v2`)**必** `asyncio.to_thread` 包裹
- `generate_presigned_url` 為**本地簽章計算**(不打網路),可直接呼叫;但仍**必**經 `S3Client` 統一入口,不在 service 層自組
- **短 timeout + 低重試上限**,禁沿用 boto3 預設(legacy retry mode 會重試到 5 次,疊上長 timeout 足以拖垮 event loop 與 thread pool):

```python
from botocore.config import Config

Config(
    connect_timeout=3.0,
    read_timeout=10.0,
    retries={"max_attempts": 2, "mode": "standard"},   # 總嘗試 ≤ 3 次
)
```

- retry 上限對齊 `01-client-design.md § Retry`(attempts ≤ 3);**禁**無上限重試
- boto3 `client` 物件於 FastAPI `lifespan` 建立單例並重用(建 client 有 metadata 載入成本);boto3 `client` thread-safe,`resource` **非** thread-safe,一律用 `client`

## 物件 key 規則(永遠遵守)

```
{S3_KEY_PREFIX}{domain}/{owner_uid}/{sha256}.{ext}
例:prod/usage-log/01J.../9f2c...a1.png
```

- **必含環境前綴** `S3_KEY_PREFIX`:dev / test / prod 共用同一 bucket 時,前綴是唯一隔離手段,少了它測試物件會污染正式資料
- key **必 deterministic**(內容 `sha256` 參與計算):同一份內容重跑產生同一 key → 支援冪等重跑 / 遷移腳本可安全重試,且免除 mapping 表
- **禁**把使用者原始檔名直接當 key(路徑穿越 `../`、URL 編碼、非 ASCII、長度上限問題);原始檔名存 DB metadata 欄位,只作顯示用
- 副檔名由 **MIME 白名單**推導,**禁**取自使用者輸入
- key **禁**含前導 `/`、`..`、控制字元;組完後統一正規化驗證

## 存取權(永遠遵守)

- bucket 一律 **private**,**Block Public Access 四項全開**
- **禁** `public-read` ACL、**禁** bucket policy 對 `Principal: "*"` 開放、**禁**把 bucket 掛 CDN 公開
- 對外取用**一律**經後端簽發的 presigned URL(下節);**禁**把 `https://<bucket>.s3.<region>.amazonaws.com/<key>` 這種裸 URL 給前端
- 伺服器端加密至少啟用 SSE-S3;有合規需求再升 SSE-KMS

## presigned URL

- TTL 由 `S3_PRESIGN_TTL_SECONDS` 控制,**預設取分鐘級**(例 900 = 15 分鐘);SigV4 + 長期 IAM 憑證下上限為 7 天,但**禁**設到天級
- **presigned URL 的權限繼承簽發者的 IAM 權限** —— 簽發者能做什麼,拿到 URL 的人在 TTL 內就能做什麼。因此 IAM **必**最小化到**單一 bucket** 的 `PutObject` / `GetObject` / `DeleteObject` / `ListBucket`,**禁**用 `s3:*` 或 admin 憑證簽發:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::<bucket>/*"
    },
    { "Effect": "Allow", "Action": ["s3:ListBucket"], "Resource": "arn:aws:s3:::<bucket>" }
  ]
}
```

- presigned URL 視同**臨時憑證**:**禁**寫入 log、**禁**存 DB、**禁**送給第三方 / 下游模型;只在 API response 即時產生給已認證的管理端使用者
- 每次讀取都**重新簽發**,不快取

## 機密(永遠遵守)

對齊 `00-overview/02-secrets.md`:

- `AWS_SECRET_ACCESS_KEY`(與 `AWS_ACCESS_KEY_ID`)**僅** env 注入,**禁** commit、**禁**寫進程式碼 / image / compose 字面值
- **禁**入 log:結構化 log 的機密過濾清單須涵蓋 `AWS_*` 與 presigned URL(`03-backend/05-exceptions-and-logging.md`)
- CI gitleaks 須能命中 AWS key 樣式(`05-CI/04-secret-scan.md`);曾外洩 → 走 `00-overview/02-secrets.md § 外洩 incident 流程`(rotate + 撤銷 + 寫 `docs/Tasks/v*/fixed.md`)
- staging / production 憑證**獨立**生成,不共用

## 失敗語意底線(永遠遵守)

物件儲存在本層定位為**記帳 / 稽核輔助層**,不是主業務資料的唯一真實來源:

- S3 失敗(逾時 / 權限 / 服務不可用)**不得**擋下主業務流程 —— 主流程照常執行、照常回應、記帳照常寫入
- 失敗採 **best-effort**:記結構化 log(含 key、mime、bytes、錯誤類別;**禁**記內容本身)+ 在資料列標記失敗態(例 `{"upload_failed": true, ...}`),供事後補跑
- **禁**因上傳失敗而降級回寫大體積原始內容進 DB(等於繞過本規範的目的)
- 若某功能確需**強一致**(上傳失敗即整筆失敗),須在**該版 propose 顯式聲明例外**並說明理由,不得於實作階段自行決定

## 測試

對齊 `03-backend/07-testing.md`:

- 走 `botocore.stub.Stubber` 或 `moto` mock;**禁**真實打 AWS(慢 + 不可重現 + 產生費用與孤兒物件)
- 必測:逾時 → `S3TimeoutError`、404 → `S3NotFoundError`、key 為 deterministic(同輸入同 key)、失敗不擋主流程
- presigned URL 測試斷言「有 TTL 參數 + 指向正確 bucket/key」,**禁**斷言完整簽章字串(隨時間變動)

## 不要做

- ❌ bucket 開公開讀 / 掛 CDN 公開(規範第一條就守不住)
- ❌ 在 async 函式裸呼 boto3(卡 event loop)
- ❌ 用使用者原始檔名或隨機 UUID 當 key(前者不安全,後者不可冪等)
- ❌ 用 admin / `s3:*` 憑證簽 presigned URL(權限外溢)
- ❌ 把 presigned URL 記進 log 或存 DB
- ❌ 讓 S3 失敗把主業務請求打掛
