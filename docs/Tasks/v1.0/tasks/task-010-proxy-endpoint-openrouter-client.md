---
id: task-010
title: SDK 代理端點 + OpenRouter client(改寫 / key 選擇 / failover 重試)
status: done
parallel: false
depends_on: [task-007, task-009]
affected_files:
  - backend/app/api/v1/model_openrouter.py
  - backend/app/services/proxy/
  - backend/app/clients/openrouter/
  - backend/app/schemas/model.py
  - backend/tests/api/test_model_openrouter.py
estimated_hours: 4
---

## 目標

實作 `POST /api/v1/model/openrouter/chat`:雙因子(X-SDK-Key + X-User-Token)驗證 + 部門一致檢查 → 白名單 → 簡化 schema(`{model,text,images}`)改寫為 OpenRouter chat/completions → 依部門隨機挑 active Key、401 failover 下一把(上限 N)→ 回原始 `{id,choices,usage}`(濾內部欄位)。`parallel:false`:與 007/009 的 client/auth 模組相依,序列化。

## Acceptance

- [x] `uv run pytest tests/api/test_model_openrouter.py` 全綠,含:部門不一致→401`unauthorized`、Token 解密失敗→401、所有 Key 失效→502`openrouter_unavailable`、非白名單→403`model_forbidden`、`videos`→400`feature_not_supported`
- [x] 端對端以 OpenRouter 低成本模型實打一次回 200(`respx` stub + 一支實打驗證腳本)
- [x] Response **不含** `department_uid`/`user_uid`/`openrouter_key_uid`/任何 key 欄位(斷言過濾)
- [x] OpenRouter 呼叫一律經 `clients/openrouter/`,`grep -rn "httpx" backend/app/services/proxy` 無直接建立 client

## 必讀檔(Just-in-time)

- [`90-third-party-service/50-openrouter.md`](../../../Design-Base/90-third-party-service/50-openrouter.md)(§3 雙因子 / §4 流程 / §6 改寫過濾 / §8 重試)
- [`90-third-party-service/00-overview.md`](../../../Design-Base/90-third-party-service/00-overview.md) · [`01-client-design.md`](../../../Design-Base/90-third-party-service/01-client-design.md)
- [`03-backend/06-clients.md`](../../../Design-Base/03-backend/06-clients.md) · [`01-routing.md`](../../../Design-Base/03-backend/01-routing.md)(串流例外起始錯誤)
