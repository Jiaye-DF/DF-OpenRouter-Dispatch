# Fixed — v2.0

> 本版(v2.0.x)累積的規範違反 / bug / 設計推翻根因。Agent 寫,user 不主動寫。
> 格式見 `docs/Design-Base/01-propose/04-fixed-format.md`;§N 全版本連號。

## §1 — 判別評審一律建議更換(A↔B 互推「神棍」現象)

- **時間**:2026-06-26+08:00
- **commit / PR**:`71de4f0`
- **影響檔案**:`backend/app/services/ai_model_eval_prompt.py`、`backend/app/services/ai_model_eval.py`、`backend/tests/services/test_ai_model_eval_prompt.py`
- **問題**:評審結果上線後,使用者觀察到判別模型幾乎**永遠建議更換**:用 A 推 B、用 B 推 A,即使原輸出吻合度極高(如 97%)也照樣推一個別的模型;同筆三裁判彼此互推,結果近乎隨機、無參考價值。
- **根因**:**三個系統性因素疊加,非單一 bug**:
  1. **盲化設計**(原 propose §5):prompt 刻意不揭露原輸出出自哪個模型,裁判**不知道目前用的是什麼** → 即使現況已最佳也無從「維持」。
  2. **措辭偏誤**:system prompt 寫「從候選白名單中挑一個你認為**更適合**此任務的模型」,語意預設「要換」,沒有「維持」這條路。
  3. **缺「維持原模型」語意**:即使吻合度滿分,裁判仍被迫填一個 `recommend.model`;系統也未把「recommend == 原模型」當成「維持」。三者合起來 → 盲化 + 強制推薦 + 各裁判偏好不同 = 必然互推。
- **修正**(`71de4f0`):判別改為**面試式、非盲測**——
  - prompt 揭露使用者**目前使用的模型(含 tier)**;裁判在知道現況下,於『目前模型 + 白名單』中綜合適配與成本挑最適合者。
  - 明確指示「**目前模型已最適合(或無明顯更優/更省)→ 推薦維持目前模型**」,並要求客觀、勿因廠商偏袒、勿為換而換。
  - 原模型若已停用、不在白名單 → 自然落到「建議更換」(正確:停用模型不該續用),不強塞回白名單。
  - `build_judge_prompt` 增 `original_model` / `original_tier` 參數,service 傳入;盲化測試改為揭露/維持/tier 測試。
- **規範參照**:`docs/Tasks/v2.0/propose-v2.0.1.md §5`(原「盲化」設計於此推翻——判別非藝術評鑑,不採盲評;使用者 2026-06-26 拍板)。
- **後續**:銜接 v2.0.5「真實重跑(champion/challenger)」——裁判現在會給出具體可呼叫的 challenger,正是該功能輸入。舊評審結果用舊 prompt 跑、已凍結 DB,不回溯;新行為待新進 log 評審或重評才顯現。

## §2 — 判別呼叫未鎖 temperature,評分非確定性偏高

- **時間**:2026-06-26+08:00
- **commit / PR**:`1d6773b`
- **影響檔案**:`backend/app/services/ai_model_eval_prompt.py`、`backend/tests/services/test_ai_model_eval_prompt.py`
- **問題**:同一筆(或重問同一問題)評審結果變異大,吻合度 / 推薦模型每次不同,難以信任與比對。
- **根因**:`build_judge_prompt` 送出的 payload 只設 `response_format`,**未設 `temperature`** → 用模型/OpenRouter 預設(取樣隨機性高)。判別本質是**評分 / 分類**任務,不需要創造性取樣,但預設行為等同開了隨機。
- **修正**(`1d6773b`):payload 加 `temperature=0`,壓低取樣隨機性、提升可重現性與三裁判一致性(跨 provider / MoE 仍非位元級一致,但變異大幅降低);補斷言測試。
- **後續**:若日後要嚴格可重現,可再加固定 `seed`。

## §3 — 待評審派發採 created_at DESC,backlog 可能被餓死

- **時間**:2026-06-26+08:00
- **commit / PR**:`1d6773b`
- **影響檔案**:`backend/app/repositories/ai_model_evaluation.py`、`backend/tests/repositories/test_ai_model_evaluation.py`
- **問題**:大量歷史未評審資料補評審時,永遠先處理最新筆;若新 log 進來速度 > 每輪批次吞吐,最舊那批可能一直輪不到。
- **根因**:`fetch_unevaluated_log_uids` 以 `created_at.desc()`(最新優先)+ `limit` 撈待派。最新優先在「持續有新 log + 批次有限」下對舊 backlog 形成 starvation;派發本應公平(FIFO)。
- **修正**(`1d6773b`):改 `created_at.asc()`(最舊優先,FIFO),backlog 公平消化;partial index 為 DESC,asc 以反向索引掃描,效能影響可忽略。補 FIFO 排序測試。
- **後續**:無。
