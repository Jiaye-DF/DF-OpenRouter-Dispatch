---
id: task-430
title: 規範前置:修訂 Design-Base `50-openrouter.md` 開放 messages 白名單透傳(需 user 批准)
status: done
parallel: true
depends_on: []
affected_files:
  - docs/Design-Base/90-third-party-service/50-openrouter.md
estimated_hours: 1
---

## 目標

`50-openrouter.md` 現行收斂原則(SDK 使用者只給 text/images/files/tools,平台從頭建構 messages、不開放其餘 OpenAI 欄位)與 propose v2.1.2 功能一衝突;依規範優先序**先改規範再實作**:把「呼叫端可自帶 OpenRouter 風格 `messages[]`(role/parts 白名單驗證後透傳)」與「開放 `temperature` / `max_tokens` / `response_format` 三個生成參數」納入該檔,並保留單輪模式與「其餘生成參數不開放」原則。

## ⚠️ 執行前提

- 本 task 動 `docs/Design-Base/*`(規範底線檔),**必須取得 user 明確批准**後才可執行;未批准前 worker 不得認領(視同 blocked)。
- 修訂內容以 propose v2.1.2 §B.1/§B.2、§D.1/§D.2/§D.7 定案為準,**禁**自行擴大開放範圍(top_p / stop 等其餘生成參數維持不開放)。

## 修訂要點(對齊 propose)

- 新增「messages 直傳模式」小節:role 白名單 `system/user/assistant`(`tool` role 不開放);content parts 白名單 `text/image_url/file`;與 `text/images/files` 互斥(同時帶 400);`messages=[]` 400;**不設應用層筆數上限**(模型 context window 為自然上限)。
- 新增「生成參數」小節(§D.7):開放 `temperature`(0–2)/ `max_tokens`(≥1)/ `response_format`(型別化白名單 `json_object` / `json_schema`)三項;兩模式皆可帶;未帶不注入 payload;**其餘生成參數(top_p / stop / penalties 等)不開放**。
- 註記 usage_logs 快照策略:messages 原樣入 `request_content`(file part 僅記 filename);有帶的生成參數一併入快照。
- 原「刻意收斂/從頭建構」段落改寫為「單輪模式(預設)+ messages 直傳模式(白名單)」雙模式敘述;「不開放其餘 OpenAI 欄位」原則改寫為「僅開放上列白名單參數」。
- 依 `docs/Design-Base/README.md § 維護準則`檢查:本次僅改既有檔內容、不新增/棄用檔 → README 索引不需動。

## Acceptance

- [ ] `grep -n "messages" docs/Design-Base/90-third-party-service/50-openrouter.md` 可見新增的 messages 直傳模式小節(含白名單、互斥、400、不設筆數上限)
- [ ] `grep -nE "temperature|max_tokens|response_format" docs/Design-Base/90-third-party-service/50-openrouter.md` 可見生成參數小節(三項開放 + 值域 + 其餘不開放)
- [ ] 修訂後文件仍載明:其餘生成參數(top_p / stop / penalties 等)不開放;回應只回純文字不外露內部欄位
- [ ] commit message 註明規範修訂緣由並引用 propose v2.1.2(對齊 `01-propose/07-rule-evolution.md`)
- [ ] user 已批准本次 Design-Base 修訂(PR / 對話紀錄可稽)

## 必讀檔(Just-in-time)

- `docs/Design-Base/00-overview/00-overview.md`(規範優先序)
- `docs/Design-Base/01-propose/07-rule-evolution.md`(規範演進閉環)
- `docs/Design-Base/90-third-party-service/50-openrouter.md`(修訂標的,全文)
- `docs/Tasks/v2.1/propose-v2.1.2.md` §B.1/§B.2/§D.1/§D.2(定案內容來源)
