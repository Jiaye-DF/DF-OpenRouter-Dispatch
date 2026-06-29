"""判別 prompt 組裝(對齊 docs/Tasks/v2.0/propose-v2.0.1.md §5 / §6)。

純函式、無 I/O、無 DB:把一筆 usage_log 的「原文 I/O」+ 候選模型白名單,組成可送往
OpenRouter `/chat/completions` 的 payload,要求判別模型輸出 dim1–4 的結構化 JSON
(對應 `app.schemas.ai_model_eval.JudgeOutput`)。供 task-105 evaluation service 呼叫。

設計約束:
- **非盲測(面試式評選)**:prompt **會**揭露使用者目前使用的模型(含 tier 等基礎資訊)。
  判別管線非藝術評鑑、不採盲評;裁判在知道現況的前提下,於「目前模型 + 候選白名單」中
  挑最適合者。**若目前模型已是最適合,即推薦維持目前模型**,避免一律建議更換造成
  A→B、B→A 互推。仍要求裁判客觀、勿因廠商偏袒。(原盲化設計見 git 史)
- **候選白名單**:dim4 推薦只能從傳入的 `candidate_models`(model_key + tier)選,
  prompt 明列白名單;tier 由 service 反查所選 model 以保證一致。
- **PII**:本版**不**遮罩、外送原文;但保留遮罩 hook(`text_masker`),v2.1 可插入。
"""

import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any

# 遮罩 hook 型別:吃一段文字、回遮罩後文字。預設 identity(本版不遮罩,見模組 docstring)。
TextMasker = Callable[[str], str]


def _identity_masker(text: str) -> str:
    """預設遮罩 hook:原樣返回(本版不做 PII 遮罩)。"""
    return text


_SYSTEM_PROMPT = (
    "你是嚴格客觀的模型適配評審(面試式、非盲測):已知使用者目前使用的模型(含 tier)、"
    "其對輸入的輸出原文,與候選模型白名單。只回傳一個 JSON 物件,含四欄:\n"
    "1. task_summary:一句話摘要使用者要做什麼。\n"
    "2. task_intent / task_complexity:意圖(給定枚舉之一)、複雜度(low|medium|high)。\n"
    "3. output_fit:{score, reason},score 為目前模型輸出對任務的吻合度(0–1)。\n"
    "4. recommend:{model, reason},於『目前模型 + 白名單』中綜合適配與成本挑最適合者;"
    "目前模型已最適合(或無明顯更優 / 更省)就填目前模型(即維持)。\n"
    "規則:recommend.model 必為白名單中的 model_key(目前模型若在其中亦可選),不得自創;"
    "嚴禁推薦免費模型(model_key 以 `:free` 結尾者一律不得作為 recommend.model);"
    "客觀判斷、勿因廠商偏袒、勿為換而換;除該 JSON 外不要輸出任何文字或圍欄。"
)

# 意圖枚舉直接寫入 prompt,讓模型回傳值落在固定集合(對齊 schema 的寬鬆解析)。
_INTENT_ENUM = (
    "code_generation | qa | summarization | translation | reasoning | extraction | other"
)

_OUTPUT_SCHEMA_HINT = json.dumps(
    {
        "task_summary": "使用者想做 X",
        "task_intent": "code_generation",
        "task_complexity": "medium",
        "output_fit": {"score": 0.86, "reason": "原回覆涵蓋…但缺…"},
        "recommend": {"model": "<白名單 model_key;維持則填目前模型>", "reason": "維持/建議用…"},
    },
    ensure_ascii=False,
)


def _render_input(request_content: Mapping[str, Any], text_masker: TextMasker) -> str:
    """把 usage_logs.request_content 原文渲染成可讀的「使用者輸入」區塊。

    request_content 形狀同 proxy `_build_request_log`:{model, text, images, tools, files}。
    此處**不**帶入 `model` 欄(目前模型改由 build_judge_prompt 的「目前使用的模型」獨立區塊
    揭露,避免重複);text 過遮罩 hook。
    """
    text = request_content.get("text")
    masked_text = text_masker(text) if isinstance(text, str) else ""
    images = request_content.get("images") or []
    tools = request_content.get("tools") or []
    files = request_content.get("files") or []

    lines: list[str] = [f"文字輸入:\n{masked_text}" if masked_text else "文字輸入:(無)"]
    if images:
        lines.append(f"圖片數量:{len(images)}")
    if tools:
        lines.append(f"使用工具:{json.dumps(tools, ensure_ascii=False)}")
    if files:
        lines.append(f"附帶檔案數量:{len(files)}")
    return "\n".join(lines)


def _render_output(response_summary: Mapping[str, Any]) -> str:
    """把 usage_logs.response_summary 的原模型 output 全文渲染成「輸出」區塊。

    response_summary 形狀同 proxy `_summarize_response`:{output_text, usage?}。
    只取 output_text(目前模型由獨立區塊揭露;此處不重複帶 usage 等雜訊)。
    """
    output_text = response_summary.get("output_text")
    if isinstance(output_text, str) and output_text:
        return output_text
    return "(無輸出)"


def _render_candidates(candidate_models: Sequence[Mapping[str, Any]]) -> str:
    """渲染候選白名單(model_key + tier),供 dim4 推薦限定選擇範圍。"""
    lines: list[str] = []
    for cand in candidate_models:
        model_key = cand.get("model_key", "")
        tier = cand.get("tier")
        if tier:
            lines.append(f"- {model_key}(tier: {tier})")
        else:
            lines.append(f"- {model_key}")
    return "\n".join(lines) if lines else "(無候選)"


def build_judge_prompt(
    request_content: Mapping[str, Any],
    response_summary: Mapping[str, Any],
    candidate_models: Sequence[Mapping[str, Any]],
    original_model: str,
    *,
    original_tier: str | None = None,
    text_masker: TextMasker = _identity_masker,
) -> dict[str, Any]:
    """組出送往判別模型的 `/chat/completions` payload(不含 judge model;由 service 填)。

    Args:
        request_content: usage_logs.request_content 原文({model, text, images, tools, files});
            `model` 欄略過不重複帶(目前模型改由 `original_model` 獨立揭露)。
        response_summary: usage_logs.response_summary({output_text, usage?});只取 output_text。
        candidate_models: 候選白名單,每項至少含 `model_key`,可含 `tier`;dim4 推薦限此清單。
        original_model: 使用者**目前使用的模型** model_key;非盲測,明確揭露給裁判判斷
            「現況是否已最適合 / 是否需更換」(面試式評選)。
        original_tier: 目前模型的 tier(基礎資訊),供裁判參考;None 則不顯示。
        text_masker: 可選的 PII 遮罩 hook(吃文字回文字),預設 identity(本版不遮罩)。
            v2.1 可注入實際遮罩實作而不破壞介面。

    Returns:
        OpenAI-compatible payload:{messages, response_format, temperature};呼叫端補上
        judge `model` 後即可送出。要求模型以 JSON 物件回應(對應 `JudgeOutput`)。
        `temperature=0`:判別為評分/分類任務,壓低取樣隨機性以提升可重現性與裁判間一致性
        (跨 provider / MoE 仍非位元級一致,但變異大幅降低)。
    """
    current_model = (
        f"{original_model}(tier: {original_tier})" if original_tier else original_model
    )
    user_prompt = (
        f"## 目前模型\n{current_model}\n\n"
        f"## 候選白名單(recommend 僅能選此)\n{_render_candidates(candidate_models)}\n\n"
        f"## 使用者輸入\n{_render_input(request_content, text_masker)}\n\n"
        f"## 目前模型輸出\n{_render_output(response_summary)}\n\n"
        f"## task_intent 枚舉\n{_INTENT_ENUM}\n\n"
        f"## 回傳 JSON 範例\n{_OUTPUT_SCHEMA_HINT}"
    )

    return {
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
        # 評分/分類任務:壓低取樣隨機性,提升可重現性與三裁判一致性。
        "temperature": 0,
    }
