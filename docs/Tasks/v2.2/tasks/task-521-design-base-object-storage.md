---
id: task-521
title: Design-Base 新增物件儲存規範檔 + 兩處對照表同步
status: pending
parallel: true
depends_on: []
affected_files:
  - docs/Design-Base/90-third-party-service/09-object-storage.md
  - docs/Design-Base/README.md
  - AGENTS.md
estimated_hours: 2
---

## 目標

AWS S3 為本專案**新的第三方服務**,`docs/Design-Base/90-third-party-service/` 現無物件儲存規範檔。依 [`01-propose/07-rule-evolution.md`](../../../Design-Base/01-propose/07-rule-evolution.md)「要改規則先改 Design-Base」,本 task 為 v2.2.1 **第一個 task**,先補地板規範,後續 523 起的實作才有依據(propose §規範層級註記,✅ user 定案 2026-07-29)。

## 範圍(只做這些)

新增 `docs/Design-Base/90-third-party-service/09-object-storage.md`,內容至少涵蓋:

1. **落點與命名**:client 落 `app/clients/s3/`(`client.py` / `errors.py` / `README.md`);主類 `S3Client`、錯誤類 `S3Error` + 子類;設定命名 `S3_*` / `AWS_*`(對齊 [`00-overview.md § 命名`](../../../Design-Base/90-third-party-service/00-overview.md))。
2. **錯誤轉換契約**:`botocore.exceptions.*` **禁**流到 service / api 層,一律轉 `S3Error` 子類。
3. **同步 SDK 的 async 規則**:boto3 為同步 SDK,所有呼叫**必** `asyncio.to_thread` 包裹(對齊 [`03-backend/03-async-and-tx.md`](../../../Design-Base/03-backend/03-async-and-tx.md));**短 timeout + 低重試上限**,禁無上限重試拖垮 event loop。
4. **物件 key 規則**:必含環境前綴(`S3_KEY_PREFIX`)以隔離 dev / test / prod;key 應為 **deterministic**(內容 hash 參與)以支援冪等重跑;禁把使用者原始檔名直接當 key(路徑穿越 / 編碼問題)。
5. **存取權**:bucket 一律 **private**,Block Public Access 全開;對外取用**一律**經後端簽發的 presigned URL,**禁**公開讀、禁把 bucket 掛 CDN 公開。
6. **presigned URL**:TTL 由 env 控制、預設取分鐘級;明載「presigned 權限**繼承簽發者 IAM 權限**」→ IAM 必最小化到單一 bucket 的 `PutObject` / `GetObject` / `DeleteObject` / `ListBucket`。
7. **機密**:`AWS_SECRET_ACCESS_KEY` 僅 env 注入,禁 commit、禁入 log(對齊 [`00-overview/02-secrets.md`](../../../Design-Base/00-overview/02-secrets.md))。
8. **失敗語意底線**:物件儲存屬**記帳 / 稽核輔助層**,其失敗**不得**擋下主業務流程(可 best-effort 記 log);若某功能確需強一致,須在該版 propose 顯式聲明例外。

同步更新兩處對照表(**漏改則 agent 之後載不到這份規範**):

- `docs/Design-Base/README.md`:「任務 → 必讀檔」第三方服務區塊 + 「檔案 → 用途」`90-third-party-service/` 表,各加一列。
- `AGENTS.md § Just-in-time Loading` 的「依子任務載入」表加一列(串物件儲存 / S3)。

## 不做

- **不**寫任何實作程式碼(S3 client 是 523 的事)。
- **不**改其他 Design-Base 檔(`01-versions.md` 的 boto3 鎖版由 523 負責,避免同檔互鎖)。

## Acceptance

- [ ] `[ -f docs/Design-Base/90-third-party-service/09-object-storage.md ]` 為真
- [ ] `grep -q "09-object-storage" docs/Design-Base/README.md` 命中 **≥ 2 次**(任務對照表 + 檔案用途表):`[ $(grep -c "09-object-storage" docs/Design-Base/README.md) -ge 2 ]`
- [ ] `grep -qi "object-storage\|物件儲存" AGENTS.md` 為真
- [ ] 新檔含全部 8 個規範主題:`for k in "app/clients/s3" "S3Error" "to_thread" "S3_KEY_PREFIX" "presigned" "private" "AWS_SECRET_ACCESS_KEY" "best-effort"; do grep -q "$k" docs/Design-Base/90-third-party-service/09-object-storage.md || echo "MISSING: $k"; done` **無任何輸出**
- [ ] 新檔內所有相對連結可解析(無 404 路徑)

## 必讀檔(Just-in-time)

- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/README.md`(§ 維護準則 — 新增規範檔須同步兩節)
- `docs/Design-Base/90-third-party-service/00-overview.md`
- `docs/Design-Base/90-third-party-service/01-client-design.md`
- `docs/Design-Base/01-propose/07-rule-evolution.md`
- `docs/Design-Base/00-overview/02-secrets.md`
