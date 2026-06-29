---
id: task-004
title: AI 欄位驗證 service(內部 LLM 呼叫回信心分數)
status: done
parallel: false
depends_on: [task-002]
affected_files:
  - backend/app/services/api_key_request_agent.py
  - backend/app/core/config.py
  - backend/.env.example
estimated_hours: 3
---

## 目標
實作 `api_key_request_agent.py`,以 `DEFAULT_OPENROUTER_KEY` 經既有 `chat_completion` 對自動候選申請做欄位正確性驗證,回單一信心分數;並新增 `API_KEY_AGENT_MODEL` 設定。

## Acceptance
- [x] `validate_fields(req, matched_department) -> AgentDecision` 呼 `get_openrouter_client().chat_completion(payload, api_key=settings.DEFAULT_OPENROUTER_KEY)`,`payload.model = settings.API_KEY_AGENT_MODEL`,要求 JSON `{confidence:int, reason:str}`。
- [x] 輸入為申請 6 欄 + 命中部門摘要(name/code);prompt 約束輸出結構化 JSON 並硬化解析(夾帶說明文字也能撈出 `{...}`)。
- [x] 失敗(逾時 / 非 2xx / JSON 不可解析 / 金鑰未設)→ `confidence=0` 並記錄 `error_message`,不拋例外卡死流程。
- [x] 不寫 usage_logs、不過白名單、不需 SDK caller 身分。
- [x] `core/config.py` 新增 `API_KEY_AGENT_MODEL: str = "anthropic/claude-sonnet-4.6"`;`.env.example` 補 `API_KEY_AGENT_MODEL` 並確認 `DEFAULT_OPENROUTER_KEY` 已列。

## 必讀檔(Just-in-time)
- [`90-third-party-service/50-openrouter.md`](../../../Design-Base/90-third-party-service/50-openrouter.md) · 呼叫流程與內部用途分離
- [`90-third-party-service/01-client-design.md`](../../../Design-Base/90-third-party-service/01-client-design.md) · client 失敗處理
- [`03-backend/06-clients.md`](../../../Design-Base/03-backend/06-clients.md) · 外部 client 封裝
- [`03-backend/05-exceptions-and-logging.md`](../../../Design-Base/03-backend/05-exceptions-and-logging.md) · 失敗降級與記錄
