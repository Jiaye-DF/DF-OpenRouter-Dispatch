---
id: task-437
title: 前端:新增 Switch 共用元件 + 使用者管理頁停用/啟用開關 + 確認對話框 + 自己那列 disable
status: done
parallel: true
depends_on: [task-436]
affected_files:
  - frontend/src/components/ui/switch.tsx
  - frontend/src/app/(main)/users/page.tsx
  - frontend/src/types/api.ts
estimated_hours: 2
---

## 目標

使用者管理頁(`frontend/src/app/(main)/users/page.tsx`)狀態欄由唯讀 Badge(現 L581-585)改為可切換 Switch:切換前確認對話框(停用文案明示「停用後將撤銷其全部 Token,SDK 呼叫與登入即刻失效」),打 `PATCH API_ENDPOINTS.userById(uid)` 送 `{ is_active }`;新增共用 `Switch` 元件(`frontend/src/components/ui/switch.tsx`,現無);登入者自己那列開關 disable。

## 實作要點(對齊 propose §C.1 / §D.5 / §D.6)

- `Switch` 元件:風格對齊既有 `components/ui/*`(Tailwind v4、觸控目標、focus ring、disabled 態);API 形狀 `checked / onCheckedChange / disabled`。
- 切換流程沿用既有 `useConfirm` 確認模式(參考撤銷 Token 流程,現 L381-414);停用與啟用文案分開(啟用文案提示「原 Token 不會恢復,需重新產生」)。
- 成功後刷新列表 + toast;失敗(含 436 的 400 不可停用自己)顯示後端錯誤訊息。
- 自己那列:開關 `disabled`(以登入者 uid 比對);後端 400 為最終防線。
- `frontend/src/types/api.ts`:使用者更新 payload 型別補 `is_active?: boolean`(`User.is_active` 已存在不動)。
- 狀態 Badge 是否保留由視覺取捨(Switch + 文字即可表態);不動其他列操作(編輯/重設密碼/產生 Token/撤銷 Token)。

## Acceptance

- [ ] `npm run lint`(frontend/)與 `npx tsc --noEmit` 零錯誤零 warning
- [ ] `[ -f frontend/src/components/ui/switch.tsx ]` 存在且被 users/page.tsx import
- [ ] 手測 case(dev 環境,配合 436):
  - [ ] 停用他人 → 確認框(含撤銷警告)→ 確認後列表狀態更新;該使用者 token 呼叫 401
  - [ ] 啟用 → 確認框(含「Token 需重新產生」提示)→ 狀態更新
  - [ ] 自己那列開關為 disabled;直接以 API 對自己送停用 → toast 顯示後端 400 訊息
  - [ ] 取消確認框 → 開關狀態不變、無 API 呼叫
- [ ] `git diff` 不含 `frontend/src/app/(main)/usage-logs/`(與 434 無交叉)

## 必讀檔(Just-in-time)

- `docs/Design-Base/02-frontend/00-overview.md`(風格地板)
- `docs/Design-Base/02-frontend/02-api-and-state.md`(API 集中)
- `docs/Design-Base/02-frontend/05-components.md`(共用元件必抽 → Switch 落 ui/)
- `docs/Design-Base/02-frontend/06-rwd.md`(觸控目標)
- `docs/Design-Base/02-frontend/90-project-frontend.md` + `91-project-ui-ux.md`(Dialog / toast 慣例)
- `docs/Tasks/v2.1/propose-v2.1.2.md` §C.1/§D.5/§D.6
