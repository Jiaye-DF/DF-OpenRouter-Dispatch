---
id: task-004
title: 更新 INTEGRATION.md 檔案上傳欄位與隱私說明
status: done
parallel: true
depends_on: []
affected_files:
  - docs/INTEGRATION.md
estimated_hours: 2
---

## 目標
更新對外 SDK 串接文件 `docs/INTEGRATION.md`,補上 `files` 欄位、檔案上傳範例與「用量紀錄只存檔名」之隱私說明(對外 API 鏈路異動須連帶更新文件)。

## Acceptance
- [x] §5 欄位表新增 `files: [{ filename, file_data }]` 列,標註可選與型別。
- [x] 新增 §5.3 檔案上傳範例(base64 data URL 與遠端 URL 各一)與隱私說明。
- [x] §10 儲存說明補檔案例外:`request_content` 僅留 `filename`、不留 `file_data`。
- [x] 文件明確說明 PDF 解析由 OpenRouter 負責,本平台不做檔案層級驗證。

## 必讀檔(Just-in-time)
- [`00-overview/04-api-docs.md`](../../../Design-Base/00-overview/04-api-docs.md) · [`90-third-party-service/50-openrouter.md`](../../../Design-Base/90-third-party-service/50-openrouter.md) · [`04-databases/10-statistics-log.md`](../../../Design-Base/04-databases/10-statistics-log.md)
