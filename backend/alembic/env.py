"""Alembic 環境設定。

App runtime 使用 asyncpg,但 migration 使用 sync psycopg driver,理由:
1. baseline 的 `CREATE OR REPLACE FUNCTION ... $$ ... $$ LANGUAGE plpgsql` 內含 `;`,
   無法依分號切割成單一 statement。
2. asyncpg 的 prepared statement protocol 不支援單次送多個 statement。

env.py 會把 `postgresql+asyncpg://` 改寫為 `postgresql+psycopg://`,
讓 alembic 用 sync 連線,並支援 multi-statement SQL。
"""

from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.core.config import get_settings
from app.models import Base  # noqa: F401  匯入以註冊所有 model metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _sync_database_url() -> str:
    url = get_settings().DATABASE_URL
    return url.replace("+asyncpg", "+psycopg", 1) if "+asyncpg" in url else url


config.set_main_option("sqlalchemy.url", _sync_database_url())

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
