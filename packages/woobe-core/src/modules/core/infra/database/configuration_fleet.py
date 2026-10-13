"""SQL barrier for an explicitly enumerated configuration bridge fleet.

An operator must first drain/remove pre-bridge processes from the deployment.
The database cannot discover processes that never registered. The required fleet
is an operator-supplied inventory, not inferred from whichever rows happen to be
alive. An empty inventory never authorizes cutover.
"""
from datetime import timedelta
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from modules.core.infra.database.configuration_models import ConfigurationProcessModel
from shared.contracts.project_configuration import ConfigurationError

BRIDGE_CAPABILITY = 'project_configuration.bridge.v1'


async def register_configuration_process(session, *, identity, capabilities, ttl_seconds=90):
    if not isinstance(identity, str) or not 1 <= len(identity) <= 255 or not 15 <= ttl_seconds <= 300:
        raise ConfigurationError('CONFIG_DEFINITION_INVALID')
    if not isinstance(capabilities, list) or len(capabilities) > 32 or any(not isinstance(item, str) or len(item) > 128 for item in capabilities):
        raise ConfigurationError('CONFIG_DEFINITION_INVALID')
    await session.execute(select(func.pg_advisory_xact_lock(7470, 1)))
    instant = await session.scalar(select(func.clock_timestamp()))
    statement = insert(ConfigurationProcessModel).values(process_identity=identity, capabilities=sorted(set(capabilities)),
        expires_at=instant + timedelta(seconds=ttl_seconds))
    await session.execute(statement.on_conflict_do_update(index_elements=['process_identity'], set_={
        'capabilities': statement.excluded.capabilities, 'expires_at': statement.excluded.expires_at}))


async def assert_configuration_bridge(session, *, required_processes):
    if (not isinstance(required_processes, list) or not required_processes or len(required_processes) > 1000
            or any(not isinstance(item, str) or not item for item in required_processes)
            or len(set(required_processes)) != len(required_processes)):
        raise ConfigurationError('CONFIG_BRIDGE_REQUIRED')
    await session.execute(select(func.pg_advisory_xact_lock(7470, 1)))
    # Hold shared row locks through source cutover. A process changing its
    # advertised protocol cannot race an already-authorized migration commit.
    rows = (await session.scalars(select(ConfigurationProcessModel).where(
        ConfigurationProcessModel.process_identity.in_(required_processes)).with_for_update(read=True))).all()
    instant = await session.scalar(select(func.clock_timestamp()))
    if len(rows) != len(required_processes) or any(row.expires_at <= instant or BRIDGE_CAPABILITY not in row.capabilities for row in rows):
        raise ConfigurationError('CONFIG_BRIDGE_REQUIRED')
    # Registered live incompatible processes cannot be omitted from the list.
    incompatible = await session.scalar(select(ConfigurationProcessModel.id).where(
        ConfigurationProcessModel.expires_at > instant,
        ~ConfigurationProcessModel.capabilities.contains([BRIDGE_CAPABILITY])).limit(1))
    if incompatible is not None:
        raise ConfigurationError('CONFIG_BRIDGE_REQUIRED')
