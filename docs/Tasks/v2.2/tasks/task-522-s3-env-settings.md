---
id: task-522
title: S3 六顆 env + Settings 欄位 + fail-fast + .env.example
status: pending
parallel: true
depends_on: []
affected_files:
  - backend/app/core/config.py
  - .env.example
estimated_hours: 2
---

## 目標

新增 S3 物件儲存所需的六顆環境變數到 `Settings`,並同步 `.env.example`,為 523 起的實作提供設定來源(propose §C)。

## 範圍(只做這些,propose §C 逐欄定死)

| 變數 | 型別 | 預設 | 說明 |
| --- | --- | --- | --- |
| `S3_STORAGE_ENABLED` | bool | `false` | 總開關;`false` → 完全維持 v2.2.0 行為(零風險回退)。對齊既有 `AI_EVAL_ENABLED` / `MODEL_SYNC_SCHEDULE_ENABLED` 慣例 |
| `AWS_ACCESS_KEY_ID` | str | 空 | IAM 存取金鑰 |
| `AWS_SECRET_ACCESS_KEY` | str | 空 | **機密**;禁 commit 實值、禁入 log |
| `AWS_REGION` | str | `ap-northeast-1` | bucket 所在 region |
| `S3_BUCKET` | str | `df-openrouter-dispatch-prod` | 物件 bucket(user 指定) |
| `S3_KEY_PREFIX` | str | 依環境(例 `dev`) | key 前綴,隔離 dev / test / prod(D.8:單 bucket 共用) |
| `S3_PRESIGN_TTL_SECONDS` | int | `900` | presigned URL 有效期;**僅**用於管理端明細頁顯示 |

> 表中為七列但 `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` 為一組憑證 —— 以 propose §C 表格為準,全數加入。

## 實作要點

- bool 走既有 `coerce_bool_env`、int 走 `coerce_int_env`(對齊既有 `AI_EVAL_ENABLED` / `AI_EVAL_BEAT_INTERVAL_SECONDS` 寫法)。
- **fail-fast**(對齊 [`03-backend/04-config.md`](../../../Design-Base/03-backend/04-config.md)):於既有 `model_validator` 加規則 —— **production 環境且 `S3_STORAGE_ENABLED=true` 時**,`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `S3_BUCKET` 缺任一 → 啟動即失敗。開關為 `false` 時不檢查(可在未配置 AWS 的環境正常啟動)。
- `.env.example`:於檔尾功能區塊之後新增 `# --- S3 物件儲存 (v2.2.1) ---` 區段,七行附中文註解;**機密留空**並標 `[COOLIFY]`。
- `.env.example` 檔尾「[COOLIFY] 機密建議由 Coolify 後台注入」清單**加入 `AWS_SECRET_ACCESS_KEY`** 一行。
- 提醒使用者於本機 `.env` 同步填值(CLAUDE.md § 開發前必檢查)。

## 敏感欄位

- `AWS_SECRET_ACCESS_KEY` **禁**出現於 Response / Log / Commit;若既有 log 過濾採白名單/黑名單機制,須確認 `AWS_*` 已被涵蓋(未涵蓋則於本 task 補上)。

## Acceptance

- [ ] `cd backend && uv run python -c "from app.core.config import get_settings; s=get_settings(); assert s.S3_STORAGE_ENABLED is False and s.AWS_REGION=='ap-northeast-1' and s.S3_BUCKET=='df-openrouter-dispatch-prod' and s.S3_PRESIGN_TTL_SECONDS==900; print('ok')"` 印出 `ok`
- [ ] 七鍵皆在 `.env.example`:`for k in S3_STORAGE_ENABLED AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_REGION S3_BUCKET S3_KEY_PREFIX S3_PRESIGN_TTL_SECONDS; do grep -q "^$k=" .env.example || echo "MISSING: $k"; done` **無任何輸出**
- [ ] 機密留空:`grep -q "^AWS_SECRET_ACCESS_KEY=$" .env.example` 為真
- [ ] Coolify 機密清單已補:`grep -q "AWS_SECRET_ACCESS_KEY" .env.example` 且該字串出現 **≥ 2 次**
- [ ] fail-fast 生效:以 `APP_ENV=production S3_STORAGE_ENABLED=true` 且缺 `S3_BUCKET` 建構 `Settings` **拋出驗證錯誤**(pytest 或一行 python 斷言皆可)
- [ ] `cd backend && uv run ruff check app/core/config.py && uv run mypy app/core/config.py` 全綠
- [ ] `gitleaks detect --no-git` 對 `.env.example` 無命中(或既有 CI secret-scan job 綠)

## 必讀檔(Just-in-time)

- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/00-overview/02-secrets.md`
- `docs/Design-Base/00-overview/03-env-layers.md`
- `docs/Design-Base/00-overview/91-project-naming-env.md`
- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/04-config.md`
