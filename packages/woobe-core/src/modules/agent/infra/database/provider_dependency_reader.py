from sqlalchemy import select, or_

from modules.agent.infra.database.models import (
    DocumentCollectionModel,
    AgentModel,
    AgentReleaseModel,
)
from modules.agent.infra.database.vector_snapshot_models import VectorSnapshotModel


class SQLProviderDependencyReader:
    def __init__(self, uow, network_consumers=None, surface_consumers=None):
        self._uow = uow
        self._network_consumers, self._surface_consumers = (
            network_consumers,
            surface_consumers,
        )

    async def downstream_consumers(self, project_id, model_ids):
        if (
            not model_ids
            or self._network_consumers is None
            or self._surface_consumers is None
        ):
            return []
        agents = set(
            (
                await self._uow.session.scalars(
                    select(AgentModel.id).where(
                        AgentModel.project_id == project_id,
                        or_(
                            AgentModel.provider_model_id.in_(model_ids),
                            AgentModel.fallback_provider_model_id.in_(model_ids),
                        ),
                    )
                )
            ).all()
        )
        releases = (
            await self._uow.session.execute(
                select(AgentReleaseModel.id, AgentReleaseModel.agent_id).where(
                    AgentReleaseModel.project_id == project_id,
                    or_(
                        AgentReleaseModel.provider_model_id.in_(model_ids),
                        AgentReleaseModel.fallback_provider_model_id.in_(model_ids),
                    ),
                )
            )
        ).all()
        release_ids = {str(row.id) for row in releases}
        agent_ids = {str(item) for item in agents} | {
            str(row.agent_id) for row in releases
        }
        networks = await self._network_consumers(
            project_id=project_id, agent_ids=agent_ids, release_ids=release_ids
        )
        surfaces = await self._surface_consumers(
            project_id=project_id,
            agent_ids=agent_ids,
            release_ids=release_ids,
            network_ids={item["id"] for item in networks},
        )
        return [*networks, *surfaces]

    async def embedding_consumers(self, project_id, model_ids):
        if not model_ids:
            return []
        rows = (
            await self._uow.session.execute(
                select(VectorSnapshotModel, DocumentCollectionModel.name)
                .join(
                    DocumentCollectionModel,
                    DocumentCollectionModel.id == VectorSnapshotModel.collection_id,
                )
                .where(
                    VectorSnapshotModel.project_id == project_id,
                    DocumentCollectionModel.project_id == project_id,
                    VectorSnapshotModel.embedding_provider_model_id.in_(model_ids),
                    VectorSnapshotModel.status.not_in(
                        ["FAILED", "CANCELLED", "ARCHIVED"]
                    ),
                )
                .order_by(VectorSnapshotModel.id)
            )
        ).all()
        return [
            {
                "type": "vector_snapshot",
                "id": str(snapshot.id),
                "name": name,
                "status": snapshot.status,
                "field": "embedding_provider_model_id",
                "provider_model_id": str(snapshot.embedding_provider_model_id),
                "collection_id": str(snapshot.collection_id),
            }
            for snapshot, name in rows
        ]
