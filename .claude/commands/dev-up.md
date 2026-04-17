# 一鍵啟動本機開發環境

啟動 `docker-compose.dev.yml` 定義的所有服務（frontend、backend、postgres、flyway），用於本機開發與測試。
**全程自動執行，不需要詢問使用者確認。**

## 執行前置檢查

依序確認下列條件，任何一項失敗都要**立即中止**並回報原因：

1. **Docker Engine 可用**：執行 `docker info`，若失敗則提示使用者先啟動 Docker Desktop。
2. **`.env` 存在**：若不存在，提醒使用者從 `.env.example` 複製並填入值後再試。
3. **環境變數完整**：對照 `.env.example` 中所有鍵名，檢查 `.env` 是否缺漏或留空；若有缺漏，逐一列出後中止。
4. **`docker-compose.dev.yml` 存在**：若不存在，告知使用者檔案缺失。

## 執行步驟

1. 顯示即將啟動的服務清單（從 `docker-compose.dev.yml` 讀取 `services:` 區塊）。

2. 背景啟動所有服務並重新建置 Image：

   ```
   docker compose -f docker-compose.dev.yml up --build -d
   ```

3. 等待啟動完成後，執行 `docker compose -f docker-compose.dev.yml ps` 顯示各服務狀態。

4. 驗證關鍵端點是否可用（僅做輕量檢查，不阻塞太久）：
   - Backend Swagger：`curl -sSf http://localhost:8000/api/docs -o /dev/null` → 成功則顯示 ✅
   - Frontend：`curl -sSf http://localhost:3001 -o /dev/null` → 成功則顯示 ✅
   - Flyway：檢查 `flyway` container 的 exit code 為 0（Migration 成功）

5. 顯示存取入口摘要：

   ```
   Frontend     → http://localhost:3000
   Backend API  → http://localhost:8000/api/v1
   Swagger 文件 → http://localhost:8000/api/docs
   PostgreSQL   → localhost:5432
   ```

6. 提示後續常用指令：
   - 查看即時 Log：`docker compose -f docker-compose.dev.yml logs -f`
   - 查看特定服務 Log：`docker compose -f docker-compose.dev.yml logs -f backend`
   - 停止所有服務：`docker compose -f docker-compose.dev.yml down`
   - 重啟單一服務：`docker compose -f docker-compose.dev.yml restart backend`

## 錯誤處理

- 若 `docker compose up` 非零結束，立即擷取最後 50 行 log 回報：
  ```
  docker compose -f docker-compose.dev.yml logs --tail=50
  ```
- 若端點檢查失敗，不中止流程，但標記為 ⚠️ 並提示使用者查看對應 container 的 log。

## 注意事項

- 本指令僅讀取與啟動容器，**不會**修改任何檔案或 commit。
- **禁止**自動填寫 `.env` 缺失的值（可能是敏感資訊）。
- 若使用者已啟動過，`--build` 會重新建置但 volume 不受影響；如需完全重置，請使用者手動 `docker compose -f docker-compose.dev.yml down -v`（**需使用者自行判斷**，不得自動執行）。