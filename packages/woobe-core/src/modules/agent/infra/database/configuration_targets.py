"""Bounded owner inventory for Project configuration diagnostics."""
from sqlalchemy import select
from modules.agent.infra.database.models import AgentModel, AgentReleaseModel
from modules.agent.infra.database.asac_models import ASaCEnvironmentSelectionModel


async def configuration_targets(session, *, project_id, environment, limit):
    rows = (await session.scalars(select(AgentModel.id).where(AgentModel.project_id == project_id)
        .order_by(AgentModel.id).limit(limit + 1))).all()
    selected = set(rows) if environment == 'draft' else set((await session.scalars(select(AgentReleaseModel.agent_id).where(
        AgentReleaseModel.project_id == project_id, AgentReleaseModel.agent_id.in_(rows), AgentReleaseModel.status == environment))).all())
    if environment != 'draft':
        selected.update((await session.scalars(select(ASaCEnvironmentSelectionModel.resource_id).where(
            ASaCEnvironmentSelectionModel.project_id == project_id, ASaCEnvironmentSelectionModel.resource_id.in_(rows),
            ASaCEnvironmentSelectionModel.environment == environment, ASaCEnvironmentSelectionModel.snapshot_id.is_not(None)))).all())
    return {'targets': [{'kind': 'agent', 'id': identifier, 'selected': identifier in selected} for identifier in rows[:limit]],
            'complete': len(rows) <= limit}
