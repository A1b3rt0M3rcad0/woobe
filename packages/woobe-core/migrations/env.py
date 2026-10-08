import asyncio
import os
from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from modules.agent.infra.database.asac_models import *  # noqa: F401,F403
from modules.network.infra.database.asac_models import *  # noqa: F401,F403
from modules.agent.infra.database.skill_models import *  # noqa: F401,F403
from modules.agent.infra.database.context_models import *  # noqa: F401,F403
from modules.agent.infra.database.models import *  # noqa: F401,F403
from modules.agent.infra.database.provider_model_repositories import ProviderModelModel  # noqa: F401
from modules.agent.infra.database.release_activation_repository import (
    AgentReleaseActivationModel,  # noqa: F401
)
from modules.agent.infra.database.run_models import *  # noqa: F401,F403
from modules.agent.infra.database.vector_snapshot_models import *  # noqa: F401,F403
from modules.chat_surface.infra.database.models import *  # noqa: F401,F403
from modules.core.infra.database.control_key_models import *  # noqa: F401,F403
from modules.identity.infra.database.authority_models import *  # noqa: F401,F403
from modules.core.infra.database.models import *  # noqa: F401,F403
from modules.identity.infra.database.models import *  # noqa: F401,F403
from modules.metering.infra.database.models import *  # noqa: F401,F403
from modules.network.infra.database.models import *  # noqa: F401,F403
from modules.network.infra.database.schema_extensions import *  # noqa: F401,F403
from modules.observability.infra.database.models import *  # noqa: F401,F403
from modules.package.infra.models import *  # noqa: F401,F403
from shared.infra.database.admin_idempotency import AdministrativeOperationModel  # noqa: F401
from shared.infra.database.base import Base


def _async_postgres_url(value: str) -> str:
    normalized = value.strip()
    if normalized.startswith("postgres://"):
        return normalized.replace("postgres://", "postgresql+asyncpg://", 1)
    if normalized.startswith("postgresql://"):
        return normalized.replace("postgresql://", "postgresql+asyncpg://", 1)
    if normalized.startswith("postgresql+asyncpg://"):
        return normalized
    raise RuntimeError("WOOBE_POSTGRES_URL must be a PostgreSQL connection URL")


config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

postgres_url = os.environ.get("WOOBE_POSTGRES_URL", "").strip()
if not postgres_url:
    raise RuntimeError(
        "WOOBE_POSTGRES_URL is required for migrations; migrations must connect "
        "directly to PostgreSQL instead of the runtime pool"
    )

sync_url = _async_postgres_url(postgres_url).replace("+asyncpg", "+psycopg2")
config.set_main_option("sqlalchemy.url", sync_url)

target_metadata = Base.metadata
MANAGED_SCHEMAS = {
    "identity",
    "core",
    "chat_surface",
    "agent",
    "network",
    "metering",
    "observability",
    "package",
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


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
