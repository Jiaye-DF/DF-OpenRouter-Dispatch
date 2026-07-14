"""對比裁決(discriminator)prompt 組裝 + 寬鬆解析(對齊 propose-v2.1.0 §5.3、決議 #7 盲化)。

純函式、無 I/O、無 DB:把「使用者原輸入 + 輸出 A + 輸出 B + 任務脈絡」組成可送往
OpenRouter `/chat/completions` 的 payload,要求裁判**盲選**何者較適合任務,輸出結構化
`{winner, reason, score}`(對應 `app.schemas.ai_model_eval.DiscriminatorOutput`)。供
task-405 rerun service 呼叫。

設計約束:
- **盲化**(決議 #7):payload 文字**不**揭露兩側模型名,只給「輸出 A / 輸出 B」。
  A/B 與 original/challenger 的對應由 caller(service)隨機映射後事後還原;本模組只接受
  「已決定好的 A 文字 / B 文字」並產 payload,確保盲化(不在 payload 內寫出模型名)。
- `winner` ∈ A/B;`score` = 對「原 AI 推薦該換成 challenger 是否合理」的**信心分數 0–1**
  (propose §4.1 `compare_score` 語意)。
- `temperature=0`:裁決為評分/分類任務,壓低取樣隨機性以提升可重現性(對齊 v2.0 fixed §2)。
- **PII**:本版**不**遮罩、外送原文;但保留遮罩 hook(`text_masker`,對齊 build_judge_prompt
  決議 #5),v2.1 可注入實際遮罩實作而不破壞介面。
"""

import json
from collections.abc import Callable, Mapping
from typing import Any

from app.schemas.ai_model_eval import DiscriminatorOutput

# 「使用者輸入」區塊的渲染與 build_judge_prompt 完全共用(原為逐字複製的第二份實作;
# v2.1.2 開放 messages 直傳後兩份都得改,故收斂為單一實作)。該實作已支援雙快照形狀。
from app.services.ai_model_eval_prompt import _render_input
from app.services.llm_json import extract_first_json_object

# 遮罩 hook 型別:吃一段文字、回遮罩後文字。預設 identity(本版不遮罩,見模組 docstring)。
TextMasker = Callable[[str], str]


def _identity_masker(text: str) -> str:
    """預設遮罩 hook:原樣返回(本版不做 PII 遮罩)。"""
    return text


_SYSTEM_PROMPT = (
    "你是嚴格客觀的對比裁決裁判(盲測):已知使用者原始輸入與任務脈絡,以及對同一輸入的"
    "兩份輸出『輸出 A』與『輸出 B』(來源模型已匿名,不揭露)。只回傳一個 JSON 物件,含三欄:\n"
    "1. winner:擇優,僅能填 'A' 或 'B'(哪一份輸出更適合該任務)。\n"
    "2. reason:一句話說明擇優理由。\n"
    "3. score:信心分數(0–1),代表你對『B 確實比 A 更適合該任務(即建議改用 B)』的信心;"
    "若你判定 A 較佳(winner=A),score 表示對此判斷的信心,亦填 0–1。\n"
    "規則:winner 必為 'A' 或 'B',不得自創;客觀比較兩份輸出對任務的適配,勿臆測來源、"
    "勿因風格偏好而非任務適配下判斷;除該 JSON 外不要輸出任何文字或圍欄。"
)

_OUTPUT_SCHEMA_HINT = json.dumps(
    {
        "winner": "A",
        "reason": "A 完整覆蓋需求且…",
        "score": 0.72,
    },
    ensure_ascii=False,
)


def build_discriminator_prompt(
    request_content: Mapping[str, Any],
    output_a: str,
    output_b: str,
    *,
    task_context: str | None = None,
    text_masker: TextMasker = _identity_masker,
) -> dict[str, Any]:
    """組出送往裁決模型的 `/chat/completions` payload(不含 judge model;由 service 填)。

    Args:
        request_content: usage_logs.request_content 原文({model, text, images, tools, files});
            `model` 欄略過不帶(盲化:payload 不得出現任一模型名)。
        output_a: 已決定好的「輸出 A」全文(A/B 隨機映射由 caller 處理,本模組不還原)。
        output_b: 已決定好的「輸出 B」全文。
        task_context: 可選的任務脈絡描述(如 task_summary / intent);None 則不顯示。
        text_masker: 可選的 PII 遮罩 hook(吃文字回文字),預設 identity(本版不遮罩)。
            v2.1 可注入實際遮罩實作而不破壞介面。

    Returns:
        OpenAI-compatible payload:{messages, response_format, temperature};呼叫端補上
        judge `model` 後即可送出。要求模型以 JSON 物件回應(對應 `DiscriminatorOutput`)。
        `temperature=0`:裁決為評分/分類任務,壓低取樣隨機性以提升可重現性與裁判間一致性。
    """
    sections: list[str] = []
    if task_context:
        sections.append(f"## 任務脈絡\n{task_context}")
    sections.append(f"## 使用者輸入\n{_render_input(request_content, text_masker)}")
    sections.append(f"## 輸出 A\n{output_a}")
    sections.append(f"## 輸出 B\n{output_b}")
    sections.append(f"## 回傳 JSON 範例\n{_OUTPUT_SCHEMA_HINT}")
    user_prompt = "\n\n".join(sections)

    return {
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
        # 評分/分類任務:壓低取樣隨機性,提升可重現性與裁判間一致性。
        "temperature": 0,
    }


def _parse_discriminator_content(content: str) -> DiscriminatorOutput:
    """寬鬆解析裁決模型回傳:容忍圍欄 / 前後夾帶文字 / 物件後額外資料,再交 DiscriminatorOutput 驗證。

    JSON 萃取共用 `llm_json.extract_first_json_object`(對齊 `ai_model_eval._parse_judge_content`)。
    """
    data = extract_first_json_object(content)
    return DiscriminatorOutput.model_validate(data)
