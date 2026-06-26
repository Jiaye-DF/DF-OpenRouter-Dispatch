"""判別 prompt 組裝(對齊 docs/Tasks/v2.0/propose-v2.0.1.md §5 / §6)。

純函式、無 I/O、無 DB:把一筆 usage_log 的「原文 I/O」+ 候選模型白名單,組成可送往
OpenRouter `/chat/completions` 的 payload,要求判別模型輸出 dim1–4 的結構化 JSON
(對應 `app.schemas.ai_model_eval.JudgeOutput`)。供 task-105 evaluation service 呼叫。

設計約束(propose §5):
- **盲化**:prompt **不**揭露原 output 出自哪個模型,降低自我偏好偏差。
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
    "你是一個嚴格、客觀的模型適配評審。你會看到一筆「使用者輸入原文」與一段"
    "「某個 AI 模型對該輸入的輸出原文」,以及一份可選用的候選模型白名單。\n"
    "你的任務是從四個方向做出判斷並只回傳 JSON:\n"
    "1. task_summary:用一句話摘要使用者想做什麼。\n"
    "2. task_intent / task_complexity:任務意圖(必須是給定枚舉之一)與複雜度(low|medium|high)。\n"
    "3. output_fit:輸出對任務意圖的吻合度,score 為 0 到 1 的浮點數,並附理由。\n"
    "4. recommend:從候選白名單中挑一個你認為更適合此任務的模型,並附理由。\n"
    "重要約束:\n"
    "- 你**不知道**輸出是由哪個模型產生的,**不要**臆測或在理由中提及任何模型名稱來源。\n"
    "- recommend.model **必須**是候選白名單中的 model_key 之一,不得自創。\n"
    "- 只回傳一個合法 JSON 物件,不要有任何額外文字、註解或 markdown 圍欄。"
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
        "recommend": {"model": "<候選白名單中的 model_key>", "reason": "此任務為…,建議用…"},
    },
    ensure_ascii=False,
    indent=2,
)


def _render_input(request_content: Mapping[str, Any], text_masker: TextMasker) -> str:
    """把 usage_logs.request_content 原文渲染成可讀的「使用者輸入」區塊。

    request_content 形狀同 proxy `_build_request_log`:{model, text, images, tools, files}。
    刻意**不**帶入 `model` 欄(那是使用者指定的原模型),以維持盲化;text 過遮罩 hook。
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
    **盲化**:只取 output_text,不帶任何模型 / provider / usage 識別。
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
    *,
    text_masker: TextMasker = _identity_masker,
) -> dict[str, Any]:
    """組出送往判別模型的 `/chat/completions` payload(不含 model;由 service 填)。

    Args:
        request_content: usage_logs.request_content 原文({model, text, images, tools, files});
            `model` 欄會被刻意略過以維持盲化。
        response_summary: usage_logs.response_summary({output_text, usage?});只取 output_text。
        candidate_models: 候選白名單,每項至少含 `model_key`,可含 `tier`;dim4 推薦限此清單。
        text_masker: 可選的 PII 遮罩 hook(吃文字回文字),預設 identity(本版不遮罩)。
            v2.1 可注入實際遮罩實作而不破壞介面。

    Returns:
        OpenAI-compatible payload:{messages, response_format};呼叫端補上 `model` 後即可送出。
        要求模型以 JSON 物件回應(對應 `JudgeOutput`)。
    """
    user_prompt = (
        "## 候選模型白名單(recommend.model 只能從此清單選)\n"
        f"{_render_candidates(candidate_models)}\n\n"
        "## 使用者輸入原文\n"
        f"{_render_input(request_content, text_masker)}\n\n"
        "## 模型輸出原文(來源模型不明,請勿臆測)\n"
        f"{_render_output(response_summary)}\n\n"
        "## 任務意圖枚舉(task_intent 必為其一)\n"
        f"{_INTENT_ENUM}\n\n"
        "## 請只回傳如下結構的 JSON\n"
        f"{_OUTPUT_SCHEMA_HINT}"
    )

    return {
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
    }
