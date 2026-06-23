import json
import re
from dataclasses import dataclass

from app.clients.openrouter.client import OpenRouterClient
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.api_key_request import ApiKeyRequest
from app.models.department import Department

logger = get_logger(__name__)


@dataclass
class AgentDecision:
    confidence: int  # 0-100
    reason: str
    error: str | None = None


_SYSTEM_PROMPT = (
    "你是 API Key 申請單的欄位審查員。任務是判斷申請欄位是否正確、合理,給出單一信心分數。\n"
    "審查重點:\n"
    "1. project_url 是否像有效、且與 project_name 相符的 GitHub 或 Replit 連結。\n"
    "2. owner_email 的網域是否合理(非明顯亂填、非一次性信箱)。\n"
    "3. department_name 與 department_code 是否相稱(命中部門摘要提供既有對照)。\n"
    "4. 整體是否疑似亂填、佔位或測試資料。\n"
    "限制:不要實際連線任何 URL,只依字面做合理性判斷。\n"
    "評分原則(重要):\n"
    "- 你『無法也不需要』驗證 URL / repo 是否真的存在、網域是否真的屬於該公司;"
    "這些由其他機制把關。**請勿因為『無法驗證實際存在或真實性』而扣分**。\n"
    "- 只在出現實際紅旗時才給低分:欄位互相矛盾、明顯佔位 / 測試字串(如 test、aaa、123、example)、"
    "一次性信箱、department_name 與 department_code 不符、project_url 非合法 GitHub / Replit 格式。\n"
    "- 各欄位字面合理且彼此一致、無上述紅旗時,應給 90-100 的高分。\n"
    '只輸出 JSON,格式為 {"confidence": <0-100 整數>, "reason": "<簡短中文理由>"},'
    "不要輸出其他文字或 Markdown 圍欄。"
)


def _build_user_content(req: ApiKeyRequest, matched_department: Department) -> str:
    return (
        "請審查以下 API Key 申請欄位:\n"
        f"- department_name: {req.department_name}\n"
        f"- department_code: {req.department_code}\n"
        f"- project_name: {req.project_name}\n"
        f"- project_url: {req.project_url}\n"
        f"- owner_name: {req.owner_name}\n"
        f"- owner_email: {req.owner_email}\n"
        "\n命中(沿用)的既有部門摘要:\n"
        f"- name: {matched_department.name}\n"
        f"- code: {matched_department.code}\n"
    )


def _parse_content(content: str) -> tuple[int, str]:
    text = content.strip()
    if text.startswith("```"):
        # 去除 ```json ... ``` 圍欄
        text = text.removeprefix("```json").removeprefix("```").strip()
        text = text.removesuffix("```").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # 模型可能在 JSON 前後夾帶說明文字(Anthropic 經 OpenRouter 不嚴格保證
        # json_object),撈出第一個 {...} 區段再 parse;撈不到才讓例外往上拋。
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match is None:
            raise
        data = json.loads(match.group(0))
    confidence = int(data["confidence"])
    confidence = max(0, min(100, confidence))
    reason = str(data.get("reason", ""))
    return confidence, reason


async def validate_fields(
    client: OpenRouterClient,
    req: ApiKeyRequest,
    matched_department: Department,
) -> AgentDecision:
    settings = get_settings()
    if not settings.DEFAULT_OPENROUTER_KEY:
        # 對外僅給通用訊息,不暴露環境變數 / 內部設定;細節走日誌。
        logger.warning("API Key 申請 AI 欄位驗證略過:未設定驗證用金鑰")
        return AgentDecision(
            confidence=0, reason="", error="AI 欄位驗證暫時無法使用,已改由人工審核"
        )

    payload = {
        "model": settings.API_KEY_AGENT_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_content(req, matched_department)},
        ],
        "response_format": {"type": "json_object"},
    }

    try:
        resp = await client.chat_completion(
            payload, api_key=settings.DEFAULT_OPENROUTER_KEY
        )
        content = resp["choices"][0]["message"]["content"]
    except Exception:  # noqa: BLE001
        # 完整例外(含上游供應商 / 狀態碼 / 原始 JSON)只進系統日誌,
        # 對外一律收斂為通用訊息,避免暴露內部 API 設計。
        logger.exception("API Key 申請 AI 欄位驗證失敗:OpenRouter 呼叫失敗")
        return AgentDecision(
            confidence=0, reason="", error="AI 欄位驗證暫時無法使用,已改由人工審核"
        )

    # 記錄 AI 原始輸出供除錯(模型是否照格式吐 JSON / 信心理由)。
    logger.info("API Key 申請 AI 欄位驗證原始回覆: %r", content)

    try:
        confidence, reason = _parse_content(content)
    except Exception:  # noqa: BLE001
        # 解析失敗(模型未照 JSON 格式)→ 連同原始內容記錄,對外仍收斂為通用訊息。
        logger.exception(
            "API Key 申請 AI 欄位驗證失敗:回覆非預期格式,原始內容=%r", content
        )
        return AgentDecision(
            confidence=0, reason="", error="AI 欄位驗證暫時無法使用,已改由人工審核"
        )

    return AgentDecision(confidence=confidence, reason=reason)
