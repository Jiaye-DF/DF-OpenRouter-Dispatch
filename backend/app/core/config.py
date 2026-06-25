from __future__ import annotations

import logging
import sys
from functools import lru_cache
from typing import Any, NoReturn

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def fatal_config_exit(message: str) -> NoReturn:
    """致命設定錯誤:記明確原因(stdlib logger + stderr 雙寫,確保容器 log 必可見)
    後正常退出,**不丟 traceback**。

    用於部署環境(如 Coolify)把型別化變數注入為非法值的情境:與其讓
    int()/bool 解析以例外 crash 且無從得知原因,不如清楚說明「哪個變數、什麼壞值、
    怎麼修」,程序乾淨結束(exit code 1,供編排器辨識為設定失敗)。
    """
    logging.getLogger("app.core.config").error(message)
    sys.stderr.write(f"[FATAL] {message}\n")
    sys.stderr.flush()
    raise SystemExit(1)


def coerce_int_env(name: str, raw: Any, default: int) -> int:
    """整數型設定容錯:未設 / 空字串 → 採預設;設了但非整數 → 明確 log 後正常退出。"""
    if raw is None:
        return default
    if isinstance(raw, int) and not isinstance(raw, bool):
        return raw
    text = str(raw).strip()
    if text == "":
        return default
    try:
        return int(text)
    except ValueError:
        fatal_config_exit(
            f"環境變數 {name} 的值 {raw!r} 不是合法整數;"
            "請於部署環境(如 Coolify)修正後重新部署。"
        )


def coerce_bool_env(name: str, raw: Any, default: bool) -> bool:
    """布林型設定容錯:未設 / 空字串 → 採預設;設了但非合法布林 → 明確 log 後正常退出。"""
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    text = str(raw).strip().lower()
    if text == "":
        return default
    if text in {"1", "true", "yes", "on", "t", "y"}:
        return True
    if text in {"0", "false", "no", "off", "f", "n"}:
        return False
    fatal_config_exit(
        f"環境變數 {name} 的值 {raw!r} 不是合法布林值(true/false);"
        "請於部署環境(如 Coolify)修正後重新部署。"
    )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # --- App ---
    APP_ENV: str = "dev"
    APP_NAME: str = "backend"
    # 部署版本標記,供 /api/v1/version 確認線上 build(滾動更新後驗證用)。
    APP_VERSION: str = "1.10.0"
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

    # --- AI 評審 / taskiq + Redis (v2.0) ---
    # AI_EVAL_ENABLED:總開關;關閉時不啟用評審派發(beat / dispatch 不動作)。
    AI_EVAL_ENABLED: bool = False
    # taskiq broker / result backend / 通用 Redis 連線;本版皆走 Redis(不同 db)。
    # ⚠ 含密碼的連線字串為機密,禁 commit 實值;由 .env / Coolify 注入。
    TASKIQ_BROKER_URL: str = "redis://localhost:6379/0"
    TASKIQ_RESULT_BACKEND_URL: str = "redis://localhost:6379/1"
    REDIS_URL: str = "redis://localhost:6379/2"
    # 評審 beat 掃描間隔(秒);每隔此秒數撈一批未評審 usage log 派發。
    AI_EVAL_BEAT_INTERVAL_SECONDS: int = 300
    # 單次 beat 派發的最大筆數(批量上限,避免一次灌爆 worker)。
    AI_EVAL_DISPATCH_BATCH_SIZE: int = 100
    # 單一評審任務失敗時的最大重試次數(配合 SimpleRetryMiddleware)。
    AI_EVAL_TASK_MAX_RETRIES: int = 3

    # --- Seq Log ---
    # SEQ_INGESTION_URL 留空則只走 console(本機開發 / CI 不對外連線);
    # 正式環境由 compose 注入 http://seq。SEQ_API_KEY 可留空。
    SEQ_INGESTION_URL: str = ""
    SEQ_API_KEY: str = ""

    # --- M365 Mail 服務 (v1.9.2) ---
    # 開通完成後以 Microsoft Graph(app-only)寄 Email 通知專案負責人。
    # 四者皆有值才啟用(見 m365_mail_enabled);缺任一則優雅略過,不寄信不報錯。
    # M365_CLIENT_SECRET 為機密,由 Coolify 注入,禁止 commit。
    M365_TENANT_ID: str = ""
    M365_CLIENT_ID: str = ""
    M365_CLIENT_SECRET: str = ""
    M365_MAIL_SENDER: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_prod(self) -> bool:
        return self.APP_ENV.lower() in ("prod", "production")

    # v2.0.1 型別化評審設定:容錯部署注入(空字串 → 預設;壞值 → 明確 log 後正常退出),
    # 避免 Coolify 等把 ${VAR} 未定義代成空字串時,pydantic 解析以例外 crash 且無從得知原因。
    @field_validator("AI_EVAL_ENABLED", mode="before")
    @classmethod
    def _coerce_ai_eval_enabled(cls, v: Any) -> bool:
        return coerce_bool_env("AI_EVAL_ENABLED", v, False)

    @field_validator("AI_EVAL_BEAT_INTERVAL_SECONDS", mode="before")
    @classmethod
    def _coerce_ai_eval_beat(cls, v: Any) -> int:
        return coerce_int_env("AI_EVAL_BEAT_INTERVAL_SECONDS", v, 300)

    @field_validator("AI_EVAL_DISPATCH_BATCH_SIZE", mode="before")
    @classmethod
    def _coerce_ai_eval_batch(cls, v: Any) -> int:
        return coerce_int_env("AI_EVAL_DISPATCH_BATCH_SIZE", v, 100)

    @field_validator("AI_EVAL_TASK_MAX_RETRIES", mode="before")
    @classmethod
    def _coerce_ai_eval_max_retries(cls, v: Any) -> int:
        return coerce_int_env("AI_EVAL_TASK_MAX_RETRIES", v, 3)

    @model_validator(mode="after")
    def _fail_fast_in_prod(self) -> Settings:
        """正式環境啟動把關:安全前提缺漏即 raise,避免靜默以最不安全狀態上線。"""
        if not self.is_prod:
            return self
        errors: list[str] = []
        if len(self.JWT_SECRET) < 32:
            errors.append("JWT_SECRET 長度須 >= 32")
        if not self.cors_origins_list:
            errors.append("CORS_ORIGINS 不可為空(prod 不允許回退為任意來源)")
        if errors:
            raise ValueError("正式環境組態檢查失敗:" + "；".join(errors))
        return self

    @property
    def sso_enabled(self) -> bool:
        """三項 SSO 設定皆有值才啟用 SSO 登入流程。"""
        return bool(self.SSO_URL and self.SSO_APP_ID and self.SSO_APP_SECRET)

    @property
    def m365_mail_enabled(self) -> bool:
        """四項 M365 設定皆有值才啟用 Graph 寄信(否則優雅略過)。"""
        return bool(
            self.M365_TENANT_ID
            and self.M365_CLIENT_ID
            and self.M365_CLIENT_SECRET
            and self.M365_MAIL_SENDER
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
