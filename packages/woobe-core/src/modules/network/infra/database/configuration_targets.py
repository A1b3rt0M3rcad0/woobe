"""Bounded owner inventory for Project configuration diagnostics."""
from sqlalchemy import select
from modules.network.infra.database.models import NetworkModel


async def configuration_targets(session, *, project_id, environment, limit):
    rows = (await session.execute(select(NetworkModel.id, NetworkModel.staging_version_id, NetworkModel.production_version_id).where(NetworkModel.project_id == project_id)
        .order_by(NetworkModel.id).limit(limit + 1))).all()
    from modules.network.infra.database.asac_models import ASaCEnvironmentSelectionModel
    selected = set((await session.scalars(select(ASaCEnvironmentSelectionModel.resource_id).where(
        ASaCEnvironmentSelectionModel.project_id == project_id, ASaCEnvironmentSelectionModel.resource_id.in_([row.id for row in rows]),
        ASaCEnvironmentSelectionModel.environment == environment, ASaCEnvironmentSelectionModel.snapshot_id.is_not(None)))).all()) if environment != 'draft' else set()
    return {'targets': [{'kind': 'network', 'id': row.id, 'selected': environment == 'draft' or row.id in selected or bool(getattr(row, environment + '_version_id'))} for row in rows[:limit]],
            'complete': len(rows) <= limit}
