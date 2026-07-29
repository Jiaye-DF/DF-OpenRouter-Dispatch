---
id: task-532
title: 對外文件同步(INTEGRATION.md + user-guide 頁)
status: pending
parallel: true
depends_on: [task-525, task-527]
affected_files:
  - docs/INTEGRATION.md
  - frontend/src/app/(main)/user-guide/page.tsx
estimated_hours: 2
---

## 目標

本版動到對外 API 鏈路的**資料語意**(用量明細的附件形態)與**附件保存政策**(檔案自本版起才留存),依專案慣例須連帶更新使用者文件與 `INTEGRATION.md`。

## 範圍(只做這些)

### 1. `docs/INTEGRATION.md`

- 明載 **request 契約不變**:呼叫端仍可照舊送 base64 data URI,**零改動**即可繼續運作。
- 明載 **送給模型的內容不變**:下游 payload 與 v2.2.0 完全相同,模型回應品質不受影響。
- 新增「附件儲存與保存政策」段:
  - 上傳的圖片 / 檔案存放於公司自有 AWS S3(private),不對外公開;取用一律經後端簽發的短期連結。
  - **檔案(PDF 等)自 v2.2.1 起才留存內容**;本版之前的歷史紀錄只有檔名、沒有內容,不會也無法補上。
  - 用量明細 API 回吐的 `request_content` 中,圖片元素語意由「base64 data URI 或 URL」變更為「可直接顯示的短期 URL」——**這是管理端可見的行為變更**。
  - S3 故障 / 逾時**不會**讓任何代理請求失敗(best-effort);最壞情況只是該筆紀錄的附件未留存,對外行為完全正常。

### 2. 前端 `user-guide` 頁

- 對應更新附件說明段落(現行該頁有 base64 / 圖片相關說明)。
- 文案與 `INTEGRATION.md` 一致,**禁**兩處講法互相矛盾。
- 樣式 / 字級對齊 `02-frontend/91-project-ui-ux.md`。

## 不做

- **不**改 API schema / 端點行為(那是 525 / 527,已完成)。
- **不**寫 `CHANGELOG.md`(release 前另行彙整,走 `01-propose/06-changelog.md`)。
- **不**在文件中出現任何 AWS 憑證、bucket ARN 或內部 key 規則細節。

## Acceptance

- [ ] `grep -q "S3\|物件儲存" docs/INTEGRATION.md` 為真
- [ ] 四個關鍵陳述皆在 `INTEGRATION.md`:`for k in "契約不變" "短期" "v2.2.1" "best-effort"; do grep -q "$k" docs/INTEGRATION.md || echo "MISSING: $k"; done` **無任何輸出**(用詞可調整,但語意須涵蓋:契約不變 / 短期連結 / 自本版起留存 / 失敗不擋請求)
- [ ] `grep -qi "s3\|儲存\|附件" "frontend/src/app/(main)/user-guide/page.tsx"` 為真
- [ ] **無機密外洩**:`grep -nE "AKIA|aws_secret|arn:aws" docs/INTEGRATION.md "frontend/src/app/(main)/user-guide/page.tsx"` **無輸出**
- [ ] `cd frontend && npm run lint && npm run type-check && npm run build` 全綠
- [ ] 兩份文件的附件政策敘述一致(人工對照,於 PR 描述說明比對結果)

## 必讀檔(Just-in-time)

- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/02-frontend/00-overview.md`
- `docs/Design-Base/02-frontend/91-project-ui-ux.md`
- `docs/Design-Base/00-overview/02-secrets.md`
- `docs/Design-Base/01-propose/06-changelog.md`(理解「本 task 不寫 CHANGELOG」的分界)
