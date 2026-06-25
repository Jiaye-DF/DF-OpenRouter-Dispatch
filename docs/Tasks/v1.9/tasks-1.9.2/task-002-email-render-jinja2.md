---
id: task-002
title: Email Render 層(Jinja2 範本檔化管理)
status: done
parallel: true
depends_on: []
affected_files:
  - backend/app/services/email_render.py
  - backend/app/templates/email/base.html
  - backend/app/templates/email/provision.html
  - backend/pyproject.toml
estimated_hours: 2
---

## 目標
導入 Jinja2,新增 `render_email` 統一從 `app/templates/email/` 載入範本並注入品牌 context;確認共用 `base.html` 與開通信 `provision.html` 可正確渲染憑證與三個 Header。

## Acceptance
- [x] `services/email_render.py` 提供 `render_email(template_name, **ctx) -> str`,以 `jinja2.Environment` + `FileSystemLoader("app/templates/email")`、`autoescape=True` 載入。
- [x] render 層自動補基底 context:`brand_name`、`platform_url`(取 `FRONTEND_URL`,可為空)、`current_year`;Environment 以 `lru_cache` 單例化避免每次寄信重建。
- [x] `provision.html`(`extends base.html`)輸出 `X-SDK-Key` / `X-User-Token` / `X-Project-Code` 三個 Header 區塊並帶入實值;`sdk_key` 為空時該欄顯示「請向管理員索取」,其餘照常。
- [x] `Jinja2` 已加入 `pyproject.toml` 依賴;憑證值經 `autoescape` 正確跳脫不破版/注入。

## 必讀檔(Just-in-time)
- [`03-backend/00-overview.md`](../../../Design-Base/03-backend/00-overview.md) · service/render 層分層
- [`03-backend/05-exceptions-and-logging.md`](../../../Design-Base/03-backend/05-exceptions-and-logging.md) · 範本錯誤處理與不記憑證
- [`90-third-party-service/03-smtp.md`](../../../Design-Base/90-third-party-service/03-smtp.md) · 信件範本與品牌 context 慣例
