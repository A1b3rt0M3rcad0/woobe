"""Network owner metadata guard for configuration source cutover."""
from sqlalchemy import select
from modules.network.infra.database.models import NetworkExecutionModel
from shared.contracts.project_configuration import ConfigurationError


async def assert_configuration_quiescent(session, *, project_id):
    active = await session.scalar(select(NetworkExecutionModel.id).where(
        NetworkExecutionModel.project_id == project_id,
        NetworkExecutionModel.status.in_(("queued", "running", "cancel_requested", "uncertain"))).limit(1))
    if active is not None:
        raise ConfigurationError("CONFIG_MIGRATION_WORK_PENDING")
