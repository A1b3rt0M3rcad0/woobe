"""Bounded owner inventory for Project configuration diagnostics."""
from sqlalchemy import select
from modules.agent.infra.database.models import AgentModel, AgentReleaseModel
from modules.agent.infra.database.asac_models import ASaCEnvironmentSelectionModel


async def configuration_targets(session, *, project_id, environment, limit, after_id=None):
    query = select(AgentModel.id).where(AgentModel.project_id == project_id)
    if after_id is not None:
        query = query.where(AgentModel.id > after_id)
    rows = (await session.scalars(query.order_by(AgentModel.id).limit(limit + 1))).all()
    selected = set(rows) if environment == 'draft' else set((await session.scalars(select(AgentReleaseModel.agent_id).where(
        AgentReleaseModel.project_id == project_id, AgentReleaseModel.agent_id.in_(rows), AgentReleaseModel.status == environment))).all())
    if environment != 'draft':
        selected.update((await session.scalars(select(ASaCEnvironmentSelectionModel.resource_id).where(
            ASaCEnvironmentSelectionModel.project_id == project_id, ASaCEnvironmentSelectionModel.resource_id.in_(rows),
            ASaCEnvironmentSelectionModel.environment == environment, ASaCEnvironmentSelectionModel.snapshot_id.is_not(None)))).all())
    targets = [{'kind': 'agent', 'id': identifier, 'selected': identifier in selected} for identifier in rows]
    return {'targets': targets[:limit], 'authorization_targets': targets,
            'complete': len(rows) <= limit, 'after_id': rows[min(limit, len(rows)) - 1] if rows else after_id}
