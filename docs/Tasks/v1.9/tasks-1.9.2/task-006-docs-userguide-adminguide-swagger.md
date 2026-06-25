---
id: task-006
title: 文件 — user-guide / admin-guide / Swagger 同步
status: done
parallel: false
depends_on: [task-004]
affected_files:
  - frontend/src/app/(main)/user-guide/page.tsx
  - frontend/src/app/(main)/admin-guide/page.tsx
estimated_hours: 2
---

## 目標
更新使用者與管理員文件,說明開通後會以 Email 通知負責人、通知失敗可重送、以及 M365 設定前置;確認 Swagger 同步新端點與新回應欄位。

## Acceptance
- [x] `/user-guide` 補「開通後會以 Email 寄送憑證給專案負責人」說明。
- [x] `/admin-guide` 補「通知失敗時可重送」與 M365 設定前置(Azure App / `Mail.Send` / 寄件人信箱)。
- [x] Swagger(`/api/docs`)反映新端點 `resend-notify` 與回應新欄位 `notified_at` / `notify_error` 的 Schema 與範例。
- [x] 文件內容與 tasks 契約一致,憑證明文不出現於文件範例。

## 必讀檔(Just-in-time)
- [`00-overview/04-api-docs.md`](../../../Design-Base/00-overview/04-api-docs.md) · Swagger 與 API 文件同步
- [`02-frontend/91-project-ui-ux.md`](../../../Design-Base/02-frontend/91-project-ui-ux.md) · 指南頁面風格
- [`02-frontend/00-overview.md`](../../../Design-Base/02-frontend/00-overview.md) · 前端頁面結構
- [`00-overview/00-overview.md`](../../../Design-Base/00-overview/00-overview.md) · 系統總覽脈絡
