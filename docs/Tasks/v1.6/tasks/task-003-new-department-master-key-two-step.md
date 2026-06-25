---
id: task-003
title: 「新增部門」對話框加主金鑰名稱欄 + POST departments→sdk-keys 兩步串接
status: done
parallel: false
depends_on: [task-002]
affected_files:
  - src/app/(main)/departments/page.tsx
estimated_hours: 3
---

## 目標
「新增部門」對話框新增「主金鑰名稱」欄,提交流程改為建部門成功後立刻建第 1 把 SDK Key,明文一次性 Dialog 顯示,新 row 預設展開。

## Acceptance
- [x] 對話框新增「主金鑰名稱」欄(placeholder「{部門名稱} 主金鑰」),留空送出 `${dept.name.trim()} 主金鑰`
- [x] 提交流程:`POST /api/v1/departments` 成功後立刻 `POST /api/v1/sdk-keys` 建第 1 把 key
- [x] 第 2 步成功:key 明文存入 `newKeyPlain` state 觸發既有明文 Dialog 一次性顯示;新部門 row 預設展開(`setExpanded` add 該 UID)
- [x] 第 2 步失敗:顯示警告(部門已建立,主金鑰建立失敗,請從 row 展開後手動補建);不 rollback step 1
- [x] 編輯部門邏輯維持不動(`first_key_name` 欄位編輯時不顯示);刪除部門邏輯維持不動(後端 4xx 涵蓋擋下)

## 必讀檔(Just-in-time)
- [`02-frontend/02-api-and-state.md`](../../../Design-Base/02-frontend/02-api-and-state.md) · [`02-frontend/05-components.md`](../../../Design-Base/02-frontend/05-components.md) · [`00-overview/04-api-docs.md`](../../../Design-Base/00-overview/04-api-docs.md) · [`90-third-party-service/50-openrouter.md`](../../../Design-Base/90-third-party-service/50-openrouter.md)
