"""Email HTML 範本 render 層(v1.9.2)。

以 Jinja2 載入 `app/templates/email/` 下的範本,並統一注入基底 context
(`brand_name` / `platform_url` / `user_guide_url` / `current_year`),
呼叫端傳入的 ctx 可覆寫預設。
"""

from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import get_settings

# 範本目錄:本檔位於 app/services/,範本位於 app/templates/email/。
_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "email"

# APP_NAME 預設值(config 預設)時改用的固定品牌字串。
_DEFAULT_APP_NAME = "backend"
_BRAND_FALLBACK = "DF OpenRouter 平台"

# 信件內連結固定指向正式站(收件人不分環境,點擊都應到正式平台;
# 不取 FRONTEND_URL,避免由 dev / test 寄出時連到 localhost)。
_PLATFORM_URL = "https://df-it-openrouter-dispatch.it.zerozero.tw"
_USER_GUIDE_URL = f"{_PLATFORM_URL}/user-guide"
# 對外 API(代理端點)正式站位址,供信中基礎呼叫範例使用。
_API_CHAT_URL = "https://df-it-openrouter-dispatch-api.it.zerozero.tw/api/v1/model/chat"


@lru_cache(maxsize=1)
def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )


def render_email(template_name: str, **ctx: object) -> str:
    """render 指定 Email 範本為 HTML 字串。

    自動補基底 context(brand_name / platform_url / current_year);
    呼叫端傳入的 ctx 同名鍵會覆寫預設值。
    """
    settings = get_settings()
    brand_name = settings.APP_NAME if settings.APP_NAME != _DEFAULT_APP_NAME else _BRAND_FALLBACK
    base_ctx: dict[str, object] = {
        "brand_name": brand_name,
        "platform_url": _PLATFORM_URL,
        "user_guide_url": _USER_GUIDE_URL,
        "api_chat_url": _API_CHAT_URL,
        "current_year": datetime.now(tz=UTC).year,
    }
    base_ctx.update(ctx)
    return _env().get_template(template_name).render(**base_ctx)
