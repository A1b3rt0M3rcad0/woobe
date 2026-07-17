import asyncio
import os
import sys
from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from shared.infra.database.base import Base
from shared.infra.config import Settings
from modules.identity.infra.database.models import *  # noqa: F401, F403
from modules.core.infra.database.models import *  # noqa: F401, F403
from modules.agent.infra.database.models import *  # noqa: F401, F403
from modules.agent.infra.database.provider_model_repositories import ProviderModelModel  # noqa: F401
from modules.agent.infra.database.vector_snapshot_models import *  # noqa: F401, F403
from modules.network.infra.database.models import *  # noqa: F401, F403
from modules.network.infra.database.schema_extensions import *  # noqa: F401, F403
from modules.metering.infra.database.models import *  # noqa: F401, F403
from modules.billing.infra.database.models import *  # noqa: F401, F403
from modules.observability.infra.database.models import *  # noqa: F401, F403

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = Settings.model_validate({})
sync_url = settings.database_url.replace("+asyncpg", "+psycopg2")
config.set_main_option("sqlalchemy.url", sync_url)

target_metadata = Base.metadata
MANAGED_SCHEMAS = {
    "identity",
    "core",
    "agent",
    "network",
    "metering",
    "billing",
    "observability",
}


def include_name(name: str | None, type_: str, _parent_names: Any) -> bool:
    if type_ == "schema":
        return name is None or name in MANAGED_SCHEMAS
    return True


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        include_schemas=True,
        include_name=include_name,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        include_name=include_name,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = configuration["sqlalchemy.url"].replace(
        "+psycopg2", "+asyncpg"
    )
    connectable = async_engine_from_config(
        configuration,
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
