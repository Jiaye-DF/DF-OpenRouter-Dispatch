---
id: task-005
title: 前端 — models provider 徽章/手動新增、openrouter-keys RPM 欄位、internal-keys 新頁、user-guide 更新
status: done
parallel: false
depends_on: [task-003, task-004]
affected_files:
  - frontend/src/types/api.ts
  - frontend/src/lib/api/endpoints.ts
  - frontend/src/lib/api/error-map.ts
  - frontend/src/app/(main)/admin/models/page.tsx
  - frontend/src/app/(main)/openrouter-keys/page.tsx
  - frontend/src/app/(main)/admin/internal-keys/page.tsx
  - frontend/src/app/(main)/user-guide/page.tsx
estimated_hours: 4
---

## 目標
前端對齊 v1.2:types/endpoints/error-map 補新欄位與錯誤碼,`/admin/models` 加 provider 徽章與手動新增本地模型,`/admin/openrouter-keys` 加 RPM/最小間隔,新增 `/admin/internal-keys` 頁與 Sidebar 入口,`/user-guide` 更新 endpoint 與本地模型段落。

## Acceptance
- [x] `types/api.ts`:`Model` 加 `provider`/`model_key`(取代 `openrouter_model_id`)、`OpenRouterKey` 加 `rpm_limit`/`min_request_interval_ms`、新增 `InternalKey`;`endpoints.ts` 加 `models` POST、`internalKeys`/`internalKeyById`、chat endpoint 改 `/api/v1/model/chat`;`error-map.ts` 加 `internal_busy`/`internal_unavailable`/`provider_misconfigured`/`provider_not_allowed` 中文化
- [x] `/admin/models`:列表 provider 徽章(openrouter 藍 / internal 紫)、工具列「手動新增本地模型」Dialog(model_key/name/description/context_length/tier_key/modality)、編輯 Drawer 依 provider 切換可編欄位
- [x] `/admin/openrouter-keys`:列表加 RPM/最小間隔欄(`0` 顯「不限」)、Dialog 加 2 個 number 欄位(placeholder「0 = 不限」+ tooltip 疊加說明)
- [x] `/admin/internal-keys` 新頁:CRUD + RPM/interval + base_url + api_key 安全處理(omit 不動),Sidebar「金鑰」分組加入
- [x] `/user-guide`:endpoint 範例改 `POST /api/v1/model/chat`、加「本地模型」段落(同 header 僅換 model 字串)、錯誤對照表加 `internal_busy`/`rate_limited`(指數退避建議)

## 必讀檔(Just-in-time)
- [`02-frontend/02-api-and-state.md`](../../../Design-Base/02-frontend/02-api-and-state.md) · [`02-frontend/01-routing-and-error.md`](../../../Design-Base/02-frontend/01-routing-and-error.md) · [`02-frontend/05-components.md`](../../../Design-Base/02-frontend/05-components.md) · [`02-frontend/03-env-and-auth.md`](../../../Design-Base/02-frontend/03-env-and-auth.md) · [`02-frontend/91-project-ui-ux.md`](../../../Design-Base/02-frontend/91-project-ui-ux.md)
