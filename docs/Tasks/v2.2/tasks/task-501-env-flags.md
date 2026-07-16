---
id: task-501
title: 三顆 env 開關 + Settings 欄位 + .env.example
status: done
parallel: true
depends_on: []
affected_files:
  - backend/app/core/config.py
  - .env.example
estimated_hours: 1.5
---

## 目標

新增本版三顆環境變數到 `Settings`,並同步 `.env.example`(與本機 `.env`),為功能一(自動同步排程)與功能二(申請單通知管理員)提供控管旗標(propose §C / §D.1 / §D.4)。

## 範圍(只做這些,propose §C)

- `MODEL_SYNC_SCHEDULE_ENABLED`(bool,**預設 `false`**):模型自動同步排程總開關;false → 排程 task 消費即 return,不同步。對齊既有 `AI_EVAL_ENABLED`。
- `MODEL_SYNC_INTERVAL_DAYS`(int,**預設 `3`**):自動同步間隔天數;排程於「每 N 天的 00:00」觸發(cron 於 502 組出)。
- `APIREQ_ADMIN_NOTIFY_ENABLED`(bool,**預設 `false`**):申請單判決後通知系統管理員總開關;M365 未配置時自然不寄。
- **不**新增 M365 相關 env(沿用既有 `M365_*`);**不**新增 cron 字串 env(排程 502 由 `MODEL_SYNC_INTERVAL_DAYS` 組 cron)。

## 實作要點

- 兩顆 bool 各加 `field_validator(..., mode="before")` 走既有 `coerce_bool_env`;int 走 `coerce_int_env`(對齊既有 `AI_EVAL_ENABLED` / `AI_EVAL_BEAT_INTERVAL_SECONDS` 寫法)。
- `.env.example` 在適當區塊(排程 / 通知)追加三行,附中文註解(預設值與說明);提醒使用者於本機 `.env` 同步填值(CLAUDE.md 開發前必檢查)。
- 欄位命名 / 註解對齊 `00-overview/91-project-naming-env.md`。

## Acceptance

- [ ] `cd backend && uv run python -c "from app.core.config import get_settings; s=get_settings(); assert s.MODEL_SYNC_SCHEDULE_ENABLED is False and s.MODEL_SYNC_INTERVAL_DAYS == 3 and s.APIREQ_ADMIN_NOTIFY_ENABLED is False; print('ok')"` 印出 `ok`
- [ ] `grep -q "MODEL_SYNC_SCHEDULE_ENABLED" .env.example && grep -q "MODEL_SYNC_INTERVAL_DAYS" .env.example && grep -q "APIREQ_ADMIN_NOTIFY_ENABLED" .env.example`(三鍵皆存在)
- [ ] `cd backend && uv run ruff check app/core/config.py && uv run mypy app/core/config.py` 全綠

## 必讀檔(Just-in-time)

- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/00-overview/02-secrets.md`
- `docs/Design-Base/00-overview/03-env-layers.md`
- `docs/Design-Base/00-overview/91-project-naming-env.md`
- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/04-config.md`
