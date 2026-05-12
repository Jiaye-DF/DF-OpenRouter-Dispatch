from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # --- App ---
    APP_ENV: str = "dev"
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

    # --- OpenRouter ---
    OPENROUTER_API_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_API_TIMEOUT: int = 60

    # --- Internal LLM (v1.2) ---
    INTERNAL_LLM_BASE_URL: str = ""              # 空 = 停用本地模型
    INTERNAL_LLM_API_KEY: str = ""               # 可空(內網信任)
    INTERNAL_LLM_REQUEST_TIMEOUT: int = 120      # 單次呼叫 httpx timeout(秒)
    INTERNAL_LLM_RPM_LIMIT: int = 60             # 每分鐘最大呼叫數(0 = 不限)
    INTERNAL_LLM_MIN_REQUEST_INTERVAL_MS: int = 0  # 連續呼叫最小間隔(毫秒;0 = 不限)
    INTERNAL_LLM_RATE_WAIT_TIMEOUT: int = 60     # 撞限額時最長等待秒數,超過 → 429 internal_busy

    # --- Dev Seed ---
    DEFAULT_OPENROUTER_KEY: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_prod(self) -> bool:
        return self.APP_ENV.lower() in ("prod", "production")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
