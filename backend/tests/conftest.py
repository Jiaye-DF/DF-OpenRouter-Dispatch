import base64
import os

# 測試前先注入最小必要 env var，確保 Settings() 可成功建立
os.environ.setdefault("APP_ENV", "dev")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET", "test_jwt_secret_for_unit_tests_0123456789abcdef")
os.environ.setdefault(
    "ENCRYPTION_KEY", base64.b64encode(b"0123456789abcdef0123456789abcdef").decode()
)
os.environ.setdefault("INITIAL_ADMIN_ACCOUNT", "admin")
os.environ.setdefault("INITIAL_ADMIN_USERNAME", "admin")
os.environ.setdefault("INITIAL_ADMIN_PASSWORD", "Admin#Pass2026!")
