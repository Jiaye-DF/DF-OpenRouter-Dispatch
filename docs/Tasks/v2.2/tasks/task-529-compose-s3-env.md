---
id: task-529
title: docker-compose 兩份 env 注入
status: pending
parallel: true
depends_on: [task-522]
affected_files:
  - docker-compose.dev.yml
  - docker-compose-prod.yml
estimated_hours: 1
---

## 目標

讓部署環境的 backend(以及會執行遷移 script 的容器)拿得到 522 新增的 S3 env。**prod compose 無 `env_file`,漏加即靜默拿不到值**(v2.2.0 已踩過同型別的坑,見 propose-v2.2.0 §B.1)。

## 範圍(只做這些)

- **`docker-compose-prod.yml`**:於 `backend`(以及任何需要跑遷移 / 讀附件的服務)的 `environment:` **明列**七顆 env:
  `S3_STORAGE_ENABLED` / `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_REGION` / `S3_BUCKET` / `S3_KEY_PREFIX` / `S3_PRESIGN_TTL_SECONDS`。
  值一律以 `${VAR}` 形式引用,**禁**寫入實值(機密由 Coolify 注入)。
- **`docker-compose.dev.yml`**:走 `env_file: .env` 自動可見 → 確認 backend 服務確實掛了 `env_file`;若某服務未掛,補上或明列。
- 確認 `taskiq-worker` / `taskiq-scheduler` 是否需要這些 env:**本版排程不碰附件**,原則上不需要;若 worker 未來要跑遷移則需要 —— 於本 task 註記結論,不擅自加。

## 不做

- **不**改 Dockerfile、**不**改 healthcheck、**不**改既有服務定義的其他欄位。
- **不**在 compose 內寫任何機密實值。

## Acceptance

- [ ] prod compose 七鍵齊備:`for k in S3_STORAGE_ENABLED AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_REGION S3_BUCKET S3_KEY_PREFIX S3_PRESIGN_TTL_SECONDS; do grep -q "$k" docker-compose-prod.yml || echo "MISSING: $k"; done` **無任何輸出**
- [ ] **無機密實值**:`grep -nE "^[[:space:]]*(S3_[A-Z_]+|AWS_[A-Z_]+):[[:space:]]*[^[:space:]$]" docker-compose-prod.yml docker-compose.dev.yml` **無輸出**(七鍵值必為 `${...}` 形式)
  > ⚠️ 本條原寫作 `"AWS_SECRET_ACCESS_KEY:\s*[^$\s]"` —— ERE 的中括號內 `\s` **不是**空白字元類而是字面 `\` 與 `s`,會對合規的 `${AWS_SECRET_ACCESS_KEY}` 誤報命中。已改用 POSIX class(2026-07-29,由 task-529 worker 回報)。
- [ ] 兩份 compose 皆語法正確:`docker compose -f docker-compose.dev.yml config -q` 與 `docker compose -f docker-compose-prod.yml config -q` 皆回 exit 0
- [ ] dev 路徑可見性:`docker compose -f docker-compose.dev.yml config | grep -q "env_file\|S3_STORAGE_ENABLED"` 為真
- [ ] `gitleaks detect --no-git` 對兩份 compose 無命中

## 必讀檔(Just-in-time)

- `docs/Design-Base/06-Coolify-CD/00-overview.md`
- `docs/Design-Base/06-Coolify-CD/01-compose.md`
- `docs/Design-Base/06-Coolify-CD/04-env-and-secrets.md`
- `docs/Design-Base/06-Coolify-CD/90-project-deployment.md`
- `docs/Design-Base/00-overview/02-secrets.md`
- `docs/Design-Base/00-overview/03-env-layers.md`
