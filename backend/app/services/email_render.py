"""Email HTML 範本 render 層(v1.9.2)。

以 Jinja2 載入 `app/templates/email/` 下的範本,並統一注入基底 context
(`brand_name` / `platform_url` / `current_year`),呼叫端傳入的 ctx 可覆寫預設。
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
        "platform_url": settings.FRONTEND_URL or "",
        "current_year": datetime.now(tz=UTC).year,
    }
    base_ctx.update(ctx)
    return _env().get_template(template_name).render(**base_ctx)
