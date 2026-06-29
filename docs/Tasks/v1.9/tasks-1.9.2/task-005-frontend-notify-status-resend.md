---
id: task-005
title: 前端 — 通知狀態顯示與重送通知
status: done
parallel: false
depends_on: [task-004]
affected_files:
  - frontend/src/types/api.ts
  - frontend/src/lib/api/endpoints.ts
  - frontend/src/app/(main)/api-key-requests/page.tsx
estimated_hours: 3
---

## 目標
前端型別與 API 串接補上通知欄位,於申請單詳情顯示通知狀態(已通知時間 / 失敗原因),並讓 admin 於失敗時可重送通知(二次確認 + 錯誤處理)。

## Acceptance
- [x] `types/api.ts`:`ApiKeyRequest` / `ApiKeyRequestDetail` 加 `notifiedAt` / `notifyError`(對齊後端回應欄位)。
- [x] `lib/api/endpoints.ts`:新增 `resendApiKeyRequestNotify`(admin)呼叫 `POST /api-key-requests/{uid}/resend-notify`。
- [x] `api-key-requests/page.tsx` 詳情顯示「通知狀態」:已通知時間或失敗原因;時間以在地時區格式呈現。
- [x] admin 於通知失敗時顯示「重送通知」動作,含二次確認與失敗錯誤提示(`409 secrets_already_claimed` / 一般錯誤分別處理)。

## 必讀檔(Just-in-time)
- [`02-frontend/02-api-and-state.md`](../../../Design-Base/02-frontend/02-api-and-state.md) · API 串接與狀態
- [`02-frontend/01-routing-and-error.md`](../../../Design-Base/02-frontend/01-routing-and-error.md) · 錯誤處理與二次確認
- [`02-frontend/04-datetime.md`](../../../Design-Base/02-frontend/04-datetime.md) · 通知時間在地時區呈現
- [`02-frontend/05-components.md`](../../../Design-Base/02-frontend/05-components.md) · 狀態與動作元件
- [`02-frontend/91-project-ui-ux.md`](../../../Design-Base/02-frontend/91-project-ui-ux.md) · 本專案 UI/UX 規範
