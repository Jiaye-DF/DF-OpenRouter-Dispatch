---
id: task-005
title: 使用者使用說明補「如何送出 API Key 申請」
status: done
parallel: true
depends_on: [task-004]
affected_files:
  - frontend/src/app/(main)/user-guide/page.tsx
estimated_hours: 1
---

## 目標
於 `/user-guide` 使用者使用說明補一段「如何送出 API Key 申請」,說明 member 可見頁面與 6 欄填寫方式,對齊既有使用說明風格。

## Acceptance
- [x] `/user-guide` 新增「如何送出 API Key 申請」章節,描述進入路徑(sidebar 入口,member/admin 皆可進)。
- [x] 說明 6 必填欄位(部門名稱 / 代號 / 專案名稱 / 專案連結 / 負責人 / 負責人信箱)與 `project_url` 須為 GitHub/Replit。
- [x] 說明檢視範圍分流:admin 看全部、member 只看自己送出的歷程。
- [x] 文案與排版對齊既有 user-guide 慣例,無破版。

## 必讀檔(Just-in-time)
- [`02-frontend/00-overview.md`](../../../Design-Base/02-frontend/00-overview.md) · 前端總覽
- [`02-frontend/05-components.md`](../../../Design-Base/02-frontend/05-components.md) · 文件頁排版元件
- [`02-frontend/91-project-ui-ux.md`](../../../Design-Base/02-frontend/91-project-ui-ux.md) · UI/UX 文案慣例
