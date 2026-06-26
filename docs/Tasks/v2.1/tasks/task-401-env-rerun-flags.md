---
id: task-401
title: env 兩顆開關 + Settings 欄位
status: done
parallel: true
depends_on: []
affected_files:
  - backend/app/core/config.py
  - .env.example
estimated_hours: 1.5
---

## 目標

新增本版兩顆環境開關到 `Settings`,並同步 `.env.example`(與本機 `.env`),為 §5 重跑管線與 §5.3 對比裁決提供控管旗標(propose §7、決議 #1 / #8)。

## 範圍(只做這些,propose §7)

- `AI_RERUN_ENABLED`(bool,**預設 `false`**):總開關;false → 完全不觸發真實重跑與對比裁決(零成本)。對齊既有 `AI_EVAL_ENABLED`。
- `AI_RERUN_DISCRIMINATOR_ENABLED`(bool,**預設 `true`**):(B) 對比裁決子開關(須 `AI_RERUN_ENABLED=true` 才生效);false → 只做 (A) 真實重跑取客觀指標,跳過 AI 裁決。
- **不**新增 batch / interval / 每日預算 env(決議 #1、#8):`dispatch_unrerun` 沿用既有 `AI_EVAL_DISPATCH_BATCH_SIZE` / `AI_EVAL_BEAT_INTERVAL_SECONDS`;**禁**新增 `AI_RERUN_DAILY_BUDGET_USD`。

## 實作要點

- 兩欄各加 `field_validator(..., mode="before")` 走既有 `coerce_bool_env`(對齊現有 `AI_EVAL_ENABLED` 的寫法,行 170–173)。
- `.env.example` 在現有 `AI_EVAL_*` 區塊後追加兩行,附中文註解(預設值與說明);提醒使用者於本機 `.env` 同步填值(CLAUDE.md 開發前必檢查)。
- challenger / discriminator 沿用既有 `DEFAULT_OPENROUTER_KEY`,**不**新增金鑰 env。

## Acceptance

- [ ] `cd backend && uv run python -c "from app.core.config import get_settings; s=get_settings(); assert s.AI_RERUN_ENABLED is False and s.AI_RERUN_DISCRIMINATOR_ENABLED is True; print('ok')"` 印出 `ok`
- [ ] `grep -q "AI_RERUN_ENABLED" .env.example && grep -q "AI_RERUN_DISCRIMINATOR_ENABLED" .env.example`(兩鍵皆存在於 `.env.example`)
- [ ] `grep -q "AI_RERUN_DAILY_BUDGET_USD" backend/app/core/config.py; test $? -ne 0`(確認**未**導入每日預算閘,決議 #1)
- [ ] `cd backend && uv run ruff check app/core/config.py && uv run mypy app/core/config.py` 全綠

## 必讀檔(Just-in-time)

- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/00-overview/02-secrets.md`
- `docs/Design-Base/00-overview/03-env-layers.md`
- `docs/Design-Base/00-overview/91-project-naming-env.md`
- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/04-config.md`
</content>
