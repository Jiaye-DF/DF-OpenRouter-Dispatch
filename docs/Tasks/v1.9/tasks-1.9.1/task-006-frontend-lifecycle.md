---
id: task-006
title: 前端申請單生命週期(狀態 badge / 一次性憑證 / 取消撤銷人工處理)
status: done
parallel: false
depends_on: [task-005]
affected_files:
  - frontend/src/types/api.ts
  - frontend/src/lib/api/endpoints.ts
  - frontend/src/app/(main)/api-key-requests/page.tsx
estimated_hours: 4
---

## 目標
前端擴充申請單列表/詳情:狀態 badge、送出 loading + 一次性憑證視窗、取消/撤銷/領取憑證操作,及 admin 人工處理面板。

## Acceptance
- [x] `types/api.ts`:`ApiKeyRequest` 加新欄位;新增 `ApiKeyRequestDetail`、`ProvisionedSecrets`、`AgentDecision`。
- [x] `lib/api/endpoints.ts`:新增 `apiKeyRequestById`/`cancelApiKeyRequest`/`revokeApiKeyRequest`/`processApiKeyRequest`/`claimApiKeyRequestSecrets`。
- [x] 列表狀態 badge:待人工處理=warning、Agent 已處理/已處理=success、已撤銷/已取消=secondary。
- [x] 送出採 loading(同步含 AI 呼叫);`agent_done` 成功彈一次性憑證視窗。
- [x] 列操作:本人可取消(填原因)/撤銷(限 `manual_pending`,二次確認);詳情可領取一次性憑證;錯誤以 `showDialog` + `err.localizedDetail` 呈現。
- [x] admin:`manual_pending` 可開「人工處理」(顯示 `agent_decision` 信心分數/理由 → 一鍵開通)。

## 必讀檔(Just-in-time)
- [`02-frontend/02-api-and-state.md`](../../../Design-Base/02-frontend/02-api-and-state.md) · endpoints 與資料流
- [`02-frontend/05-components.md`](../../../Design-Base/02-frontend/05-components.md) · Dialog/Table/Badge/LoadingButton
- [`02-frontend/01-routing-and-error.md`](../../../Design-Base/02-frontend/01-routing-and-error.md) · 錯誤處理 localizedDetail
- [`02-frontend/91-project-ui-ux.md`](../../../Design-Base/02-frontend/91-project-ui-ux.md) · 狀態 badge 與互動規範
