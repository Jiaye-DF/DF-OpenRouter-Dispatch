from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # --- App ---
    APP_ENV: str = "dev"
    APP_NAME: str = "backend"
    LOG_LEVEL: str = "INFO"

    # --- Backend / Uvicorn ---
    UVICORN_WORKERS: int = 1

    # --- Database ---
    DATABASE_URL: str

    # --- Auth / Security ---
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRES_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRES_DAYS: int = 7
    ACCESS_COOKIE_NAME: str = "access_token"
    REFRESH_COOKIE_NAME: str = "refresh_token"
    ENCRYPTION_KEY: str  # base64-encoded 32 bytes
    CORS_ORIGINS: str = ""

    # --- Admin Bootstrap ---
    INITIAL_ADMIN_ACCOUNT: str
    INITIAL_ADMIN_USERNAME: str
    INITIAL_ADMIN_PASSWORD: str
    # 可選:首位 admin 的 Email。填入後 Seed 會寫入(或回填)admin.email,
    # 使該帳號可直接以 DF-SSO 登入(SSO 以 Email 對應本地帳號)。
    INITIAL_ADMIN_EMAIL: str = ""

    # --- DF-SSO 登入器整合 ---
    # SSO 中央伺服器位址;三者皆有值才視為啟用 SSO 登入(見 sso_enabled)。
    #   Test: https://df-sso-login-test.apps.zerozero.tw
    #   Prod: https://df-it-sso-login.it.zerozero.tw
    # SSO_APP_ID / SSO_APP_SECRET 由對應環境的 SSO Dashboard 各自發放;
    # SSO_APP_SECRET 為機密,禁止寫入前端或 commit。
    SSO_URL: str = ""
    SSO_APP_ID: str = ""
    SSO_APP_SECRET: str = ""
    SSO_TIMEOUT_SECONDS: float = 8.0
    # 前後端分離:BACKEND_URL = SSO callback 落點 origin(Dashboard redirect_uris 需登記);
    #            FRONTEND_URL = 登入頁 / dashboard 落點 origin。
    BACKEND_URL: str = ""
    FRONTEND_URL: str = ""

    # --- OpenRouter ---
    OPENROUTER_API_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_API_TIMEOUT: int = 60
    # 串流(SSE)用獨立 read timeout:串流連線需長時間維持,chunk 間可能久無資料,
    # 故與一般呼叫分開,避免被 OPENROUTER_API_TIMEOUT(60s)提早中斷。
    OPENROUTER_STREAM_TIMEOUT: int = 300
    # 申請單 AI 欄位驗證模型(經 OpenRouter 呼叫)
    API_KEY_AGENT_MODEL: str = "anthropic/claude-sonnet-4.6"

    # --- Internal LLM (v1.2) ---
    # base_url / api_key / rpm_limit / min_interval 已移至 DB(`internal_keys` 表,per-Key 設定);
    # 此處僅保留「系統層級、所有 Key 共用」的兩個 timeout。
    INTERNAL_LLM_REQUEST_TIMEOUT: int = 120      # 單次呼叫 httpx timeout(秒,共用 httpx client)
    INTERNAL_LLM_RATE_WAIT_TIMEOUT: int = 60     # 全部 Key 撞限額後最長等待秒數,超過 → 429 internal_busy

    # --- Dev Seed ---
    DEFAULT_OPENROUTER_KEY: str = ""

    # --- Seq Log ---
    # SEQ_INGESTION_URL 留空則只走 console(本機開發 / CI 不對外連線);
    # 正式環境由 compose 注入 http://seq。SEQ_API_KEY 可留空。
    SEQ_INGESTION_URL: str = ""
    SEQ_API_KEY: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_prod(self) -> bool:
        return self.APP_ENV.lower() in ("prod", "production")

    @property
    def sso_enabled(self) -> bool:
        """三項 SSO 設定皆有值才啟用 SSO 登入流程。"""
        return bool(self.SSO_URL and self.SSO_APP_ID and self.SSO_APP_SECRET)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
