---
id: task-002
title: 部門頁加可展開 row + DepartmentKeysPanel 顯示該部門全部 SDK Keys
status: done
parallel: false
depends_on: []
affected_files:
  - src/app/(main)/departments/page.tsx
estimated_hours: 4
---

## 目標
部門表格 row 加可展開箭頭,展開後 inline 渲染該部門所有 SDK Keys(名稱 / 部門金鑰明文 / 啟停 / 刪除 / 新增);進頁批次拉一次 keys 並依 `department_uid` group。

## Acceptance
- [x] 表格新增展開欄(最左、ChevronRight / ChevronDown),admin only,狀態以 `expanded: Set<department_uid>` 管理,不影響 row 排序與分頁
- [x] 表格新增右側「部門金鑰數量」欄(KeyRound icon + 數字),admin only
- [x] 展開後在原 row 下方插入 second row(`colSpan=7`)渲染 `<DepartmentKeysPanel>`:該部門 SDK Keys mini-table(名稱 / 部門金鑰明文 / 啟停 badge / 刪除 icon)
- [x] 部門金鑰明文欄:有 `key_values` 顯示完整明文 + 複製 icon;`key_values=null`(舊資料)顯示「(舊資料,請重新建立)」
- [x] 進頁批次拉一次 `/api/v1/sdk-keys?page=1&size=200`(admin only),依 `department_uid` group 為 `Record<department_uid, SdkKey[]>`;後續操作以 `reloadKeys()` 重抓,不重抓部門列表
- [x] 「+ 新增 SDK Key」inline 輸入框(支援 Enter),成功後一次性明文 Dialog;複製明文以 `useToast()` 給「已複製部門金鑰」通知
- [x] non-admin 進部門頁看不到展開欄 / 操作欄 / 部門金鑰欄(維持 v1.5 行為)

## 必讀檔(Just-in-time)
- [`02-frontend/05-components.md`](../../../Design-Base/02-frontend/05-components.md) · [`02-frontend/02-api-and-state.md`](../../../Design-Base/02-frontend/02-api-and-state.md) · [`03-backend/92-project-permission.md`](../../../Design-Base/03-backend/92-project-permission.md) · [`90-third-party-service/50-openrouter.md`](../../../Design-Base/90-third-party-service/50-openrouter.md)
