"""Bounded owner check before irreversible source cutover."""
from sqlalchemy import select
from modules.agent.infra.database.run_models import AgentRunModel
from modules.agent.infra.database.vector_snapshot_models import VectorSnapshotModel
from shared.contracts.project_configuration import ConfigurationError


async def assert_configuration_quiescent(session, *, project_id):
    active_run = await session.scalar(select(AgentRunModel.id).where(
        AgentRunModel.project_id == project_id,
        AgentRunModel.status.in_(("running", "uncertain"))).limit(1))
    active_build = await session.scalar(select(VectorSnapshotModel.id).where(
        VectorSnapshotModel.project_id == project_id,
        VectorSnapshotModel.status == "BUILDING").limit(1))
    if active_run is not None or active_build is not None:
        raise ConfigurationError("CONFIG_MIGRATION_WORK_PENDING")
