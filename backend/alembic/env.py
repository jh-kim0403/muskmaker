"""
Alembic env.py — async-compatible migration environment.

Uses asyncio + asyncpg to run migrations against the same async engine
as the FastAPI application.
"""
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Import Base so all models are registered with metadata before autogenerate
from app.models import Base  # noqa: F401 — registers all table metadata
from app.config import get_settings

# ── Alembic config ────────────────────────────────────────────────────────────
config = context.config
settings = get_settings()

# Inject the real DB URL from settings (overrides empty sqlalchemy.url in alembic.ini)
config.set_main_option("sqlalchemy.url", settings.database_url)

# Logging setup from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata for --autogenerate support
target_metadata = Base.metadata


# ── Offline migrations (generate SQL without connecting) ──────────────────────
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,         # detect column type changes
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online migrations (connect and run) ───────────────────────────────────────
def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
